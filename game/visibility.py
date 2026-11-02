"""Line-of-sight visibility for fog of war.

``line_of_sight`` traces a ray between two cell centers using the
Amanatides & Woo grid traversal (constant-time stepping from one crossed
cell to the next) and checks the wall on each crossed edge.  Exact corner
crossings need an open "L" around the corner in either direction -- the
usual corner-cutting rule.

``visible_cells`` collects everything within a radius that is in line of
sight (a circle of cells, not a square, so fog looks round).  ``explore``
accumulates it into a player's explored set.
"""
from __future__ import annotations

from typing import Set

from maze.grid import DELTA, Grid


def line_of_sight(grid: Grid, x0: int, y0: int, x1: int, y1: int) -> bool:
    """True if a straight ray from the center of ``(x0,y0)`` to the center of
    ``(x1,y1)`` crosses no wall (with the corner rule at exact corners)."""
    if (x0, y0) == (x1, y1):
        return True
    # Ray endpoints: cell centers.
    px, py = x0 + 0.5, y0 + 0.5
    dx = (x1 + 0.5) - px
    dy = (y1 + 0.5) - py
    stepx = 1 if dx > 0 else -1
    stepy = 1 if dy > 0 else -1
    tdx = abs(1.0 / dx) if dx != 0 else float("inf")
    tdy = abs(1.0 / dy) if dy != 0 else float("inf")
    # t-values at which the ray first crosses a vertical / horizontal edge.
    if dx > 0:
        tx = (x0 + 1 - px) / dx
    elif dx < 0:
        tx = (x0 - px) / dx
    else:
        tx = float("inf")
    if dy > 0:
        ty = (y0 + 1 - py) / dy
    elif dy < 0:
        ty = (y0 - py) / dy
    else:
        ty = float("inf")
    # Direction bits for the edges we may cross.
    east, west, south, north = 2, 8, 4, 1
    cx, cy = x0, y0
    while (cx, cy) != (x1, y1):
        if tx < ty:
            d = east if stepx > 0 else west
            if grid.has_wall(cx, cy, d):
                return False
            cx += stepx
            tx += tdx
        elif ty < tx:
            d = south if stepy > 0 else north
            if grid.has_wall(cx, cy, d):
                return False
            cy += stepy
            ty += tdy
        else:
            # Exact corner: need an open L around it in either direction.
            dxe = east if stepx > 0 else west
            dye = south if stepy > 0 else north
            via_horiz = (
                not grid.has_wall(cx, cy, dxe)
                and not grid.has_wall(cx + stepx, cy, dye)
            )
            via_vert = (
                not grid.has_wall(cx, cy, dye)
                and not grid.has_wall(cx, cy + stepy, dxe)
            )
            if not (via_horiz or via_vert):
                return False
            cx += stepx
            cy += stepy
            tx += tdx
            ty += tdy
    return True


def visible_cells(grid: Grid, x: int, y: int, radius: float) -> Set[tuple]:
    """Cells within ``radius`` (Euclidean, in tiles) and in line of sight."""
    out = {(x, y)}
    r2 = radius * radius + 1e-9
    ri = int(radius) + 1
    for oy in range(-ri, ri + 1):
        for ox in range(-ri, ri + 1):
            if ox == 0 and oy == 0:
                continue
            tx, ty = x + ox, y + oy
            if not (0 <= tx < grid.width and 0 <= ty < grid.height):
                continue
            if ox * ox + oy * oy > r2:
                continue
            if line_of_sight(grid, x, y, tx, ty):
                out.add((tx, ty))
    return out


def explore(grid: Grid, explored: Set[tuple], x: int, y: int, radius: float) -> None:
    """Accumulate currently-visible cells into ``explored`` (in place)."""
    explored.update(visible_cells(grid, x, y, radius))
