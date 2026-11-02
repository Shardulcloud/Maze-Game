"""Tests for line-of-sight / fog-of-war visibility."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game.visibility import explore, line_of_sight, visible_cells
from maze import generate
from maze.grid import Grid


class TestLineOfSight(unittest.TestCase):
    def test_same_cell(self):
        g = Grid(4, 4)
        self.assertTrue(line_of_sight(g, 2, 2, 2, 2))

    def test_wall_blocks_adjacent(self):
        g = Grid(4, 4)  # fully walled
        self.assertFalse(line_of_sight(g, 1, 1, 2, 1))
        self.assertFalse(line_of_sight(g, 1, 1, 1, 2))

    def test_open_adjacent(self):
        g = Grid(4, 4, walls_mode="open")  # no interior walls
        self.assertTrue(line_of_sight(g, 1, 1, 2, 1))
        self.assertTrue(line_of_sight(g, 1, 1, 2, 2))  # diagonal, L open

    def test_diagonal_blocked_by_both_ls(self):
        # Corner cell with both L paths walled: diagonal LOS blocked.
        g = Grid(4, 4, walls_mode="open")
        g.add_wall(1, 1, 2)  # E wall of (1,1)
        g.add_wall(1, 1, 4)  # S wall of (1,1)
        self.assertFalse(line_of_sight(g, 1, 1, 2, 2))

    def test_diagonal_open_via_one_l(self):
        g = Grid(4, 4, walls_mode="open")
        g.add_wall(1, 1, 2)  # E blocked, S open -> L via (1,2) still open
        self.assertTrue(line_of_sight(g, 1, 1, 2, 2))

    def test_long_corridor(self):
        # A corridor maze: LOS down the corridor, blocked by its walls.
        g = Grid(9, 3)
        for x in range(8):
            g.carve(x, 1, 2)  # open corridor along middle row
        self.assertTrue(line_of_sight(g, 0, 1, 8, 1))
        self.assertFalse(line_of_sight(g, 0, 1, 8, 0))  # blocked by row walls
        # In a fully-walled 1-wide corridor above? (0,0)-(8,0) has no passages
        # and walls all around: blocked immediately.

    def test_symmetry(self):
        for seed in (1, 2, 3):
            g = generate(13, 9, method="dfs", seed=seed)
            with self.subTest(seed=seed):
                for (a, b) in [((0, 0), (12, 8)), ((6, 4), (0, 8))]:
                    self.assertEqual(
                        line_of_sight(g, *a, *b),
                        line_of_sight(g, *b, *a),
                        (a, b),
                    )


class TestVisibleCells(unittest.TestCase):
    def test_contains_self_and_respects_radius(self):
        g = generate(31, 21, method="dfs", seed=6)
        vis = visible_cells(g, 15, 10, 4.0)
        self.assertIn((15, 10), vis)
        for (x, y) in vis:
            dist2 = (x - 15) ** 2 + (y - 10) ** 2
            self.assertLessEqual(dist2, 4.0 * 4.0 + 1e-9, (x, y))
        # Round fog, not square: the circle strictly excludes some cells that
        # a Chebyshev (square) radius of 4 would include.
        square_only = {
            (15 + ox, 10 + oy)
            for ox in range(-4, 5) for oy in range(-4, 5)
            if max(abs(ox), abs(oy)) <= 4 and ox * ox + oy * oy > 16
        }
        self.assertTrue(any(c not in vis for c in square_only))

    def test_respects_bounds(self):
        g = generate(21, 15, method="prim", seed=3)
        vis = visible_cells(g, 0, 0, 3.5)
        for (x, y) in vis:
            self.assertTrue(0 <= x < 21 and 0 <= y < 15)

    def test_explore_accumulates(self):
        g = generate(21, 15, method="dfs", seed=3)
        explored = set()
        explore(g, explored, 2, 2, 3.0)
        n1 = len(explored)
        self.assertGreater(n1, 1)
        explore(g, explored, 2, 2, 3.0)
        self.assertEqual(len(explored), n1)  # idempotent
        explore(g, explored, 10, 7, 3.0)
        self.assertGreater(len(explored), n1)  # accumulates

    def test_fully_walled_sees_only_self(self):
        g = Grid(10, 10)
        self.assertEqual(visible_cells(g, 5, 5, 4.0), {(5, 5)})


if __name__ == "__main__":
    unittest.main()
