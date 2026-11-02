"""Turn benchmark CSVs into charts (matplotlib, Agg backend -- no display).

Produces in ``benchmarks/results/``:
    generation_time.png     -- median generation time vs maze size (log-log)
    pathfinding_time.png    -- median solve time vs maze size (log-log)
    nodes_expanded.png      -- nodes expanded vs maze size
    memory_peak.png         -- peak allocation vs maze size

and prints summary tables to stdout.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maze import GENERATOR_LABELS  # texture names -> nice labels

RESULTS = Path(__file__).parent / "results"


def read_csv(name: str):
    path = RESULTS / name
    if not path.exists():
        print(f"missing {path} -- run the benchmarks first")
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def series(rows, key_field: str, x_field: str, y_field: str):
    """Group rows -> {key: sorted [(x, y)]}."""
    out = defaultdict(list)
    for r in rows:
        out[r[key_field]].append((int(r[x_field]), float(r[y_field])))
    for k in out:
        out[k].sort()
    return dict(out)


def plot(series_map, title, xlabel, ylabel, out_name, loglog=True):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for key, pts in series_map.items():
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, marker="o", linewidth=1.8, markersize=5, label=key)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", linestyle=":", linewidth=0.6, alpha=0.7)
    if loglog:
        ax.set_xscale("log")
        ax.set_yscale("log")
    ax.legend(fontsize=9, loc="best")
    fig.tight_layout()
    out = RESULTS / out_name
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"wrote {out}")


def main() -> None:
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("matplotlib is required for plots: pip install matplotlib")
        sys.exit(1)

    gen = read_csv("generation.csv")
    if gen:
        plot(
            series(gen, "label", "cells", "time_ms"),
            "Maze generation: median time vs maze size",
            "cells (log)", "milliseconds (log)", "generation_time.png",
        )
        print("\nGeneration summary (median ms):")
        by = defaultdict(list)
        for r in gen:
            by[r["label"]].append((int(r["cells"]), float(r["time_ms"])))
        for label, pts in by.items():
            pts.sort()
            s = "  ".join(f"{c:>6}c:{t:8.2f}" for c, t in pts)
            print(f"  {label:>24} | {s}")

    pf_files = sorted(RESULTS.glob("pathfinding_*.csv"))
    for pf_path in pf_files:
        gen_name = pf_path.stem.replace("pathfinding_", "")
        pf = read_csv(pf_path.name)
        if not pf:
            continue
        nice = GENERATOR_LABELS.get(gen_name, gen_name)
        plot(
            series(pf, "label", "cells", "time_ms"),
            f"Pathfinding: median time vs maze size ({nice} mazes)",
            "cells (log)", "milliseconds (log)", f"pathfinding_time_{gen_name}.png",
        )
        plot(
            series(pf, "label", "cells", "nodes_expanded"),
            f"Pathfinding: nodes expanded vs maze size ({nice} mazes)",
            "cells (log)", "nodes expanded (log)", f"nodes_expanded_{gen_name}.png",
        )
        print(f"\nPathfinding summary on {nice} mazes, largest size:")
        biggest = max(int(r["cells"]) for r in pf)
        for r in pf:
            if int(r["cells"]) == biggest:
                print(
                    f"  {r['label']:>22} | {float(r['time_ms']):8.2f} ms | "
                    f"{int(r['nodes_expanded']):>6} expanded | path {int(r['path_length']):>5} "
                    f"{'optimal' if r['optimal'] == '1' else 'LONGER'}"
                )

    mem = read_csv("memory.csv")
    if mem:
        gen_mem = [r for r in mem if r["kind"] == "generation"]
        plot(
            series(gen_mem, "label", "cells", "peak_bytes"),
            "Generation: peak allocation vs maze size (tracemalloc)",
            "cells (log)", "peak bytes (log)", "memory_peak.png",
        )
        print("\nSolver peak memory @ 127x127:")
        for r in mem:
            if r["kind"] == "solver" and r["w"] == "127":
                print(
                    f"  {r['label']:>22} | peak {int(r['peak_bytes']):>10,} B"
                )

    if not (gen or pf or mem):
        print("no benchmark results found -- nothing to plot")
        sys.exit(1)


if __name__ == "__main__":
    main()
