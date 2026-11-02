"""Maze generation algorithms.

Five classic algorithms, all producing *perfect* mazes (spanning trees: every
cell reachable from every other cell, exactly one path between any pair):

* ``dfs``          -- DFS backtracker (iterative). Deep, winding corridors.
* ``prim``         -- Randomized Prim. Short, bushy branches, many dead ends.
* ``kruskal``      -- Randomized Kruskal (union-find). Even texture.
* ``wilson``       -- Wilson's algorithm. Samples spanning trees *uniformly*.
* ``division``     -- Recursive Division. Starts from an open room and adds
                      walls (each cut leaves exactly one passage).

Every generator shares one contract::

    fn(grid, rng, on_carve=None, on_wall=None) -> None

They mutate ``grid`` in place.  ``on_carve(x, y, d)`` fires whenever a wall is
removed between ``(x, y)`` and its neighbor in direction ``d``;
``on_wall(x, y, d)`` fires when one is added (only Recursive Division adds
walls).  The game uses these callbacks to record events and replay them as a
live "watch the algorithm build the maze" animation; benchmarks pass nothing
and pay no recording cost.

``generate(...)`` is the public factory: it builds the grid in the right
initial state for the chosen algorithm (all walls vs. open room), seeds the
RNG, and runs the generator.
"""
from __future__ import annotations

import random
from typing import Callable, Dict, List, Optional, Tuple

from .grid import DELTA, DIRS, E, N, S, W, Grid

# (generator function, grid initialization mode)
GENERATORS: Dict[str, Tuple[Callable, str]] = {}

GENERATOR_LABELS: Dict[str, str] = {
    "dfs": "DFS Backtracker",
    "prim": "Randomized Prim",
    "kruskal": "Randomized Kruskal",
    "wilson": "Wilson's (uniform)",
    "division": "Recursive Division",
}


class _DSU:
    """Disjoint-set (union-find) with path compression + union by rank.

    Used by Randomized Kruskal to detect which candidate passages would close
    a cycle.  Kept tiny and allocation-light on purpose -- it runs in the
    generation hot loop.
    """

    __slots__ = ("parent", "rank")

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = bytearray(n)

    def find(self, x: int) -> int:
        parent = self.parent
        root = x
        while parent[root] != root:
            root = parent[root]
        # Path compression: re-point everything we walked through at root.
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(self, a: int, b: int) -> bool:
        """Merge the sets containing ``a`` and ``b``.

        Returns True if they were separate (i.e. this edge joins two trees and
        must be carved), False if they were already connected (carving it
        would create a cycle / loop in the maze).
        """
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True


# --------------------------------------------------------------------- DFS
def dfs_backtracker(
    grid: Grid,
    rng: random.Random,
    on_carve: Optional[Callable] = None,
    on_wall: Optional[Callable] = None,
) -> None:
    """Iterative depth-first backtracker.

    Walk from a random cell, always carving into an *unvisited* neighbor and
    backtracking at dead ends.  Produces long twisting corridors with a low
    branching factor -- the classic "hard to navigate" texture.

    Iterative with an explicit stack rather than recursive: Python's default
    recursion limit (1000) is easily blown by a 255x255 maze, and function-call
    overhead dominates in benchmarks.
    """
    w, h = grid.width, grid.height
    visited = bytearray(w * h)
    start = rng.randrange(w * h)
    sx, sy = start % w, start // w
    visited[start] = 1
    stack: List[Tuple[int, int]] = [(sx, sy)]
    while stack:
        x, y = stack[-1]
        options = []
        for d in DIRS:
            dx, dy = DELTA[d]
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny * w + nx]:
                options.append(d)
        if not options:
            stack.pop()
            continue
        d = options[rng.randrange(len(options))]
        grid.carve(x, y, d)
        if on_carve is not None:
            on_carve(x, y, d)
        dx, dy = DELTA[d]
        nx, ny = x + dx, y + dy
        visited[ny * w + nx] = 1
        stack.append((nx, ny))


GENERATORS["dfs"] = (dfs_backtracker, "all")


# -------------------------------------------------------------------- Prim
def randomized_prim(
    grid: Grid,
    rng: random.Random,
    on_carve: Optional[Callable] = None,
    on_wall: Optional[Callable] = None,
) -> None:
    """"Modified" randomized Prim on the cell graph.

    Maintain a frontier of cells adjacent to the growing maze.  Repeatedly
    pick a random frontier cell and connect it to a random *already-visited*
    neighbor.  Texture: short corridors, many dead ends -- feels "bushy"
    compared to the DFS backtracker.
    """
    w, h = grid.width, grid.height
    visited = bytearray(w * h)
    i = rng.randrange(w * h)
    x, y = i % w, i // w
    visited[i] = 1
    frontier: List[Tuple[int, int]] = []

    def push_frontier(cx: int, cy: int) -> None:
        for d in DIRS:
            dx, dy = DELTA[d]
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny * w + nx]:
                frontier.append((nx, ny))

    push_frontier(x, y)
    while frontier:
        # Swap-pop a uniformly random frontier cell (O(1) removal).
        k = rng.randrange(len(frontier))
        frontier[k], frontier[-1] = frontier[-1], frontier[k]
        x, y = frontier.pop()
        if visited[y * w + x]:
            continue  # duplicate frontier entry
        # Connect to a random visited neighbor.
        cands = []
        for d in DIRS:
            dx, dy = DELTA[d]
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and visited[ny * w + nx]:
                cands.append(d)
        d = cands[rng.randrange(len(cands))]
        grid.carve(x, y, d)
        if on_carve is not None:
            on_carve(x, y, d)
        visited[y * w + x] = 1
        push_frontier(x, y)


GENERATORS["prim"] = (randomized_prim, "all")


# ----------------------------------------------------------------- Kruskal
def randomized_kruskal(
    grid: Grid,
    rng: random.Random,
    on_carve: Optional[Callable] = None,
    on_wall: Optional[Callable] = None,
) -> None:
    """Randomized Kruskal.

    List every interior wall as a candidate passage, shuffle, then carve each
    candidate whose endpoints live in different union-find components.  The
    result is a minimum spanning tree under a random weight order -- an
    unbiased "even texture" maze with no long-range structure.
    """
    w, h = grid.width, grid.height
    edges: List[Tuple[int, int, int]] = []
    for y in range(h):
        for x in range(w):
            if x + 1 < w:
                edges.append((x, y, E))
            if y + 1 < h:
                edges.append((x, y, S))
    rng.shuffle(edges)
    dsu = _DSU(w * h)
    for x, y, d in edges:
        dx, dy = DELTA[d]
        a = y * w + x
        b = (y + dy) * w + (x + dx)
        if dsu.union(a, b):
            grid.carve(x, y, d)
            if on_carve is not None:
                on_carve(x, y, d)


GENERATORS["kruskal"] = (randomized_kruskal, "all")


# ------------------------------------------------------------------ Wilson
def wilson(
    grid: Grid,
    rng: random.Random,
    on_carve: Optional[Callable] = None,
    on_wall: Optional[Callable] = None,
) -> None:
    """Wilson's algorithm (loop-erased random walks).

    Repeatedly: pick an unvisited cell, random-walk until the walk stumbles
    into the visited set, then *replay* the loop-erased walk, carving it.
    The loop erasure falls out naturally by storing one outgoing direction per
    cell in a dict -- a revisit simply overwrites the earlier choice, slicing
    the loop off the walk.

    Why bother?  Wilson's is the only algorithm here that samples spanning
    trees *uniformly* at random -- no structural bias at all.  The price is
    speed: early random walks can wander a long time before hitting the
    visited set (visible in the generation benchmarks).
    """
    w, h = grid.width, grid.height
    n = w * h
    # In-bounds directions per cell, precomputed once.
    valid: List[List[int]] = []
    for y in range(h):
        for x in range(w):
            valid.append(
                [d for d in DIRS if grid.in_bounds(x + DELTA[d][0], y + DELTA[d][1])]
            )
    visited = bytearray(n)
    i0 = rng.randrange(n)
    visited[i0] = 1
    remaining = n - 1
    while remaining:
        # Pick a random unvisited cell to start a walk from.
        while True:
            i = rng.randrange(n)
            if not visited[i]:
                break
        # Random walk (through walls are irrelevant here: we walk the full
        # lattice) until we hit a visited cell, recording one step per cell.
        walk_dir: Dict[int, int] = {}
        cur = i
        while not visited[cur]:
            opts = valid[cur]
            d = opts[rng.randrange(len(opts))]
            walk_dir[cur] = d
            x, y = cur % w, cur // w
            dx, dy = DELTA[d]
            cur = (y + dy) * w + (x + dx)
        # Replay the (loop-erased) walk, carving it into the maze.
        cur = i
        while not visited[cur]:
            d = walk_dir[cur]
            x, y = cur % w, cur // w
            grid.carve(x, y, d)
            if on_carve is not None:
                on_carve(x, y, d)
            visited[cur] = 1
            remaining -= 1
            dx, dy = DELTA[d]
            cur = (y + dy) * w + (x + dx)


GENERATORS["wilson"] = (wilson, "all")


# ------------------------------------------------------ Recursive Division
def recursive_division(
    grid: Grid,
    rng: random.Random,
    on_carve: Optional[Callable] = None,
    on_wall: Optional[Callable] = None,
) -> None:
    """Recursive Division.

    Inverted strategy: the grid starts as one open room (only border walls),
    and each recursive step adds a wall across the longer axis with a single
    random passage, then recurses into both halves.  Heavy on long straight
    corridors and rectangular rooms -- very different texture from the
    tree-growing algorithms.

    NOTE: requires a grid built with ``walls_mode="open"``; ``generate()``
    takes care of this.  Emits ``on_wall`` events instead of ``on_carve``.
    """
    w, h = grid.width, grid.height

    def add(x: int, y: int, d: int) -> None:
        grid.add_wall(x, y, d)
        if on_wall is not None:
            on_wall(x, y, d)

    def divide(x0: int, y0: int, x1: int, y1: int) -> None:
        rw = x1 - x0 + 1
        rh = y1 - y0 + 1
        if rw < 2 and rh < 2:
            return
        if rw >= 2 and rh >= 2:
            # Divide across the longer axis; coin flip on a square.
            horizontal = (rh > rw) if rw != rh else rng.random() < 0.5
        else:
            horizontal = rh >= 2
        if horizontal:
            # Horizontal wall below row yc, with a passage at column px.
            yc = y0 + rng.randrange(rh - 1)
            px = x0 + rng.randrange(rw)
            for x in range(x0, x1 + 1):
                if x != px:
                    add(x, yc, S)
            divide(x0, y0, x1, yc)
            divide(x0, yc + 1, x1, y1)
        else:
            # Vertical wall right of column xc, with a passage at row py.
            xc = x0 + rng.randrange(rw - 1)
            py = y0 + rng.randrange(rh)
            for y in range(y0, y1 + 1):
                if y != py:
                    add(xc, y, E)
            divide(x0, y0, xc, y1)
            divide(xc + 1, y0, x1, y1)

    divide(0, 0, w - 1, h - 1)


GENERATORS["division"] = (recursive_division, "open")


# ------------------------------------------------------------------ factory
def generate(
    width: int,
    height: int,
    method: str = "dfs",
    seed: Optional[int] = None,
    on_carve: Optional[Callable] = None,
    on_wall: Optional[Callable] = None,
) -> Grid:
    """Build a ``width x height`` maze with ``method`` and an optional seed.

    Raises ``ValueError`` for an unknown method name (the message lists the
    valid ones, which keeps CLI users happy).
    """
    try:
        fn, mode = GENERATORS[method]
    except KeyError:
        raise ValueError(
            f"unknown generation method {method!r}; choose from {sorted(GENERATORS)}"
        ) from None
    grid = Grid(width, height, mode)
    rng = random.Random(seed)
    fn(grid, rng, on_carve=on_carve, on_wall=on_wall)
    return grid


def initial_state(method: str) -> str:
    """Visual starting state for animating ``method``: 'walled' or 'open'.

    Carve-based generators begin with every wall present and remove them one
    by one; Recursive Division begins with an open room and adds walls.  The
    game renderer asks this before replaying generation events.
    """
    return "walled" if GENERATORS[method][1] == "all" else "open"
