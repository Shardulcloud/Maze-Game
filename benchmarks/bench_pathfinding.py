"""Benchmark pathfinding algorithms across maze sizes.

Each maze is generated once per size (DFS backtracker, fixed seed for
reproducibility), then every solver runs the same corner-to-corner search.
We record: median wall-clock time, nodes expanded, peak frontier size, path
length, and whether the path length matches BFS's optimum.

Results -> ``benchmarks/results/pathfinding.csv``.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
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

DEFAULT_SIZES = [(15, 15), (31, 31), (63, 63), (127, 127), (255, 255)]
QUICK_SIZES = DEFAULT_SIZES[:3]

BENCH_SOLVERS = [
    ("bfs", "BFS", bfs),
    ("dfs", "DFS", dfs),
    ("dijkstra", "Dijkstra", dijkstra),
    ("astar", "A* (Manhattan)", astar),
    ("astar_euclidean", "A* (Euclidean)", partial(astar, heuristic=euclidean)),
    ("greedy", "Greedy best-first", greedy_best_first),
    ("bidirectional", "Bidirectional BFS", bidirectional_bfs),
    ("dead_end_filling", "Dead-end filling", dead_end_filling),
    ("wall_follower", "Wall follower", wall_follower),
]


def run(sizes, repeats: int, gen_method: str, out_path: Path) -> None:
    rows = []
    for (w, h) in sizes:
        grid = generate(w, h, method=gen_method, seed=42)
        start, goal = (0, 0), (w - 1, h - 1)
        base = bfs(grid, start, goal)
        print(f"\nmaze {w}x{h} ({w*h} cells, {gen_method}), optimal path = {base.length} steps")
        for key, label, fn in BENCH_SOLVERS:
            times = []
            res = None
            for rep in range(repeats):
                t0 = time.perf_counter()
                res = fn(grid, start, goal)
                times.append((time.perf_counter() - t0) * 1000.0)
            assert res is not None and res.found, f"{label} failed on {w}x{h}"
            med = statistics.median(times)
            opt = res.length == base.length
            rows.append(
                {
                    "solver": key,
                    "label": label,
                    "w": w,
                    "h": h,
                    "cells": w * h,
                    "time_ms": round(med, 3),
                    "nodes_expanded": res.nodes_expanded,
                    "frontier_peak": res.frontier_peak,
                    "path_length": res.length,
                    "optimal": int(opt),
                }
            )
            print(
                f"  {label:>22}: {med:8.2f} ms | {res.nodes_expanded:>6} expanded "
                f"| peak {res.frontier_peak:>6} | path {res.length:>6} "
                f"{'(optimal)' if opt else '(longer)'}"
            )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="smaller size sweep")
    ap.add_argument(
        "--gen", default="dfs", choices=list(GENERATOR_LABELS),
        help="maze texture to solve on: 'dfs' = long snake corridors, "
             "'division' = rooms and open halls (search behaves very differently)",
    )
    ap.add_argument("--repeats", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    sizes = QUICK_SIZES if args.quick else DEFAULT_SIZES
    repeats = args.repeats or (3 if args.quick else 5)
    out = (
        Path(args.out) if args.out
        else Path(__file__).parent / "results" / f"pathfinding_{args.gen}.csv"
    )
    run(sizes, repeats, args.gen, out)


if __name__ == "__main__":
    main()
