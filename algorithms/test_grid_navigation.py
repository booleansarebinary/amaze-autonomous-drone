"""Static-grid behavior tests; no sensors, radio, or flight commands."""

import unittest

from algorithms import grid_navigation
from algorithms.grid_navigation import Grid


class GridTests(unittest.TestCase):
    def test_rectangular_bounds_use_x_for_width_and_y_for_height(self):
        grid = Grid(width=4, height=2)
        for cell in [(0, 0), (3, 0), (0, 1), (3, 1)]:
            with self.subTest(cell=cell):
                self.assertTrue(grid.in_bounds(cell))
        for cell in [(-1, 0), (0, -1), (4, 0), (0, 2), (1, 3)]:
            with self.subTest(cell=cell):
                self.assertFalse(grid.in_bounds(cell))

    def test_only_unblocked_in_bounds_cells_are_traversable(self):
        grid = Grid(4, 2, blocked={(2, 1)})
        self.assertTrue(grid.is_traversable((1, 1)))
        self.assertFalse(grid.is_traversable((2, 1)))
        self.assertTrue(grid.is_traversable((2, 0)))
        self.assertFalse(grid.is_traversable((4, 0)))

    def test_interior_neighbors_are_cardinal_and_ordered(self):
        self.assertEqual(
            Grid(3, 3).neighbors((1, 1)),
            [(2, 1), (1, 2), (0, 1), (1, 0)],
        )

    def test_all_corners_and_an_edge_exclude_out_of_bounds_cells(self):
        grid = Grid(4, 3)
        expected = {
            (0, 0): [(1, 0), (0, 1)],
            (3, 0): [(3, 1), (2, 0)],
            (0, 2): [(1, 2), (0, 1)],
            (3, 2): [(2, 2), (3, 1)],
            (1, 0): [(2, 0), (1, 1), (0, 0)],
        }
        for cell, neighbors in expected.items():
            with self.subTest(cell=cell):
                self.assertEqual(grid.neighbors(cell), neighbors)

    def test_blocked_neighbors_are_excluded(self):
        grid = Grid(3, 3, blocked={(2, 1), (1, 2)})
        self.assertEqual(grid.neighbors((1, 1)), [(0, 1), (1, 0)])

    def test_blocked_or_out_of_bounds_sources_have_no_neighbors(self):
        grid = Grid(3, 2, blocked={(1, 0)})
        for cell in [(1, 0), (-1, 0), (3, 0), (0, 2)]:
            with self.subTest(cell=cell):
                self.assertEqual(grid.neighbors(cell), [])
        self.assertEqual(Grid(1, 1).neighbors((0, 0)), [])

    def test_grid_copies_supplied_obstacles(self):
        blocked = {(1, 0)}
        grid = Grid(3, 2, blocked=blocked)
        blocked.clear()
        self.assertFalse(grid.is_traversable((1, 0)))
        self.assertEqual(grid.blocked, frozenset({(1, 0)}))

    def test_invalid_dimensions_and_obstacle_coordinates_are_rejected(self):
        for width, height in [(0, 2), (2, -1), (2.5, 2), (2, True)]:
            with self.subTest(width=width, height=height):
                with self.assertRaises(ValueError):
                    Grid(width, height)
        for cell in [(-1, 0), (3, 0), (0, 2), (1.0, 0), (True, 0), (1,)]:
            with self.subTest(cell=cell):
                with self.assertRaises(ValueError):
                    Grid(3, 2, blocked={cell})

    def test_queries_reject_malformed_cells(self):
        grid = Grid(3, 2)
        for query in [grid.in_bounds, grid.is_traversable, grid.neighbors]:
            for cell in [(0.5, 0), (0, False), (0,), [0, 0], "00", None]:
                with self.subTest(query=query.__name__, cell=cell):
                    with self.assertRaises(ValueError):
                        query(cell)


class ManhattanDistanceTests(unittest.TestCase):
    def test_goal_itself_has_zero_distance(self):
        self.assertEqual(grid_navigation.manhattan_distance((3, 2), (3, 2)), 0)

    def test_horizontal_distance_in_both_directions(self):
        self.assertEqual(grid_navigation.manhattan_distance((1, 2), (5, 2)), 4)
        self.assertEqual(grid_navigation.manhattan_distance((5, 2), (1, 2)), 4)

    def test_vertical_distance_in_both_directions(self):
        self.assertEqual(grid_navigation.manhattan_distance((3, 1), (3, 6)), 5)
        self.assertEqual(grid_navigation.manhattan_distance((3, 6), (3, 1)), 5)

    def test_mixed_axes_add_independent_step_counts(self):
        for start, goal, expected in [
            ((1, 2), (4, 6), 7),
            ((4, 6), (1, 2), 7),
            ((1, 6), (4, 2), 7),
            ((-2, 3), (1, -1), 7),
        ]:
            with self.subTest(start=start, goal=goal):
                self.assertEqual(grid_navigation.manhattan_distance(start, goal), expected)

    def test_malformed_endpoint_is_rejected(self):
        for invalid in [(1.5, 2), (True, 2), (1,), [1, 2], None]:
            for start, goal in [(invalid, (0, 0)), ((0, 0), invalid)]:
                with self.subTest(start=start, goal=goal):
                    with self.assertRaises(ValueError):
                        grid_navigation.manhattan_distance(start, goal)


if __name__ == "__main__":
    unittest.main()
