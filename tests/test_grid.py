"""Tests for the Grid data structure."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maze.grid import ALL_WALLS, DELTA, DIRS, E, Grid, N, S, W


class TestGrid(unittest.TestCase):
    def test_new_grid_fully_walled(self):
        g = Grid(4, 3)
        for x, y in g.cells_iter():
            self.assertEqual(g.walls_at(x, y), ALL_WALLS)
            self.assertEqual(g.degree(x, y), 0)
        self.assertEqual(g.passage_count(), 0)

    def test_open_grid_has_only_borders(self):
        g = Grid(4, 3, walls_mode="open")
        # An open grid has every interior passage open (that's the point --
        # recursive division starts here and walls passages off):
        # (w-1)*h + w*(h-1) = 3*3 + 4*2 = 17 shared edges.
        self.assertEqual(g.passage_count(), (4 - 1) * 3 + 4 * (3 - 1))
        for x, y in g.cells_iter():
            expect = 0
            if y == 0:
                expect |= N
            if y == g.height - 1:
                expect |= S
            if x == 0:
                expect |= W
            if x == g.width - 1:
                expect |= E
            self.assertEqual(g.walls_at(x, y), expect, (x, y))

    def test_carve_symmetry_and_can_go(self):
        g = Grid(5, 5)
        g.carve(2, 2, E)
        self.assertFalse(g.has_wall(2, 2, E))
        self.assertFalse(g.has_wall(3, 2, W))
        self.assertTrue(g.can_go(2, 2, E))
        self.assertTrue(g.can_go(3, 2, W))
        self.assertEqual(g.passage_count(), 1)
        self.assertEqual(g.open_neighbors(2, 2), [(3, 2)])

    def test_add_wall_symmetry(self):
        g = Grid(5, 5, walls_mode="open")
        self.assertTrue(g.can_go(2, 2, E))
        g.add_wall(2, 2, E)
        self.assertTrue(g.has_wall(2, 2, E))
        self.assertTrue(g.has_wall(3, 2, W))
        self.assertFalse(g.can_go(2, 2, E))

    def test_carve_out_of_bounds_raises(self):
        g = Grid(4, 4)
        with self.assertRaises(ValueError):
            g.carve(0, 0, N)
        with self.assertRaises(ValueError):
            g.carve(3, 3, E)
        with self.assertRaises(ValueError):
            g.add_wall(0, 0, W)

    def test_border_never_open(self):
        g = Grid(4, 4, walls_mode="open")
        for x, y in g.cells_iter():
            for d in DIRS:
                nx, ny = x + DELTA[d][0], y + DELTA[d][1]
                if not g.in_bounds(nx, ny):
                    self.assertFalse(g.can_go(x, y, d), (x, y, d))

    def test_passage_count_counts_shared_edges_once(self):
        g = Grid(3, 2)
        g.carve(0, 0, E)   # (0,0)-(1,0)
        g.carve(1, 0, E)   # (1,0)-(2,0)
        g.carve(0, 1, E)   # (0,1)-(1,1)
        self.assertEqual(g.passage_count(), 3)

    def test_to_ascii_marks_path_and_markers(self):
        g = Grid(2, 2)
        g.carve(0, 0, E)
        g.carve(1, 0, S)
        art = g.to_ascii(path=[(0, 0), (1, 0)], markers={(1, 1): "G"})
        lines = art.splitlines()
        # 2 cells -> 2+1 wall rows of "+" lines, 2 cell rows, 1 bottom row
        self.assertEqual(len(lines), 2 * 2 + 1)
        self.assertIn("*", lines[1])
        self.assertIn("G", lines[3])

    def test_index_roundtrip(self):
        g = Grid(7, 5)
        for x, y in g.cells_iter():
            self.assertEqual(g.cell_at(g.index(x, y)), (x, y))

    def test_rejects_degenerate(self):
        with self.assertRaises(ValueError):
            Grid(0, 3)
        with self.assertRaises(ValueError):
            Grid(3, 0)
        with self.assertRaises(ValueError):
            Grid(3, 3, walls_mode="bogus")


if __name__ == "__main__":
    unittest.main()
