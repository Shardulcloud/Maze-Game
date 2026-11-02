"""Rendering: maze surfaces, camera, entities, fog of war.

Key design points:

* The maze is rendered ONCE into a cached ``Surface`` (floor + all walls).
  Per-frame work is blits and a handful of shapes -- large mazes stay 60fps.
* Generation animation: instead of rebuilding the surface, events *paint over*
  it incrementally -- a carve paints floor over the removed wall's rect, an
  added wall paints a wall rect.  O(1) per event, no full redraws.
* The fog overlay is a world-sized SRCALPHA surface rebuilt ONLY when the
  underlying visibility state changes (a player's tile arrival), then blitted
  every frame.  pygame's draw functions write raw pixels (no blending), so
  "draw transparent rect" punches clean holes for visible cells.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence, Set, Tuple

import pygame

from game import config as C
from maze.grid import ALL_WALLS, Grid, N, E, S, W


# ------------------------------------------------------------ wall geometry
def wall_thickness(tile: int) -> int:
    return max(3, min(8, tile // 5))


def edge_rect(tile: int, x: int, y: int, d: int) -> Tuple[int, int, int, int]:
    """Pixel rect covering the shared edge between ``(x, y)`` and its
    neighbor in direction ``d`` (extended by half the wall thickness at both
    ends so corners join cleanly)."""
    t = wall_thickness(tile)
    t2 = t // 2
    if d == N:
        return (x * tile - t2, y * tile - t2, tile + t, t)
    if d == S:
        return (x * tile - t2, (y + 1) * tile - t2, tile + t, t)
    if d == W:
        return (x * tile - t2, y * tile - t2, t, tile + t)
    if d == E:
        return ((x + 1) * tile - t2, y * tile - t2, t, tile + t)
    raise ValueError(f"bad direction {d}")


# ------------------------------------------------------------- maze surface
def build_surface(grid: Grid, tile: int, initial: Optional[str] = None) -> pygame.Surface:
    """Draw the maze into a fresh surface.

    ``initial=None``  -- render the grid's *current* walls (final state).
    ``initial="walled"`` -- every wall present (start state for carve-based
                            generation animations).
    ``initial="open"``   -- open room, borders only (start state for
                            Recursive Division's wall-adding animation).
    """
    w, h = grid.width, grid.height
    surf = pygame.Surface((w * tile, h * tile))
    surf.fill(C.FLOOR)
    # Subtle cell-center dots: texture without touching shared edges, so
    # incremental event painting never fights them.
    if tile >= 12:
        dot = 2
        for y in range(h):
            for x in range(w):
                surf.fill(
                    C.GRID_DOT,
                    (x * tile + tile // 2 - 1, y * tile + tile // 2 - 1, dot, dot),
                )
    if initial == "walled":
        # Carve-based algorithms: start with EVERY wall present (rendered
        # explicitly -- the grid passed here is already fully generated).
        for y in range(h):
            for x in range(w):
                for d in (N, E, S, W):
                    surf.fill(C.WALL, edge_rect(tile, x, y, d))
    elif initial == "open":
        # Recursive Division: start with an open room, border walls only.
        for x in range(w):
            surf.fill(C.WALL, edge_rect(tile, x, 0, N))
            surf.fill(C.WALL, edge_rect(tile, x, h - 1, S))
        for y in range(h):
            surf.fill(C.WALL, edge_rect(tile, 0, y, W))
            surf.fill(C.WALL, edge_rect(tile, w - 1, y, E))
    else:
        # Final render: every currently-present wall.
        for y in range(h):
            for x in range(w):
                mask = grid.walls_at(x, y)
                for d in (N, E, S, W):
                    if mask & d:
                        surf.fill(C.WALL, edge_rect(tile, x, y, d))
    return surf


def paint_event(surf: pygame.Surface, tile: int, kind: str, x: int, y: int, d: int) -> None:
    """Incrementally apply one generation event to the cached surface."""
    color = C.FLOOR if kind == "carve" else C.WALL
    surf.fill(color, edge_rect(tile, x, y, d))


# ------------------------------------------------------------------ camera
class Camera:
    """Scrollable window onto the maze world (world units = pixels)."""

    def __init__(self, view_x: int, view_y: int, view_w: int, view_h: int,
                 world_w: int, world_h: int) -> None:
        self.view_x, self.view_y = view_x, view_y
        self.view_w, self.view_h = view_w, view_h
        self.world_w, self.world_h = world_w, world_h
        self.x = 0.0
        self.y = 0.0
        self.sx, self.sy = 0, 0  # screen shake offset (set by main each frame)

    def center_world(self) -> None:
        """Fit the whole maze in view (letterbox when smaller than the view)."""
        self.x = (self.world_w - self.view_w) / 2.0
        self.y = (self.world_h - self.view_h) / 2.0

    def center(self, wx: float, wy: float) -> None:
        """Follow a world point, clamped to maze bounds."""
        self.x = wx - self.view_w / 2.0
        self.y = wy - self.view_h / 2.0
        if self.world_w <= self.view_w:
            self.x = (self.world_w - self.view_w) / 2.0
        else:
            self.x = min(max(self.x, 0.0), self.world_w - self.view_w)
        if self.world_h <= self.view_h:
            self.y = (self.world_h - self.view_h) / 2.0
        else:
            self.y = min(max(self.y, 0.0), self.world_h - self.view_h)

    def blit_offset(self) -> Tuple[int, int]:
        """Top-left of the world as it lands on screen (shake included)."""
        return (
            int(self.view_x - self.x) + self.sx,
            int(self.view_y - self.y) + self.sy,
        )

    def to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        ox, oy = self.blit_offset()
        return int(wx) + ox, int(wy) + oy

    def blit(self, screen: pygame.Surface, surf: pygame.Surface) -> None:
        screen.blit(surf, self.blit_offset())


# -------------------------------------------------------------------- glow
def make_glow(radius: float, color, max_alpha: int = 70) -> pygame.Surface:
    """Precomputed radial glow sprite (SRCALPHA).  Built once per entity kind,
    blitted per frame -- no per-frame SRCALPHA construction."""
    R = max(4, int(radius * 2.2))
    surf = pygame.Surface((2 * R, 2 * R), pygame.SRCALPHA)
    r0 = int(radius * 0.6)
    for r in range(R, r0, -2):  # outside-in: inner rings overwrite outer
        a = int(max_alpha * (R - r) / max(1, R - r0))
        pygame.draw.circle(surf, (*color, a), (R, R), r)
    return surf


# ---------------------------------------------------------------- entities
def draw_player(screen: pygame.Surface, cam: Camera, player, tile: int,
                glow: pygame.Surface, offset: Tuple[float, float] = (0.0, 0.0)) -> None:
    """A player dot with glow, outline and a little specular highlight.

    ``offset`` (in tiles) visually separates players sharing one cell (race
    mode spawns both on the same tile).
    """
    wx = (player.rx + 0.5 + offset[0]) * tile
    wy = (player.ry + 0.5 + offset[1]) * tile
    sx, sy = cam.to_screen(wx, wy)
    screen.blit(glow, (sx - glow.get_width() // 2, sy - glow.get_height() // 2))
    r = max(4, int(tile * 0.30))
    pygame.draw.circle(screen, player.color, (sx, sy), r)
    outline = tuple(int(c * 0.45) for c in player.color)
    pygame.draw.circle(screen, outline, (sx, sy), r, max(1, tile // 18))
    hr = max(2, r // 3)
    pygame.draw.circle(screen, (245, 250, 255), (sx - r // 3, sy - r // 3), hr)


def draw_exit(screen: pygame.Surface, cam: Camera, exit_cell: Tuple[int, int],
              tile: int, t: float, glow: pygame.Surface) -> None:
    """Pulsing green portal: glow, breathing rings, orbiting sparks, core."""
    wx = (exit_cell[0] + 0.5) * tile
    wy = (exit_cell[1] + 0.5) * tile
    sx, sy = cam.to_screen(wx, wy)
    screen.blit(glow, (sx - glow.get_width() // 2, sy - glow.get_height() // 2))
    pulse = 0.5 + 0.5 * math.sin(t * 3.0)
    r1 = int(tile * 0.34 + pulse * 3)
    pygame.draw.circle(screen, C.EXIT, (sx, sy), r1, max(2, tile // 10))
    pygame.draw.circle(screen, C.EXIT, (sx, sy), max(3, int(tile * 0.13)))
    orbit = tile * 0.5
    for k in range(4):
        ang = t * 1.8 + k * math.pi / 2.0
        px = sx + int(orbit * math.cos(ang))
        py = sy + int(orbit * math.sin(ang))
        pygame.draw.circle(screen, C.EXIT, (px, py), max(2, tile // 14))


def draw_coin(screen: pygame.Surface, cam: Camera, cell: Tuple[int, int],
              tile: int, t: float, phase: float) -> None:
    """Rotating, wobbling golden diamond."""
    wx = (cell[0] + 0.5) * tile
    wy = (cell[1] + 0.5) * tile
    sx, sy = cam.to_screen(wx, wy)
    ang = t * 2.2 + phase
    r = tile * 0.20 * (0.8 + 0.2 * math.sin(t * 3.0 + phase))
    pts = []
    for k in range(4):
        a = ang + k * math.pi / 2.0
        pts.append((sx + r * math.cos(a), sy + r * math.sin(a)))
    pygame.draw.polygon(screen, C.COIN, pts)
    pygame.draw.polygon(
        screen, tuple(int(c * 0.55) for c in C.COIN), pts, 1
    )


def draw_hint_path(screen: pygame.Surface, cam: Camera, path: Sequence[Tuple[int, int]],
                   tile: int, t: float, frac_left: float) -> None:
    """A* hint: pulsing purple beads along the path.  Drawn ABOVE the fog --
    a hint is allowed to reveal the way through unexplored maze."""
    alpha = min(1.0, 2.0 * frac_left)  # fades out in the last half
    color = tuple(int(c * (0.35 + 0.65 * alpha)) for c in C.HINT)
    for i, (x, y) in enumerate(path):
        wx = (x + 0.5) * tile
        wy = (y + 0.5) * tile
        sx, sy = cam.to_screen(wx, wy)
        r = max(2, int(tile * 0.12) + int(1.5 * math.sin(t * 6.0 - i * 0.7)))
        pygame.draw.circle(screen, color, (sx, sy), r)


# --------------------------------------------------------------------- fog
class FogLayer:
    """Per-viewport fog overlay, rebuilt only when visibility state changes.

    World-sized SRCALPHA surface:
      * everything               -> near-opaque dark
      * explored cells           -> punched transparent, then dimmed
      * currently visible cells  -> punched transparent again (fully clear)
    Rebuild is O(visible + explored) rect fills on tile arrivals only;
    per-frame cost is a single blit.
    """

    def __init__(self, grid: Grid, tile: int) -> None:
        self.tile = tile  # cell size in px -- rebuild() needs it later
        self.surf = pygame.Surface((grid.width * tile, grid.height * tile),
                                   pygame.SRCALPHA)
        self._key: Optional[Tuple] = None

    def rebuild(self, explored: Optional[Set[Tuple]], visible: Optional[Set[Tuple]],
                key: Tuple) -> None:
        self._key = key
        t = self.tile
        self.surf.fill((*C.FOG_RGB, C.FOG_OPAQUE_A))
        if explored:
            for (x, y) in explored:
                self.surf.fill((0, 0, 0, 0), (x * t, y * t, t, t))
            if visible:
                for (x, y) in explored - visible:
                    self.surf.fill((*C.FOG_RGB, C.FOG_MEMORY_A),
                                   (x * t, y * t, t, t))
        if visible:
            for (x, y) in visible:
                self.surf.fill((0, 0, 0, 0), (x * t, y * t, t, t))

    def maybe_rebuild(self, key: Tuple, explored: Optional[Set[Tuple]],
                      visible: Optional[Set[Tuple]]) -> None:
        if key != self._key:
            self.rebuild(explored, visible, key)

    def draw(self, screen: pygame.Surface, cam: Camera) -> None:
        cam.blit(screen, self.surf)
