"""The maze grid.

Each cell stores a 4-bit wall mask using the cardinal directions
``N, E, S, W``.  A set bit means "wall present" in that direction; a cleared
bit means "passage open".  ``carve`` and ``add_wall`` keep both sides of every
shared edge consistent, so the mask is symmetric: cell ``(x, y)`` having its
``E`` wall cleared implies ``(x+1, y)`` has its ``W`` wall cleared, and vice
versa.

Border walls (the outermost edges of the maze) are always present.  This makes
movement / visibility queries uniform -- an out-of-bounds move is simply "a
wall is there".
"""
from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Tuple

# Direction bit flags.
N, E, S, W = 1, 2, 4, 8
ALL_WALLS = N | E | S | W

# Canonical iteration order (clockwise starting at North).  Stable ordering
# matters for the wall-follower pathfinding algorithm, which rotates through
# the headings using this order.
DIRS: Tuple[int, ...] = (N, E, S, W)

DIR_NAMES: Dict[int, str] = {N: "N", E: "E", S: "S", W: "W"}

# Tile offset produced by stepping one cell in each direction.  Screen +y points
# downward, so North decreases y.
DELTA: Dict[int, Tuple[int, int]] = {
    N: (0, -1),
    E: (1, 0),
    S: (0, 1),
    W: (-1, 0),
}

# The wall a cell faces on the opposite side of a shared edge.
OPPOSITE: Dict[int, int] = {N: S, S: N, E: W, W: E}


class Grid:
    """A rectangular maze backed by a flat ``bytearray`` of wall masks."""

    __slots__ = ("width", "height", "walls")

    def __init__(self, width: int, height: int, walls_mode: str = "all") -> None:
        if width < 1 or height < 1:
            raise ValueError("grid must be at least 1x1")
        self.width = width
        self.height = height
        n = width * height
        if walls_mode == "all":
            # Every wall present, including the borders.  Carving-based
            # generators start here and remove walls.
            self.walls = bytearray([ALL_WALLS]) * n
        elif walls_mode == "open":
            # Only border walls present.  Recursive Division starts here and
            # *adds* interior walls while carving exactly one passage per cut.
            self.walls = bytearray(n)
            self._add_borders()
        else:
            raise ValueError(f"unknown walls_mode {walls_mode!r}")

    # ------------------------------------------------------------------ basic
    @property
    def cell_count(self) -> int:
        return self.width * self.height

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def index(self, x: int, y: int) -> int:
        return y * self.width + x

    def cell_at(self, i: int) -> Tuple[int, int]:
        return i % self.width, i // self.width

    def _add_borders(self) -> None:
        w, h = self.width, self.height
        for x in range(w):
            self.walls[x] |= N                       # top edge
            self.walls[(h - 1) * w + x] |= S        # bottom edge
        for y in range(h):
            self.walls[y * w] |= W                  # left edge
            self.walls[y * w + w - 1] |= E          # right edge

    # -------------------------------------------------------------- wall ops
    def walls_at(self, x: int, y: int) -> int:
        return self.walls[y * self.width + x]

    def has_wall(self, x: int, y: int, d: int) -> bool:
        return bool(self.walls[y * self.width + x] & d)

    def neighbor(self, x: int, y: int, d: int) -> Tuple[int, int]:
        dx, dy = DELTA[d]
        return x + dx, y + dy

    def can_go(self, x: int, y: int, d: int) -> bool:
        """True if a one-cell move in direction ``d`` from ``(x, y)`` is legal.

        Legal means: the neighbor is in bounds AND no wall blocks the passage.
        The border-wall invariant guarantees out-of-bounds moves report a wall,
        so the bounds check is technically redundant for properly-initialized
        grids -- we keep it as a defensive safety net.
        """
        dx, dy = DELTA[d]
        nx, ny = x + dx, y + dy
        if not (0 <= nx < self.width and 0 <= ny < self.height):
            return False
        return not (self.walls[y * self.width + x] & d)

    def carve(self, x: int, y: int, d: int) -> None:
        """Remove the wall between ``(x, y)`` and its neighbor in direction ``d``.

        Raises if the neighbor would be out of bounds -- carving into the
        border is a bug in the caller, not a normal operation.
        """
        dx, dy = DELTA[d]
        nx, ny = x + dx, y + dy
        if not (0 <= nx < self.width and 0 <= ny < self.height):
            raise ValueError(f"cannot carve {d} from ({x},{y}): neighbor out of bounds")
        i = y * self.width + x
        j = ny * self.width + nx
        self.walls[i] &= ~d & 0x0F
        self.walls[j] &= ~OPPOSITE[d] & 0x0F

    def add_wall(self, x: int, y: int, d: int) -> None:
        """The symmetric counterpart of ``carve``: add a wall on a shared edge."""
        dx, dy = DELTA[d]
        nx, ny = x + dx, y + dy
        if not (0 <= nx < self.width and 0 <= ny < self.height):
            raise ValueError(f"cannot add wall {d} from ({x},{y}): neighbor out of bounds")
        i = y * self.width + x
        j = ny * self.width + nx
        self.walls[i] |= d
        self.walls[j] |= OPPOSITE[d]

    # ------------------------------------------------------------ navigation
    def open_dirs(self, x: int, y: int) -> List[int]:
        """Direction flags whose passages are open from ``(x, y)``."""
        mask = self.walls[y * self.width + x]
        return [d for d in DIRS if not (mask & d)]

    def open_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        out: List[Tuple[int, int]] = []
        for d in DIRS:
            if self.can_go(x, y, d):
                dx, dy = DELTA[d]
                out.append((x + dx, y + dy))
        return out

    def degree(self, x: int, y: int) -> int:
        mask = self.walls[y * self.width + x]
        return sum(1 for d in DIRS if not (mask & d))

    def passage_count(self) -> int:
        """Number of open passages (edges) in the grid.

        Each open passage is shared by exactly two cells, so we count cleared
        bits across all cells and divide by two.  A *perfect* maze over ``n``
        cells has exactly ``n - 1`` passages (a spanning tree).
        """
        total = 0
        for i in range(self.cell_count):
            total += bin(self.walls[i] & ALL_WALLS).count("1")
        open_bits = self.cell_count * 4 - total
        return open_bits // 2

    def cells_iter(self) -> Iterator[Tuple[int, int]]:
        for y in range(self.height):
            for x in range(self.width):
                yield x, y

    # ----------------------------------------------------------------- ASCII
    def to_ascii(
        self,
        path: Optional[List[Tuple[int, int]]] = None,
        markers: Optional[Dict[Tuple[int, int], str]] = None,
    ) -> str:
        """Render the maze as ASCII art.

        ``path`` cells are marked with ``*``; ``markers`` lets a caller stamp
        single characters (e.g. ``S`` / ``G``) on specific cells.  Useful for
        debugging without a window, and for the README's text examples.
        """
        pathset = set(path) if path else set()
        markers = markers or {}
        lines: List[str] = []
        for y in range(self.height):
            top = ""
            for x in range(self.width):
                top += "+"
                top += "--" if self.has_wall(x, y, N) else "  "
            top += "+"
            lines.append(top)
            mid = ""
            for x in range(self.width):
                mid += "|" if self.has_wall(x, y, W) else " "
                cell = " "
                if (x, y) in markers:
                    cell = markers[(x, y)]
                elif (x, y) in pathset:
                    cell = "*"
                mid += cell + " "
            mid += "|" if self.has_wall(self.width - 1, y, E) else " "
            lines.append(mid)
        bottom = "+"
        for x in range(self.width):
            bottom += "--" if self.has_wall(x, self.height - 1, S) else "  "
            bottom += "+"
        lines.append(bottom)
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Grid({self.width}x{self.height}, passages={self.passage_count()})"
