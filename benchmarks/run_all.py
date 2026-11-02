"""Run all benchmarks, then produce charts.

Usage:
    python benchmarks/run_all.py           # full sweep (takes a few minutes)
    python benchmarks/run_all.py --quick   # smaller sweep
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def main() -> int:
    extra = ["--quick"] if "--quick" in sys.argv else []
    for script in ("bench_generation.py", "bench_pathfinding.py", "bench_memory.py"):
        cmds = []
        if script == "bench_pathfinding.py":
            # Sweep two maze textures: a snake-like DFS maze and a roomy
            # Recursive-Division maze -- search algorithms behave very
            # differently on them (that's the interesting analysis!).
            cmds = [[sys.executable, str(HERE / script), "--gen", g] + extra
                    for g in ("dfs", "division")]
        else:
            cmds = [[sys.executable, str(HERE / script)] + extra]
        for cmd in cmds:
            print(f"\n=== {script} {' '.join(cmd[2:])} ===", flush=True)
            rc = subprocess.run(cmd).returncode
            if rc != 0:
                print(f"{script} failed with exit code {rc}")
                return rc
    print("\n=== plots.py ===", flush=True)
    return subprocess.run([sys.executable, str(HERE / "plots.py")]).returncode


if __name__ == "__main__":
    sys.exit(main())
