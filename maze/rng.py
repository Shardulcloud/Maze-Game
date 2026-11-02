"""Seeded random utilities.

Keeping RNG creation in one place makes it easy to swap implementations later
and ensures every algorithm uses the same reproducibility contract: the same
seed always produces the same maze.
"""
from __future__ import annotations

import random
from typing import Optional


def make_rng(seed: Optional[int] = None) -> random.Random:
    """Return a fresh ``random.Random`` instance.

    Passing ``None`` (or omitting the argument) yields a randomly-seeded
    generator, which is what we want when the player picks "random seed" in
    the menu.  Passing an integer makes generation fully reproducible, which
    is what benchmarks and tests rely on.
    """
    return random.Random(seed)


def random_seed() -> int:
    """A 32-bit random seed suitable for display and reproduction."""
    return random.randrange(1 << 31)
