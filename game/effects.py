"""Juice: particles, screen shake, and the generation animation replay."""
from __future__ import annotations

import math
import random
from typing import Callable, List, Optional, Sequence, Tuple


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "damp", "grav")

    def __init__(self, x, y, vx, vy, life, color, size, damp, grav) -> None:
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.damp = damp
        self.grav = grav


class ParticleSystem:
    """World-space particle pool (cell pixels, not screen pixels).

    A fixed allocation-free update loop; bursts are small so a Python list of
    a few hundred slots keeps 60fps comfortably.
    """

    def __init__(self) -> None:
        self.parts: List[Particle] = []
        self._rng = random.Random()

    def burst(
        self,
        x: float,
        y: float,
        color,
        n: int = 14,
        speed: float = 90.0,
        life: float = 0.6,
        size: float = 3.5,
        damp: float = 3.0,
        grav: float = 0.0,
    ) -> None:
        rng = self._rng
        for i in range(n):
            ang = i / n * 2.0 * math.pi + rng.uniform(-0.3, 0.3)
            v = speed * rng.uniform(0.35, 1.0)
            self.parts.append(
                Particle(
                    x, y,
                    math.cos(ang) * v, math.sin(ang) * v,
                    life * rng.uniform(0.6, 1.2),
                    color,
                    size * rng.uniform(0.7, 1.4),
                    damp, grav,
                )
            )

    def confetti(self, x: float, y: float, colors: Sequence, n: int = 60) -> None:
        rng = self._rng
        for _ in range(n):
            ang = rng.uniform(0, 2.0 * math.pi)
            v = rng.uniform(40, 220)
            self.parts.append(
                Particle(
                    x, y,
                    math.cos(ang) * v, math.sin(ang) * v - 60,
                    rng.uniform(0.8, 1.6),
                    colors[rng.randrange(len(colors))],
                    rng.uniform(2.5, 5.0),
                    1.2, 260.0,   # light gravity for falling confetti
                )
            )

    def update(self, dt: float) -> None:
        alive: List[Particle] = []
        for p in self.parts:
            p.life -= dt
            if p.life <= 0:
                continue
            damp = math.exp(-p.damp * dt)
            p.vx *= damp
            p.vy = p.vy * damp + p.grav * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self.parts = alive

    def draw(self, screen, cam) -> None:
        for p in self.parts:
            frac = p.life / p.max_life
            r = max(1, int(p.size * (0.4 + 0.6 * frac)))
            sx, sy = cam.to_screen(p.x, p.y)
            screen.fill(p.color, (sx, sy, r, r))


class ScreenShake:
    """Exponential-decay trauma shake; renderer queries ``offset()`` per frame."""

    def __init__(self) -> None:
        self.mag = 0.0
        self._rng = random.Random()

    def add(self, magnitude: float) -> None:
        self.mag = min(14.0, self.mag + magnitude)

    def update(self, dt: float) -> None:
        self.mag *= math.exp(-6.0 * dt)
        if self.mag < 0.05:
            self.mag = 0.0

    def offset(self) -> Tuple[int, int]:
        if self.mag <= 0:
            return 0, 0
        rng = self._rng
        return (
            int(rng.uniform(-self.mag, self.mag)),
            int(rng.uniform(-self.mag, self.mag)),
        )


class Effects:
    """Facade bundling particles + screen shake; this is what modes receive."""

    def __init__(self) -> None:
        self.parts = ParticleSystem()
        self.shake = ScreenShake()

    def burst(self, *args, **kwargs) -> None:
        self.parts.burst(*args, **kwargs)

    def confetti(self, *args, **kwargs) -> None:
        self.parts.confetti(*args, **kwargs)

    def shake_add(self, magnitude: float) -> None:
        self.shake.add(magnitude)

    def update(self, dt: float) -> None:
        self.parts.update(dt)
        self.shake.update(dt)


class GenerationAnimation:
    """Replays recorded carve/wall events as a live "algorithm at work" show.

    ``events`` is a list of ``(kind, x, y, d)`` tuples captured by the
    ``on_carve`` / ``on_wall`` callbacks during generation.  ``apply_event``
    paints one event onto the maze surface; we pace the replay so it finishes
    in roughly ``duration`` seconds regardless of maze size (speed floor of
    30 events/sec so tiny mazes still feel animated).
    """

    def __init__(self, events: Sequence[Tuple], duration: float = 3.0) -> None:
        self.events = list(events)
        self.i = 0
        self._acc = 0.0
        self.rate = max(30.0, len(self.events) / max(duration, 0.001))

    def update(self, dt: float, apply_event: Callable) -> None:
        self._acc += self.rate * dt
        n = int(self._acc)
        self._acc -= n
        events = self.events
        while n > 0 and self.i < len(events):
            kind, x, y, d = events[self.i]
            apply_event(kind, x, y, d)
            self.i += 1
            n -= 1

    def skip(self, apply_event: Callable) -> None:
        while self.i < len(self.events):
            kind, x, y, d = self.events[self.i]
            apply_event(kind, x, y, d)
            self.i += 1

    @property
    def done(self) -> bool:
        return self.i >= len(self.events)

    @property
    def progress(self) -> float:
        return self.i / max(1, len(self.events))
