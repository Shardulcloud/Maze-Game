"""Tests for pathfinding solvers.

Covers: optimality agreement between optimal solvers, path validity (no
walking through walls), solver-specific behaviors (greedy/DFS may be
suboptimal, wall follower follows walls), and edge cases (start == goal,
unreachable goals on a fully-walled grid).
"""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maze import (
    Grid,
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
    solve,
    wall_follower,
)

MAZES = [
    (w, h, seed)
    for w, h in [(5, 5), (9, 7), (13, 11), (21, 15)]
    for seed in (1, 2, 3)
]

OPTIMAL_SOLVERS = [
    ("bfs", bfs),
    ("dijkstra", dijkstra),
    ("astar_manhattan", lambda g, s, t: astar(g, s, t, heuristic=manhattan)),
    ("astar_euclidean", lambda g, s, t: astar(g, s, t, heuristic=euclidean)),
    ("bidirectional", bidirectional_bfs),
    ("dead_end_filling", dead_end_filling),
]


def assert_valid_path(test, grid, path):
    """Every step must cross an open passage (no teleporting through walls)."""
    test.assertIsNotNone(path)
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        dx, dy = x1 - x0, y1 - y0
        test.assertIn((dx, dy), [(0, -1), (1, 0), (0, 1), (-1, 0)])
        # Determine direction of this step and check the passage is open.
        d = {(0, -1): 1, (1, 0): 2, (0, 1): 4, (-1, 0): 8}[(dx, dy)]
        test.assertFalse(grid.has_wall(x0, y0, d), (x0, y0, (x1, y1)))


class TestPathfinding(unittest.TestCase):
    def test_optimal_solvers_agree_on_length(self):
        for (w, h, seed) in MAZES:
            grid = generate(w, h, method="dfs", seed=seed)
            start, goal = (0, 0), (w - 1, h - 1)
            with self.subTest(maze=(w, h, seed)):
                lengths = set()
                for name, fn in OPTIMAL_SOLVERS:
                    res = fn(grid, start, goal)
                    self.assertTrue(res.found, name)
                    assert_valid_path(self, grid, res.path)
                    lengths.add(res.length)
                self.assertEqual(len(lengths), 1, f"solver lengths diverged: {lengths}")

    def test_optimal_across_generators(self):
        # Optimal agreement must hold no matter which generator built the maze.
        for method in ("dfs", "prim", "kruskal", "wilson", "division"):
            grid = generate(11, 9, method=method, seed=9)
            with self.subTest(method=method):
                lb = bfs(grid, (0, 0), (10, 8)).length
                for name, fn in OPTIMAL_SOLVERS:
                    self.assertEqual(fn(grid, (0, 0), (10, 8)).length, lb, name)

    def test_dfs_greedy_find_valid_but_maybe_longer_paths(self):
        for (w, h, seed) in MAZES:
            grid = generate(w, h, method="prim", seed=seed)
            start, goal = (0, 0), (w - 1, h - 1)
            with self.subTest(maze=(w, h, seed)):
                optimal = bfs(grid, start, goal).length
                for name, fn in [("dfs", dfs), ("greedy", greedy_best_first)]:
                    res = fn(grid, start, goal)
                    self.assertTrue(res.found, name)
                    assert_valid_path(self, grid, res.path)
                    self.assertGreaterEqual(res.length, optimal, name)

    def test_wall_follower_solves_perfect_mazes(self):
        for (w, h, seed) in MAZES:
            grid = generate(w, h, method="dfs", seed=seed)
            start, goal = (0, 0), (w - 1, h - 1)
            with self.subTest(maze=(w, h, seed)):
                for hand in ("right", "left"):
                    res = wall_follower(grid, start, goal, hand=hand)
                    self.assertTrue(res.found, hand)
                    assert_valid_path(self, grid, res.path)
                    self.assertEqual(res.path[0], start)
                    self.assertEqual(res.path[-1], goal)
                    # In a perfect maze the wall follower's walk may be long,
                    # but it can't be shorter than the unique shortest path.
                    self.assertGreaterEqual(
                        res.length, bfs(grid, start, goal).length, hand
                    )

    def test_start_equals_goal(self):
        grid = generate(7, 7, method="dfs", seed=1)
        for name, fn in OPTIMAL_SOLVERS:
            res = fn(grid, (3, 3), (3, 3))
            self.assertEqual(res.path, [(3, 3)], name)
        self.assertEqual(dfs(grid, (2, 2), (2, 2)).path, [(2, 2)])
        self.assertEqual(greedy_best_first(grid, (1, 1), (1, 1)).path, [(1, 1)])
        self.assertEqual(
            wall_follower(grid, (0, 0), (0, 0)).path, [(0, 0)]
        )
        self.assertEqual(dead_end_filling(grid, (0, 0), (0, 0)).path, [(0, 0)])

    def test_unreachable_returns_none(self):
        grid = Grid(6, 6)  # fully walled
        for name, fn in OPTIMAL_SOLVERS:
            res = fn(grid, (0, 0), (5, 5))
            self.assertIsNone(res.path, name)
            self.assertFalse(res.found, name)
            self.assertEqual(res.length, -1, name)
        self.assertIsNone(dfs(grid, (0, 0), (5, 5)).path)
        self.assertIsNone(greedy_best_first(grid, (0, 0), (5, 5)).path)
        self.assertIsNone(wall_follower(grid, (0, 0), (5, 5)).path)
        self.assertIsNone(dead_end_filling(grid, (0, 0), (5, 5)).path)

    def test_astar_instruments_and_beats_bfs_on_expansions(self):
        # On corner-to-corner searches A* with an informed heuristic should
        # expand fewer nodes than blind BFS.
        for (w, h, seed) in [(21, 15, 1), (31, 21, 2), (45, 31, 3)]:
            grid = generate(w, h, method="dfs", seed=seed)
            start, goal = (0, 0), (w - 1, h - 1)
            with self.subTest(maze=(w, h, seed)):
                b = bfs(grid, start, goal)
                a = astar(grid, start, goal)
                self.assertLessEqual(a.nodes_expanded, b.nodes_expanded)
                self.assertEqual(a.length, b.length)

    def test_bidirectional_optimal_and_sometimes_cheaper(self):
        # Bidirectional BFS must always match BFS's optimal path length.
        # Node expansions: two half-depth balls *can* be cheaper, but on
        # corner-to-corner rectangle mazes the balls overlap heavily and
        # cells get popped by both sides -- so we only require it to stay
        # within 2x of BFS and to strictly win at least once across seeds.
        # (The benchmark chapter explores this nuance with data.)
        wins = 0
        trials = 0
        for seed in range(1, 11):
            grid = generate(61, 41, method="dfs", seed=seed)
            start, goal = (0, 0), (60, 40)
            b = bfs(grid, start, goal)
            bi = bidirectional_bfs(grid, start, goal)
            self.assertEqual(bi.length, b.length, seed)
            self.assertLessEqual(bi.nodes_expanded, 2 * b.nodes_expanded, seed)
            trials += 1
            if bi.nodes_expanded < b.nodes_expanded:
                wins += 1
        self.assertGreater(wins, 0, "bidirectional never won across seeds")

    def test_greedy_and_dfs_optimal_on_perfect_mazes(self):
        # Lovely structural property: a perfect maze has exactly ONE simple
        # path between any two cells, so every solver that returns a simple
        # path (DFS, greedy best-first included) must return THE path.
        # Wall-follower walks may revisit cells, so it can be longer.
        for seed in range(1, 20):
            grid = generate(15, 11, method="dfs", seed=seed)
            start, goal = (0, 0), (14, 10)
            with self.subTest(seed=seed):
                optimal = bfs(grid, start, goal).length
                self.assertEqual(dfs(grid, start, goal).length, optimal)
                self.assertEqual(greedy_best_first(grid, start, goal).length, optimal)

    def test_greedy_suboptimal_somewhere_on_looped_mazes(self):
        # Suboptimality needs loops.  Carve extra passages into a perfect
        # maze to introduce cycles; over many seeds greedy best-first must
        # commit to a longer route at least once (that's its documented
        # trade-off), while always staying valid and never shorter.
        rng = random.Random(1234)
        longer = 0
        for seed in range(1, 40):
            grid = generate(17, 13, method="dfs", seed=seed)
            start, goal = (0, 0), (16, 12)
            # Smash some interior walls to create loops.
            smashed = 0
            while smashed < 10:
                x, y = rng.randrange(grid.width), rng.randrange(grid.height)
                d = rng.choice([1, 2, 4, 8])
                dx, dy = {1: (0, -1), 2: (1, 0), 4: (0, 1), 8: (-1, 0)}[d]
                if grid.in_bounds(x + dx, y + dy) and grid.has_wall(x, y, d):
                    grid.carve(x, y, d)
                    smashed += 1
            optimal = bfs(grid, start, goal).length
            res = greedy_best_first(grid, start, goal)
            assert_valid_path(self, grid, res.path)
            self.assertGreaterEqual(res.length, optimal)
            if res.length > optimal:
                longer += 1
        self.assertGreater(longer, 0, "greedy never strayed across 40 looped mazes")

    def test_dead_end_filling_reports_pruned_cells(self):
        grid = generate(21, 15, method="dfs", seed=4)
        res = dead_end_filling(grid, (0, 0), (20, 14))
        self.assertTrue(res.found)
        self.assertGreater(res.extra["filled"], 0)

    def test_solve_dispatcher(self):
        grid = generate(9, 9, method="kruskal", seed=2)
        res = solve(grid, (0, 0), (8, 8), algorithm="astar")
        self.assertEqual(res.algorithm, "astar_manhattan")
        self.assertTrue(res.found)
        with self.assertRaises(ValueError):
            solve(grid, (0, 0), (8, 8), algorithm="teleport")
        # kwargs pass through:
        res = solve(grid, (0, 0), (8, 8), algorithm="wall_follower", hand="left")
        self.assertEqual(res.algorithm, "wall_follower_left")

    def test_heuristics(self):
        self.assertEqual(manhattan((0, 0), (3, 4)), 7)
        self.assertEqual(euclidean((0, 0), (3, 4)), 5.0)


if __name__ == "__main__":
    unittest.main()
