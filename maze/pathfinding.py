"""Pathfinding algorithms over the maze grid.

Two families live here:

*Search solvers* -- take ``(grid, start, goal)`` and return a ``SearchResult``
with the path plus instrumentation (nodes expanded, peak frontier size).
Benchmarks consume these numbers; the game uses the paths for hints, live
"steps to exit" HUDs, and the post-game efficiency stat.

    bfs, dfs, dijkstra, astar (Manhattan or Euclidean heuristic),
    greedy_best_first, bidirectional_bfs

*Gameplay solvers* -- the classic human maze-solving rules, kept because they
make great demos and AI opponents:

    wall_follower  (right/left hand on the wall; walks the maze, no map needed)
    dead_end_filling (prune dead ends until only the path remains)

Every solver returns ``SearchResult``; ``path`` is ``None`` when the goal is
unreachable.  In a perfect maze every cell is reachable, so that only happens
on degenerate grids (e.g. a fully-walled one in tests).
"""
from __future__ import annotations

import heapq
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .grid import DELTA, DIRS, E, N, OPPOSITE, S, W, Grid

Cell = Tuple[int, int]

# Headings rotated 90 degrees clockwise / counter-clockwise (screen +y is down).
ROT_RIGHT = {N: E, E: S, S: W, W: N}
ROT_LEFT = {v: k for k, v in ROT_RIGHT.items()}


@dataclass
class SearchResult:
    """One solver run: the path (or None) plus instrumentation."""

    algorithm: str
    path: Optional[List[Cell]]
    nodes_expanded: int = 0
    frontier_peak: int = 0
    extra: Dict[str, int] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return self.path is not None

    @property
    def length(self) -> int:
        """Path length in steps; -1 when no path was found."""
        return -1 if self.path is None else len(self.path) - 1


# ---------------------------------------------------------------- heuristics
def manhattan(a: Cell, b: Cell) -> int:
    """|dx| + |dy| -- admissible & consistent for 4-directional grids."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def euclidean(a: Cell, b: Cell) -> float:
    """Straight-line distance.  Admissible (never overestimates on a grid)."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ------------------------------------------------------------------- helpers
def _neighbors(grid: Grid, cell: Cell) -> List[Cell]:
    """Open (wall-free) neighbors of ``cell``."""
    x, y = cell
    out: List[Cell] = []
    for d in DIRS:
        if grid.can_go(x, y, d):
            dx, dy = DELTA[d]
            out.append((x + dx, y + dy))
    return out


def _reconstruct(came_from: Dict[Cell, Optional[Cell]], start: Cell, goal: Cell) -> List[Cell]:
    """Walk the parent chain backwards from goal to start, then reverse."""
    path = [goal]
    cur = goal
    while cur != start:
        cur = came_from[cur]
        path.append(cur)
    path.reverse()
    return path


# ----------------------------------------------------------------------- BFS
def bfs(grid: Grid, start: Cell, goal: Cell) -> SearchResult:
    """Breadth-first search.  Optimal on unweighted grids."""
    if start == goal:
        return SearchResult("bfs", [start])
    came: Dict[Cell, Optional[Cell]] = {start: None}
    q = deque([start])
    expanded = 0
    peak = 1
    while q:
        cur = q.popleft()
        expanded += 1
        for nb in _neighbors(grid, cur):
            if nb in came:
                continue
            came[nb] = cur
            if nb == goal:
                # Goal test at discovery: valid + optimal for BFS.
                return SearchResult("bfs", _reconstruct(came, start, goal), expanded, max(peak, len(q)))
            q.append(nb)
        peak = max(peak, len(q))
    return SearchResult("bfs", None, expanded, peak)


# ----------------------------------------------------------------------- DFS
def dfs(grid: Grid, start: Cell, goal: Cell) -> SearchResult:
    """Depth-first search.  Finds *a* path, never the short one on purpose.

    Kept both as a baseline (the classic contrast to BFS in textbooks and in
    the benchmark tables) and because "the AI wanders" is a fun opponent.
    """
    if start == goal:
        return SearchResult("dfs", [start])
    came: Dict[Cell, Optional[Cell]] = {start: None}
    stack: List[Cell] = [start]
    visited = {start}
    expanded = 0
    peak = 1
    while stack:
        cur = stack.pop()
        if cur == goal:
            return SearchResult("dfs", _reconstruct(came, start, goal), expanded, peak)
        visited.add(cur)
        expanded += 1
        for nb in _neighbors(grid, cur):
            if nb not in came:
                came[nb] = cur
                stack.append(nb)
        peak = max(peak, len(stack))
    return SearchResult("dfs", None, expanded, peak)


# ------------------------------------------------------------------ Dijkstra
def dijkstra(grid: Grid, start: Cell, goal: Cell) -> SearchResult:
    """Dijkstra with a binary heap.  On a unit-cost grid this is BFS with a
    priority queue: same optimal path, higher constant factor -- which is
    exactly what the benchmarks quantify."""
    if start == goal:
        return SearchResult("dijkstra", [start])
    counter = 0  # heap tiebreak; also prevents comparing cells
    dist: Dict[Cell, int] = {start: 0}
    came: Dict[Cell, Optional[Cell]] = {start: None}
    heap = [(0, counter, start)]
    counter += 1
    closed = set()
    expanded = 0
    peak = 1
    while heap:
        d, _, cur = heapq.heappop(heap)
        if cur in closed:
            continue  # stale entry
        closed.add(cur)
        if cur == goal:
            return SearchResult("dijkstra", _reconstruct(came, start, goal), expanded, peak)
        expanded += 1
        for nb in _neighbors(grid, cur):
            if nb in closed:
                continue
            nd = d + 1
            if nd < dist.get(nb, 1 << 30):
                dist[nb] = nd
                came[nb] = cur
                heapq.heappush(heap, (nd, counter, nb))
                counter += 1
        peak = max(peak, len(heap))
    return SearchResult("dijkstra", None, expanded, peak)


# ----------------------------------------------------------------------- A*
def astar(
    grid: Grid,
    start: Cell,
    goal: Cell,
    heuristic: Callable[[Cell, Cell], float] = manhattan,
) -> SearchResult:
    """A* search.  Optimal for any admissible heuristic (both here are).

    Heap entries are ``(f, g, counter, node)``: ties on f prefer lower g,
    i.e. deeper nodes -- a well-known micro-optimization that pushes the
    search toward the goal instead of bouncing around the frontier rim.
    """
    h = heuristic
    name = "astar_manhattan" if h is manhattan else "astar_euclidean"
    if start == goal:
        return SearchResult(name, [start])
    counter = 0
    g: Dict[Cell, int] = {start: 0}
    came: Dict[Cell, Optional[Cell]] = {start: None}
    heap = [(h(start, goal), 0, counter, start)]
    counter += 1
    closed = set()
    expanded = 0
    peak = 1
    while heap:
        f, gcur, _, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        if cur == goal:
            return SearchResult(name, _reconstruct(came, start, goal), expanded, peak)
        expanded += 1
        for nb in _neighbors(grid, cur):
            if nb in closed:
                continue
            ng = gcur + 1
            if ng < g.get(nb, 1 << 30):
                g[nb] = ng
                came[nb] = cur
                heapq.heappush(heap, (ng + h(nb, goal), ng, counter, nb))
                counter += 1
        peak = max(peak, len(heap))
    return SearchResult(name, None, expanded, peak)


# -------------------------------------------------------- Greedy best-first
def greedy_best_first(grid: Grid, start: Cell, goal: Cell) -> SearchResult:
    """Best-first on the heuristic alone.  Fast, not optimal -- the benchmark
    table shows it trading path quality for expanded-node count."""
    if start == goal:
        return SearchResult("greedy_best_first", [start])
    h = manhattan
    counter = 0
    came: Dict[Cell, Optional[Cell]] = {start: None}
    heap = [(h(start, goal), counter, start)]
    counter += 1
    closed = set()
    expanded = 0
    peak = 1
    while heap:
        _, _, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        if cur == goal:
            return SearchResult("greedy_best_first", _reconstruct(came, start, goal), expanded, peak)
        expanded += 1
        for nb in _neighbors(grid, cur):
            if nb in closed:
                continue
            if nb not in came:
                came[nb] = cur
                heapq.heappush(heap, (h(nb, goal), counter, nb))
                counter += 1
        peak = max(peak, len(heap))
    return SearchResult("greedy_best_first", None, expanded, peak)


# ------------------------------------------------------- Bidirectional BFS
def bidirectional_bfs(grid: Grid, start: Cell, goal: Cell) -> SearchResult:
    """BFS from both ends, alternating one *complete frontier layer* at a time.

    Correctness subtlety worth a comment: we may only stop once the two
    *discovered* sets intersect after finishing a full layer on one side.
    A shortest s-t path of length L has a midpoint at distance floor(L/2)
    from s and ceil(L/2) from t; alternating layers guarantees both sides
    have discovered it by the time any intersection can exist (any
    intersecting node proves depth0 + depth1 >= L).  Taking the minimum
    d0(m) + d1(m) over the intersection therefore reconstructs a shortest
    path -- the tests assert this against plain BFS on hundreds of mazes.
    """
    if start == goal:
        return SearchResult("bidirectional_bfs", [start])
    came = [{start: None}, {goal: None}]
    disc = [{start}, {goal}]
    qs = [deque([start]), deque([goal])]
    expanded = 0
    peak = 2
    side = 0
    while qs[0] and qs[1]:
        # Expand one full layer of the current side.
        for _ in range(len(qs[side])):
            cur = qs[side].popleft()
            expanded += 1
            for nb in _neighbors(grid, cur):
                if nb not in disc[side]:
                    disc[side].add(nb)
                    came[side][nb] = cur
                    qs[side].append(nb)
        peak = max(peak, len(qs[0]) + len(qs[1]))
        inter = disc[0] & disc[1]
        if inter:
            best: Optional[Tuple[int, List[Cell]]] = None
            for m in inter:
                p0 = _reconstruct(came[0], start, m)          # start .. m
                p1 = _reconstruct(came[1], goal, m)           # goal .. m
                total = (len(p0) - 1) + (len(p1) - 1)
                if best is None or total < best[0]:
                    best = (total, p0 + list(reversed(p1))[1:])
            assert best is not None
            return SearchResult("bidirectional_bfs", best[1], expanded, peak)
        side = 1 - side
    return SearchResult("bidirectional_bfs", None, expanded, peak)


# --------------------------------------------------------------- wall follower
def wall_follower(
    grid: Grid, start: Cell, goal: Cell, hand: str = "right"
) -> SearchResult:
    """The classic human rule: keep one hand on the wall and walk.

    At each cell, try directions in order (for the right hand): turn right,
    go straight, turn left, u-turn.  In a simply-connected maze (no loops --
    exactly what a perfect maze is) this traverses every edge at most twice,
    so it always reaches any reachable cell.  It never knows the map: pure
    local decisions, which is the fun part.
    """
    algorithm = f"wall_follower_{hand}"
    if hand not in ("left", "right"):
        raise ValueError("hand must be 'left' or 'right'")
    if start == goal:
        return SearchResult(algorithm, [start])
    x, y = start
    heading = None
    for d in DIRS:
        if grid.can_go(x, y, d):
            heading = d
            break
    if heading is None:  # isolated cell
        return SearchResult(algorithm, None, extra={"steps": 0})
    # Every edge is walked at most twice: bound total steps by 4 * cells.
    max_steps = 4 * grid.width * grid.height + 8
    path = [start]
    steps = 0
    while (x, y) != goal:
        if hand == "right":
            order = (ROT_RIGHT[heading], heading, ROT_LEFT[heading], OPPOSITE[heading])
        else:
            order = (ROT_LEFT[heading], heading, ROT_RIGHT[heading], OPPOSITE[heading])
        chosen = None
        for d in order:
            if grid.can_go(x, y, d):
                chosen = d
                break
        if chosen is None:  # fully isolated pocket (shouldn't happen in a perfect maze)
            return SearchResult(algorithm, None, extra={"steps": steps})
        heading = chosen
        dx, dy = DELTA[heading]
        x, y = x + dx, y + dy
        path.append((x, y))
        steps += 1
        if steps > max_steps:
            return SearchResult(algorithm, None, extra={"steps": steps})
    return SearchResult(algorithm, path, steps, 0, {"steps": steps})


# ---------------------------------------------------------- dead-end filling
def dead_end_filling(grid: Grid, start: Cell, goal: Cell) -> SearchResult:
    """Prune dead ends until only the start-goal corridor remains.

    Iteratively mark any cell whose *remaining* degree is 1 (except start and
    goal), removing it from the graph and decrementing its neighbors.  In a
    perfect maze what survives is exactly the unique start-goal path, which a
    final BFS then reads off.  A neat "solve by subtraction" demo.
    """
    if start == goal:
        return SearchResult("dead_end_filling", [start])
    w, h = grid.width, grid.height
    deg = [0] * (w * h)
    for y in range(h):
        for x in range(w):
            deg[y * w + x] = grid.degree(x, y)
    filled = bytearray(w * h)
    si = start[1] * w + start[0]
    gi = goal[1] * w + goal[0]
    stack = [i for i in range(w * h) if deg[i] == 1 and i != si and i != gi]
    filled_count = 0
    while stack:
        i = stack.pop()
        if filled[i] or i == si or i == gi:
            continue
        filled[i] = 1
        filled_count += 1
        x, y = i % w, i // w
        for d in DIRS:
            if grid.can_go(x, y, d):
                dx, dy = DELTA[d]
                j = (y + dy) * w + (x + dx)
                if not filled[j]:
                    deg[j] -= 1
                    if deg[j] == 1 and j != si and j != gi:
                        stack.append(j)
    # BFS restricted to unfilled cells; in a perfect maze this is a corridor.
    came: Dict[Cell, Optional[Cell]] = {start: None}
    q = deque([start])
    expanded = 0
    peak = 1
    while q:
        cur = q.popleft()
        expanded += 1
        if cur == goal:
            return SearchResult(
                "dead_end_filling", _reconstruct(came, start, goal), expanded, peak,
                {"filled": filled_count},
            )
        for nb in _neighbors(grid, cur):
            if nb not in came and not filled[nb[1] * w + nb[0]]:
                came[nb] = cur
                q.append(nb)
        peak = max(peak, len(q))
    return SearchResult(
        "dead_end_filling", None, expanded, peak, {"filled": filled_count}
    )


# ------------------------------------------------------------------ registry
SOLVERS: Dict[str, Callable] = {
    "bfs": bfs,
    "dfs": dfs,
    "dijkstra": dijkstra,
    "astar": astar,
    "greedy": greedy_best_first,
    "bidirectional": bidirectional_bfs,
    "wall_follower": wall_follower,
    "dead_end_filling": dead_end_filling,
}

SOLVER_LABELS: Dict[str, str] = {
    "bfs": "BFS",
    "dfs": "DFS",
    "dijkstra": "Dijkstra",
    "astar": "A* (Manhattan)",
    "greedy": "Greedy best-first",
    "bidirectional": "Bidirectional BFS",
    "wall_follower": "Wall follower",
    "dead_end_filling": "Dead-end filling",
}


def solve(grid: Grid, start: Cell, goal: Cell, algorithm: str = "astar", **kwargs) -> SearchResult:
    """Dispatch a solver by name.  Extra kwargs pass through (e.g. ``hand=``)."""
    try:
        fn = SOLVERS[algorithm]
    except KeyError:
        raise ValueError(
            f"unknown algorithm {algorithm!r}; choose from {sorted(SOLVERS)}"
        ) from None
    return fn(grid, start, goal, **kwargs)
