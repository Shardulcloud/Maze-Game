"""Tests for maze generators.

The key property under test is *perfect maze*: the carved passages form a
spanning tree of the cell graph, meaning

  1. every cell is reachable from every other (connected), and
  2. passage count == cell count - 1 (tree, hence exactly one simple path
     between any two cells).

Checking both conditions on many sizes/seeds gives us a strong guarantee;
`test_reachable` doubles as an integration test of the solvers.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maze import GENERATORS, GENERATOR_LABELS, bfs, generate
from maze.grid import Grid


def reachable_cells(grid: Grid, start) -> set:
    came = {start: None}
    q = [start]
    while q:
        cur = q.pop()
        for nb in grid.open_neighbors(*cur):
            if nb not in came:
                came[nb] = cur
                q.append(nb)
    return set(came)


class TestGenerators(unittest.TestCase):
    SIZES = [(3, 3), (7, 5), (13, 9)]
    SEEDS = [1, 2, 3, 42]

    def test_registry_covers_all_algorithms(self):
        self.assertEqual(
            set(GENERATORS), set(GENERATOR_LABELS),
            "every registered generator should have a label (menus rely on it)",
        )

    def test_all_generators_produce_perfect_mazes(self):
        for method in GENERATORS:
            for (w, h) in self.SIZES:
                for seed in self.SEEDS:
                    with self.subTest(method=method, size=(w, h), seed=seed):
                        grid = generate(w, h, method=method, seed=seed)
                        # 1. tree edge count
                        self.assertEqual(
                            grid.passage_count(), w * h - 1,
                            "passages != n-1: not a spanning tree",
                        )
                        # 2. connectivity
                        seen = reachable_cells(grid, (0, 0))
                        self.assertEqual(len(seen), w * h, "not fully reachable")

    def test_same_seed_same_maze(self):
        for method in GENERATORS:
            with self.subTest(method=method):
                a = generate(9, 7, method=method, seed=123)
                b = generate(9, 7, method=method, seed=123)
                self.assertEqual(bytes(a.walls), bytes(b.walls))

    def test_different_seeds_usually_differ(self):
        for method in GENERATORS:
            with self.subTest(method=method):
                a = generate(15, 11, method=method, seed=1)
                b = generate(15, 11, method=method, seed=2)
                self.assertNotEqual(bytes(a.walls), bytes(b.walls))

    def test_on_carve_events_match_passage_count(self):
        # Event instrumentation must fire exactly once per carved passage.
        for method in ("dfs", "prim", "kruskal", "wilson"):
            with self.subTest(method=method):
                events = []
                generate(
                    9, 7, method=method, seed=5,
                    on_carve=lambda x, y, d: events.append((x, y, d)),
                )
                self.assertEqual(len(events), 9 * 7 - 1)

    def test_on_wall_events_for_division(self):
        events = []
        grid = generate(
            9, 7, method="division", seed=5,
            on_wall=lambda x, y, d: events.append((x, y, d)),
        )
        # Division ends with n-1 passages: (interior edges) - (walls added)
        # interior edges total = n*2 - w - h; walls added = that minus (n-1).
        self.assertEqual(len(events), 9 * 7 * 2 - 9 - 7 - (9 * 7 - 1))
        self.assertEqual(grid.passage_count(), 9 * 7 - 1)

    def test_unknown_method_raises_with_hint(self):
        with self.assertRaises(ValueError) as ctx:
            generate(5, 5, method="magic")
        self.assertIn("kruskal", str(ctx.exception))

    def test_bfs_solves_every_generated_maze(self):
        # Integration: BFS finds a path between opposite corners on every maze.
        for method in GENERATORS:
            for (w, h) in self.SIZES:
                with self.subTest(method=method, size=(w, h)):
                    grid = generate(w, h, method=method, seed=7)
                    res = bfs(grid, (0, 0), (w - 1, h - 1))
                    self.assertTrue(res.found)
                    self.assertEqual(res.path[0], (0, 0))
                    self.assertEqual(res.path[-1], (w - 1, h - 1))


if __name__ == "__main__":
    unittest.main()
