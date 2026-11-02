"""Benchmark memory usage (peak allocation) of generation & pathfinding.

Uses ``tracemalloc`` to measure peak bytes during each operation.  Note that
tracemalloc adds ~2-4x runtime overhead -- memory numbers only, never timing
numbers (those come from the other two benchmarks).

Results -> ``benchmarks/results/memory.csv``.
"""
from __future__ import annotations

import argparse
import csv
import sys
import tracemalloc
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maze import (
    GENERATOR_LABELS,
    astar,
    bfs,
    bidirectional_bfs,
    dead_end_filling,
    dfs,
    dijkstra,
    euclidean,
    generate,
    greedy_best_first,
    manhattan,
    wall_follower,
)

GEN_SIZES = [(31, 31), (63, 63), (127, 127)]
SOLVE_SIZES = [(63, 63), (127, 127)]
QUICK_GEN_SIZES = GEN_SIZES[:2]
QUICK_SOLVE_SIZES = SOLVE_SIZES[:1]


def measured(fn, *args, **kwargs):
    """Run ``fn`` under tracemalloc; return (result, steady_bytes, peak_bytes)."""
    tracemalloc.start()
    result = fn(*args, **kwargs)
    steady, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, steady, peak


def run(out_path: Path, quick: bool) -> None:
    rows = []
    gen_sizes = QUICK_GEN_SIZES if quick else GEN_SIZES
    solve_sizes = QUICK_SOLVE_SIZES if quick else SOLVE_SIZES

    # --- generation: steady-state = the grid itself; peak = grid + transients
    for method, label in GENERATOR_LABELS.items():
        for (w, h) in gen_sizes:
            grid, steady, peak = measured(generate, w, h, method=method, seed=99)
            assert grid.passage_count() == w * h - 1
            rows.append(
                {
                    "kind": "generation",
                    "name": method,
                    "label": label,
                    "w": w, "h": h, "cells": w * h,
                    "grid_bytes": w * h,
                    "steady_bytes": steady,
                    "peak_bytes": peak,
                }
            )
            print(f"gen   {label:>24} {w:>3}x{h:<3}: steady {steady:>9,} B | peak {peak:>10,} B")

    # --- solvers: peak = search structures (came_from dicts, queues, heaps)
    solvers = [
        ("bfs", "BFS", bfs),
        ("dfs", "DFS", dfs),
        ("dijkstra", "Dijkstra", dijkstra),
        ("astar", "A* (Manhattan)", astar),
        ("greedy", "Greedy best-first", greedy_best_first),
        ("bidirectional", "Bidirectional BFS", bidirectional_bfs),
        ("dead_end_filling", "Dead-end filling", dead_end_filling),
        ("wall_follower", "Wall follower", wall_follower),
    ]
    for (w, h) in solve_sizes:
        grid = generate(w, h, method="dfs", seed=42)
        start, goal = (0, 0), (w - 1, h - 1)
        for key, label, fn in solvers:
            res, steady, peak = measured(fn, grid, start, goal)
            rows.append(
                {
                    "kind": "solver",
                    "name": key,
                    "label": label,
                    "w": w, "h": h, "cells": w * h,
                    "grid_bytes": w * h,
                    "steady_bytes": steady,
                    "peak_bytes": peak,
                }
            )
            print(f"solve {label:>24} {w:>3}x{h:<3}: steady {steady:>9,} B | peak {peak:>10,} B "
                  f"| path {res.length}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="smaller size sweep")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = Path(args.out) if args.out else Path(__file__).parent / "results" / "memory.csv"
    run(out, quick=args.quick)


if __name__ == "__main__":
    main()
