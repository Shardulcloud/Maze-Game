"""Player entity: grid-based movement with smooth interpolation.

Movement model: the player logically occupies one tile at a time; when a
direction key is held and no wall blocks the way, the player commits to the
neighboring tile and glides there at ``PLAYER_SPEED`` tiles/second.  On
arrival, the next held key is consumed in the same frame, so chained
movement feels continuous (Pac-Man style cornering).

``steps`` counts tile-to-tile moves (the post-game efficiency stat compares
this against A*'s optimal path length).  ``take_arrived()`` lets game modes
react exactly once per tile arrival (pickups, fog reveal, exit checks).
"""
from __future__ import annotations

from typing import Dict, Tuple

import pygame

from maze.grid import DELTA, DIRS, Grid, N, S, W, E  # noqa: F401 (E for key map)

K_WASD = {N: pygame.K_w, E: pygame.K_d, S: pygame.K_s, W: pygame.K_a}
K_ARROWS = {N: pygame.K_UP, E: pygame.K_RIGHT, S: pygame.K_DOWN, W: pygame.K_LEFT}


class Player:
    __slots__ = (
        "gx", "gy",        # logical tile
        "rx", "ry",        # render position in tile units (floats)
        "tx", "ty",        # committed move target (when moving)
        "dir",             # direction flag of the current move (or None)
        "keys", "color", "name",
        "speed", "score", "steps", "_arrived",
    )

    def __init__(
        self,
        x: int,
        y: int,
        color: Tuple[int, int, int],
        keys: Dict[int, int],
        name: str,
        speed: float = 8.0,
    ) -> None:
        self.gx, self.gy = x, y
        self.rx, self.ry = float(x), float(y)
        self.tx, self.ty = x, y
        self.dir = None
        self.keys = keys
        self.color = color
        self.name = name
        self.speed = speed
        self.score = 0
        self.steps = 0
        self._arrived = False

    # ---------------------------------------------------------------- state
    @property
    def tile(self) -> Tuple[int, int]:
        return self.gx, self.gy

    @property
    def arrived(self) -> bool:
        return self._arrived

    def take_arrived(self) -> bool:
        """Consume the 'just arrived at a new tile' flag (one-shot)."""
        was = self._arrived
        self._arrived = False
        return was

    def force_arrive(self) -> None:
        """Set the arrival flag without moving (used by the smoke test to
        fast-forward to game-over states)."""
        self._arrived = True

    def set_tile(self, x: int, y: int) -> None:
        """Teleport (keeps render position consistent)."""
        self.gx, self.gy = x, y
        self.rx, self.ry = float(x), float(y)
        self.tx, self.ty = x, y
        self.dir = None

    # --------------------------------------------------------------- update
    def update(self, dt: float, grid: Grid, keystate) -> None:
        """Advance one frame: finish any glide, then maybe commit a new move.

        ``keystate`` is anything indexable by pygame key constants
        (``pygame.key.get_pressed()`` in game, a plain dict in the smoke test).
        """
        if self.dir is not None:
            step = self.speed * dt
            dx = self.tx - self.rx
            dy = self.ty - self.ry
            if abs(dx) + abs(dy) <= step:
                # Snap to the target tile; same-frame chaining follows.
                self.rx, self.ry = float(self.tx), float(self.ty)
                self.gx, self.gy = self.tx, self.ty
                self.dir = None
                self.steps += 1
                self._arrived = True
            else:
                # Moves are axis-aligned: advance the single active axis.
                if dx > 0:
                    self.rx += step
                elif dx < 0:
                    self.rx -= step
                elif dy > 0:
                    self.ry += step
                elif dy < 0:
                    self.ry -= step
        if self.dir is None:
            for d in DIRS:
                if keystate[self.keys[d]] and grid.can_go(self.gx, self.gy, d):
                    dx, dy = DELTA[d]
                    self.dir = d
                    self.tx, self.ty = self.gx + dx, self.gy + dy
                    break

    def __repr__(self) -> str:
        return f"<Player {self.name} at {self.tile} score={self.score}>"
