"""Benchmark maze generation algorithms across maze sizes.

For every (algorithm, size): run several repeats with different seeds,
take the median wall-clock time, and sanity-assert each run produced a
perfect maze.  Results go to ``benchmarks/results/generation.csv``.

Usage:
    python benchmarks/bench_generation.py            # full sweep
    python benchmarks/bench_generation.py --quick  # smaller sweep
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maze import GENERATOR_LABELS, generate

DEFAULT_SIZES = [(15, 15), (31, 31), (63, 63), (127, 127), (255, 255)]
QUICK_SIZES = DEFAULT_SIZES[:3]

# Wilson's random walks scale poorly (that IS the benchmark finding); cap it
# so the full sweep finishes in reasonable time and note it in the output.
WILSON_MAX_CELLS = 127 * 127


def run(sizes, repeats: int, out_path: Path) -> list:
    rows = []
    for method, label in GENERATOR_LABELS.items():
        for (w, h) in sizes:
            if method == "wilson" and w * h > WILSON_MAX_CELLS:
                print(f"{label:>24} {w}x{h}: skipped (slow random walks; see README)")
                continue
            times = []
            passages = 0
            for rep in range(repeats):
                seed = 1000 + rep
                t0 = time.perf_counter()
                grid = generate(w, h, method=method, seed=seed)
                times.append((time.perf_counter() - t0) * 1000.0)
                passages = grid.passage_count()
                assert passages == w * h - 1, "not a perfect maze!"
            med = statistics.median(times)
            rows.append(
                {
                    "method": method,
                    "label": label,
                    "w": w,
                    "h": h,
                    "cells": w * h,
                    "passages": passages,
                    "time_ms": round(med, 3),
                    "repeats": repeats,
                }
            )
            print(f"{label:>24} {w:>3}x{h:<3} {w*h:>6} cells: {med:10.2f} ms (median of {repeats})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {out_path}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="smaller size sweep")
    ap.add_argument("--repeats", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    sizes = QUICK_SIZES if args.quick else DEFAULT_SIZES
    repeats = args.repeats or (3 if args.quick else 5)
    out = Path(args.out) if args.out else Path(__file__).parent / "results" / "generation.csv"
    run(sizes, repeats, out)


if __name__ == "__main__":
    main()
