"""maze -- maze generation & pathfinding algorithms.

Pure logic: no GUI dependencies.  The game, the tests, and the benchmarks all
import this package, which keeps the algorithms benchmarkable in isolation.

Quick tour::

    from maze import generate, astar

    grid = generate(31, 21, method="dfs", seed=42)
    result = astar(grid, (0, 0), (30, 20))
    print(result.path)
"""
from .grid import (  # noqa: F401
    ALL_WALLS,
    DELTA,
    DIRS,
    DIR_NAMES,
    E,
    Grid,
    N,
    OPPOSITE,
    S,
    W,
)
from .generators import (  # noqa: F401
    GENERATORS,
    GENERATOR_LABELS,
    dfs_backtracker,
    generate,
    initial_state,
    randomized_kruskal,
    randomized_prim,
    recursive_division,
    wilson,
)
from .pathfinding import (  # noqa: F401
    SOLVERS,
    SOLVER_LABELS,
    SearchResult,
    astar,
    bfs,
    bidirectional_bfs,
    dead_end_filling,
    dfs,
    dijkstra,
    euclidean,
    greedy_best_first,
    manhattan,
    solve,
    wall_follower,
)
from .rng import make_rng, random_seed  # noqa: F401

__version__ = "1.0.0"
