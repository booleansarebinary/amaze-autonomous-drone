"""Static-grid behavior tests; no sensors, radio, or flight commands."""

import math
import unittest
from collections import deque

from algorithms import grid_navigation
from algorithms.grid_navigation import Grid


def breadth_first_steps(width, height, blocked, start, goal):
    """Independent shortest-length reference for valid unit-cost inputs."""
    pending = deque([(start, 0)])
    visited = {start}
    while pending:
        (x, y), steps = pending.popleft()
        if (x, y) == goal:
            return steps
        # Deliberately use raw map data, not the production grid helpers.
        for candidate in ((x, y - 1), (x - 1, y), (x, y + 1), (x + 1, y)):
            column, row = candidate
            if not (0 <= column < width and 0 <= row < height):
                continue
            if candidate in blocked or candidate in visited:
                continue
            visited.add(candidate)
            pending.append((candidate, steps + 1))
    return None


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


class AstarTests(unittest.TestCase):
    def assert_valid_route(self, grid, route, start, goal, steps):
        self.assertIsNotNone(route)
        self.assertEqual(route[0], start)
        self.assertEqual(route[-1], goal)
        self.assertEqual(len(route) - 1, steps)
        for cell in route:
            self.assertIsInstance(cell, tuple)
            self.assertEqual(len(cell), 2)
            x, y = cell
            self.assertIs(type(x), int)
            self.assertIs(type(y), int)
            self.assertTrue(0 <= x < grid.width and 0 <= y < grid.height, cell)
            self.assertNotIn(cell, grid.blocked)
        for previous, current in zip(route, route[1:]):
            self.assertEqual(
                abs(previous[0] - current[0]) + abs(previous[1] - current[1]), 1
            )

    def test_open_grid_returns_a_shortest_route_with_both_endpoints(self):
        grid = Grid(4, 3)
        route = grid_navigation.astar(grid, (0, 0), (3, 2))
        self.assert_valid_route(grid, route, (0, 0), (3, 2), steps=5)

    def test_obstacle_requires_a_detour(self):
        grid = Grid(3, 2, blocked={(1, 0)})
        route = grid_navigation.astar(grid, (0, 0), (2, 0))
        self.assert_valid_route(grid, route, (0, 0), (2, 0), steps=4)

    def test_later_cheaper_route_replaces_an_earlier_discovery(self):
        # This layout needs a cheaper arrival at (4, 3): 9 steps instead of 11.
        # Keeping the first discovery produces a 19-step route to the goal.
        grid = Grid(8, 7, blocked={
            (0, 6), (1, 0), (1, 1), (1, 2), (1, 3), (1, 5), (1, 6),
            (2, 6), (3, 4), (4, 0), (5, 3), (5, 4), (5, 6),
            (6, 1), (6, 4), (6, 5), (7, 0),
        })
        route = grid_navigation.astar(grid, (0, 0), (7, 6))
        self.assert_valid_route(grid, route, (0, 0), (7, 6), steps=17)

    def test_tied_choices_produce_repeatable_shortest_routes(self):
        grid = Grid(3, 3)
        route = grid_navigation.astar(grid, (0, 0), (2, 2))
        self.assert_valid_route(grid, route, (0, 0), (2, 2), steps=4)
        for _ in range(3):
            self.assertEqual(grid_navigation.astar(grid, (0, 0), (2, 2)), route)

    def test_start_at_goal_returns_one_cell(self):
        self.assertEqual(grid_navigation.astar(Grid(2, 2), (1, 1), (1, 1)), [(1, 1)])

    def test_valid_disconnected_endpoints_return_no_route(self):
        grid = Grid(3, 2, blocked={(1, 0), (1, 1)})
        self.assertIsNone(grid_navigation.astar(grid, (0, 0), (2, 0)))

    def test_blocked_and_out_of_bounds_endpoints_are_invalid(self):
        grid = Grid(3, 2, blocked={(1, 0)})
        for start, goal in [
            ((1, 0), (2, 0)), ((0, 0), (1, 0)),
            ((-1, 0), (2, 0)), ((0, 0), (3, 0)),
        ]:
            with self.subTest(start=start, goal=goal):
                with self.assertRaises(ValueError):
                    grid_navigation.astar(grid, start, goal)

    def test_breadth_first_reference_matches_hand_counted_cases(self):
        cases = [
            (4, 3, set(), (0, 0), (3, 2), 5),
            (3, 2, {(1, 0)}, (0, 0), (2, 0), 4),
            (3, 2, {(1, 0), (1, 1)}, (0, 0), (2, 0), None),
            (1, 1, set(), (0, 0), (0, 0), 0),
        ]
        for width, height, blocked, start, goal, expected in cases:
            with self.subTest(width=width, height=height, blocked=blocked):
                self.assertEqual(
                    breadth_first_steps(width, height, blocked, start, goal), expected
                )

    def test_narrow_passage_requires_a_longer_route(self):
        blocked = {(2, y) for y in range(5) if y != 2}
        grid = Grid(5, 5, blocked)
        route = grid_navigation.astar(grid, (0, 0), (4, 0))
        self.assert_valid_route(grid, route, (0, 0), (4, 0), steps=8)
        self.assertIn((2, 2), route)

    def test_one_cell_wide_rectangles_work_in_both_directions(self):
        for width, height in [(1, 5), (5, 1)]:
            grid = Grid(width, height)
            far_corner = (width - 1, height - 1)
            for start, goal in [((0, 0), far_corner), (far_corner, (0, 0))]:
                with self.subTest(width=width, height=height, start=start):
                    route = grid_navigation.astar(grid, start, goal)
                    self.assert_valid_route(grid, route, start, goal, steps=4)

    def test_enclosed_start_or_goal_returns_none(self):
        grid = Grid(3, 3, blocked={(1, 0), (0, 1)})
        for start, goal in [((0, 0), (2, 2)), ((2, 2), (0, 0))]:
            with self.subTest(start=start, goal=goal):
                self.assertIsNone(grid_navigation.astar(grid, start, goal))

    def test_start_equals_goal_still_requires_a_valid_cell(self):
        grid = Grid(2, 2, blocked={(1, 1)})
        for cell in [(1, 1), (-1, 0), (0, 2)]:
            with self.subTest(cell=cell):
                with self.assertRaises(ValueError):
                    grid_navigation.astar(grid, cell, cell)
        self.assertEqual(grid_navigation.astar(Grid(1, 1), (0, 0), (0, 0)), [(0, 0)])

    def test_each_endpoint_rejects_all_map_boundaries_and_malformed_cells(self):
        grid = Grid(4, 2)
        invalid_cells = [
            (-1, 0), (4, 0), (0, -1), (0, 2), (1.0, 0), (True, 0),
            (float("nan"), 0), (0, float("inf")), (0,), (0, 0, 0),
            [0, 0], "00", None,
        ]
        for invalid in invalid_cells:
            for start, goal in [(invalid, (0, 0)), ((0, 0), invalid)]:
                with self.subTest(start=start, goal=goal):
                    with self.assertRaises(ValueError):
                        grid_navigation.astar(grid, start, goal)

    def test_all_small_obstacle_layouts_match_independent_breadth_first_search(self):
        for width, height in [(3, 3), (4, 2), (2, 4)]:
            first, last = (0, 0), (width - 1, height - 1)
            optional_obstacles = [
                (x, y) for x in range(width) for y in range(height)
                if (x, y) not in (first, last)
            ]
            for mask in range(1 << len(optional_obstacles)):
                blocked = {
                    cell for index, cell in enumerate(optional_obstacles)
                    if mask & (1 << index)
                }
                grid = Grid(width, height, blocked)
                for start, goal in [(first, last), (last, first)]:
                    with self.subTest(width=width, height=height, mask=mask, start=start):
                        expected = breadth_first_steps(width, height, blocked, start, goal)
                        route = grid_navigation.astar(grid, start, goal)
                        if expected is None:
                            self.assertIsNone(route)
                        else:
                            self.assert_valid_route(grid, route, start, goal, expected)


class GridCoordinatesTests(unittest.TestCase):
    def coordinates(self, grid=None, size=0.5, origin=(-1.0, -0.5)):
        return grid_navigation.GridCoordinates(grid or Grid(4, 2), size, origin)

    def test_centers_use_meters_origin_and_distinct_x_y_axes(self):
        coordinates = self.coordinates()
        self.assertEqual(coordinates.cell_center((0, 0)), (-0.75, -0.25))
        self.assertEqual(coordinates.cell_center((2, 1)), (0.25, 0.25))
        self.assertEqual(coordinates.cell_center((3, 0)), (0.75, -0.25))

    def test_world_points_use_the_containing_cell_including_negative_positions(self):
        coordinates = self.coordinates()
        for point, cell in [
            ((-0.9, -0.4), (0, 0)), ((-0.1, -0.2), (1, 0)),
            ((0.2, 0.2), (2, 1)), ((0.9, 0.4), (3, 1)),
        ]:
            with self.subTest(point=point):
                self.assertEqual(coordinates.world_to_cell(point), cell)

    def test_cell_centers_round_trip_for_rectangular_maps(self):
        for width, height, size, origin in [
            (4, 2, 0.5, (-1.0, -0.5)), (2, 4, 0.25, (1.0, -2.0)),
        ]:
            coordinates = self.coordinates(Grid(width, height), size, origin)
            for x in range(width):
                for y in range(height):
                    with self.subTest(width=width, height=height, cell=(x, y)):
                        self.assertEqual(
                            coordinates.world_to_cell(coordinates.cell_center((x, y))),
                            (x, y),
                        )

    def test_internal_boundaries_belong_to_positive_side(self):
        coordinates = self.coordinates()
        self.assertEqual(coordinates.world_to_cell((-1.0, -0.5)), (0, 0))
        self.assertEqual(coordinates.world_to_cell((-0.5, -0.25)), (1, 0))
        self.assertEqual(coordinates.world_to_cell((-0.75, 0.0)), (0, 1))
        self.assertEqual(coordinates.world_to_cell((0.0, 0.0)), (2, 1))

    def test_points_just_inside_and_outside_boundaries_are_not_clamped(self):
        # Map spans [-1, 1) on x and [-0.5, 0.5) on y.
        coordinates = self.coordinates()
        self.assertEqual(
            coordinates.world_to_cell((math.nextafter(1.0, -math.inf), 0.25)), (3, 1)
        )
        self.assertEqual(
            coordinates.world_to_cell((0.25, math.nextafter(0.5, -math.inf))), (2, 1)
        )
        for point in [
            (1.0, 0.0), (0.0, 0.5),
            (math.nextafter(-1.0, -math.inf), 0.0),
            (0.0, math.nextafter(-0.5, -math.inf)),
        ]:
            with self.subTest(point=point):
                with self.assertRaises(ValueError):
                    coordinates.world_to_cell(point)

    def test_decimal_cell_boundaries_use_the_configured_boundary_positions(self):
        coordinates = self.coordinates(Grid(4, 2), 0.1, (0.0, 0.0))
        edge = 3 * 0.1
        self.assertEqual(coordinates.world_to_cell((edge, 0.05)), (3, 0))
        self.assertEqual(
            coordinates.world_to_cell((math.nextafter(edge, -math.inf), 0.05)), (2, 0)
        )

    def test_conversion_does_not_decide_obstacle_traversability(self):
        grid = Grid(4, 2, blocked={(2, 1)})
        coordinates = self.coordinates(grid)
        self.assertEqual(coordinates.cell_center((2, 1)), (0.25, 0.25))
        self.assertEqual(coordinates.world_to_cell((0.25, 0.25)), (2, 1))
        self.assertFalse(grid.is_traversable((2, 1)))

    def test_invalid_size_and_origin_are_rejected(self):
        for size in [0, -0.5, True, "0.5", math.nan, math.inf]:
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    self.coordinates(size=size)
        for origin in [(math.inf, 0), (0, math.nan), (True, 0), (0,), [0, 0], None]:
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError):
                    self.coordinates(origin=origin)

    def test_invalid_cell_or_world_point_is_rejected(self):
        coordinates = self.coordinates()
        for cell in [(-1, 0), (4, 0), (0, 2), (0.5, 0), (True, 0), [0, 0]]:
            with self.subTest(cell=cell):
                with self.assertRaises(ValueError):
                    coordinates.cell_center(cell)
        for point in [(math.nan, 0), (0, math.inf), (False, 0), ("0", 0), (0,), [0, 0], None]:
            with self.subTest(point=point):
                with self.assertRaises(ValueError):
                    coordinates.world_to_cell(point)

    def test_unrepresentable_map_extents_or_cell_centers_are_rejected(self):
        for size, origin in [(1e308, (0.0, 0.0)), (0.5, (1e16, 0.0))]:
            with self.subTest(size=size, origin=origin):
                with self.assertRaises(ValueError):
                    self.coordinates(size=size, origin=origin)


if __name__ == "__main__":
    unittest.main()
