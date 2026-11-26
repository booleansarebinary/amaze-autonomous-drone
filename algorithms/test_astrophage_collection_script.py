"""Pure planning tests for the team lead's mission script; no hardware."""

import builtins
import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from algorithms import astrophage_collection_script as mission


class GridPointConversionTests(unittest.TestCase):
    def setUp(self):
        # Test settings are temporary in-memory values, not edits to the script.
        settings = patch.multiple(mission, AREA=(0, 2, 0, 2), CELL=0.1)
        settings.start()
        self.addCleanup(settings.stop)

    def test_zero_point_is_at_origin_without_a_half_cell_offset(self):
        self.assertEqual(mission.to_meters((0, 0)), (0.0, 0.0))
        self.assertEqual(mission.to_cell(0.0, 0.0), (0, 0))

    def test_x_and_y_indices_remain_distinct(self):
        x, y = mission.to_meters((3, 2))
        self.assertAlmostEqual(x, 0.3)
        self.assertAlmostEqual(y, 0.2)
        self.assertEqual(mission.to_cell(0.3, 0.2), (3, 2))

    def test_configured_origin_and_spacing_apply_to_both_axes(self):
        with patch.multiple(mission, AREA=(-1, 1, 0.5, 1.5), CELL=0.25):
            self.assertEqual(mission.to_meters((0, 0)), (-1.0, 0.5))
            self.assertEqual(mission.to_meters((3, 2)), (-0.25, 1.0))
            self.assertEqual(mission.to_cell(-0.25, 1.0), (3, 2))

    def test_grid_points_round_trip_across_a_rectangular_area(self):
        with patch.multiple(mission, AREA=(-1, 1, 0.5, 1.5), CELL=0.25):
            for x in range(9):
                for y in range(5):
                    with self.subTest(point=(x, y)):
                        self.assertEqual(
                            mission.to_cell(*mission.to_meters((x, y))), (x, y)
                        )
            self.assertEqual(mission.to_meters((8, 4)), (1.0, 1.5))

    def test_between_point_coordinates_snap_to_nearest_grid_point(self):
        requested = (0.26, 0.34)
        point = mission.to_cell(*requested)
        self.assertEqual(point, (3, 3))
        snapped = mission.to_meters(point)
        self.assertAlmostEqual(snapped[0], 0.3)
        self.assertAlmostEqual(snapped[1], 0.3)
        self.assertNotEqual(snapped, requested)

    def test_exact_halfway_values_use_pythons_current_ties_to_even_rounding(self):
        # Binary-exact spacing makes these genuine ties rather than near-ties.
        with patch.object(mission, "CELL", 0.5):
            self.assertEqual(mission.to_cell(0.25, 0.75), (0, 2))
            self.assertEqual(mission.to_cell(1.25, 1.75), (2, 4))

    def test_negative_world_positions_use_the_configured_origin(self):
        with patch.multiple(mission, AREA=(-1, 1, -2, 0), CELL=0.5):
            self.assertEqual(mission.to_cell(-0.74, -1.24), (1, 2))
            self.assertEqual(mission.to_meters((1, 2)), (-0.5, -1.0))


class CoordinateValidationTests(unittest.TestCase):
    def test_to_cell_rejects_nonfinite_coordinates_on_either_axis(self):
        for x, y in [
            (float("nan"), 0),
            (float("inf"), 0),
            (-float("inf"), 0),
            (0, float("nan")),
            (0, float("inf")),
            (0, -float("inf")),
        ]:
            with self.subTest(x=x, y=y):
                with self.assertRaisesRegex(ValueError, "Coordinates must be finite numbers"):
                    mission.to_cell(x, y)

    def test_to_cell_rejects_non_numeric_values(self):
        for x, y in [(None, 0), ("1", 0), (True, 0)]:
            with self.subTest(x=x, y=y):
                with self.assertRaisesRegex(ValueError, "Coordinates must be finite numbers"):
                    mission.to_cell(x, y)

    def test_plan_rejects_invalid_target_before_search(self):
        with patch.object(mission, "HOME", (0.0, 0.0)), patch.object(mission, "astar") as search:
            with self.assertRaisesRegex(ValueError, "Coordinates must be finite numbers"):
                mission.plan([(float("inf"), 0)], [])
            search.assert_not_called()

    def test_plan_rejects_invalid_home_before_search(self):
        with patch.object(mission, "HOME", (0.0, float("nan"))):
            with patch.object(mission, "astar") as search:
                with self.assertRaisesRegex(ValueError, "Coordinates must be finite numbers"):
                    mission.plan([], [])
                search.assert_not_called()


class GridConfigurationTests(unittest.TestCase):
    def test_spacing_must_be_a_positive_finite_number(self):
        for spacing in [0, -0.1, float("nan"), float("inf"), True, "0.1"]:
            with self.subTest(spacing=spacing), patch.object(mission, "CELL", spacing):
                with self.assertRaisesRegex(ValueError, "CELL must be a positive finite number"):
                    mission.to_cell(0, 0)
                with self.assertRaisesRegex(ValueError, "CELL must be a positive finite number"):
                    mission.to_meters((0, 0))

    def test_area_must_contain_four_finite_numbers(self):
        for area in [(0, 2, 0), (0, float("inf"), 0, 2), (0, "2", 0, 2), (True, 2, 0, 2)]:
            with self.subTest(area=area), patch.object(mission, "AREA", area):
                with self.assertRaisesRegex(ValueError, "AREA must contain four finite numbers"):
                    mission.to_cell(0, 0)
                with self.assertRaisesRegex(ValueError, "AREA must contain four finite numbers"):
                    mission.to_meters((0, 0))

    def test_area_minimums_must_be_less_than_maximums(self):
        for area in [(2, 0, 0, 2), (0, 2, 2, 0), (0, 0, 0, 2), (0, 2, 0, 0)]:
            with self.subTest(area=area), patch.object(mission, "AREA", area):
                with self.assertRaisesRegex(ValueError, "AREA bounds must increase"):
                    mission.to_cell(0, 0)

    def test_plan_rejects_bad_grid_settings_before_search(self):
        with patch.object(mission, "CELL", 0), patch.object(mission, "astar") as search:
            with self.assertRaisesRegex(ValueError, "CELL must be a positive finite number"):
                mission.plan([], [])
            search.assert_not_called()


class ObstacleConfigurationTests(unittest.TestCase):
    def test_plan_rejects_reversed_or_flat_obstacle_rectangles_before_search(self):
        rectangles = [
            (1.0, 0.0, 0.5, 0.5),
            (0.0, 1.0, 0.5, 0.5),
            (0.5, 0.0, 0.5, 0.5),
            (0.0, 0.5, 0.5, 0.5),
        ]
        for obstacle in rectangles:
            with self.subTest(obstacle=obstacle):
                with patch.object(mission, "HOME", (0.0, 0.0)):
                    with patch.object(mission, "astar") as search:
                        with self.assertRaisesRegex(ValueError, "obstacle.*bounds"):
                            mission.plan([], [obstacle])
                        search.assert_not_called()

    def test_plan_rejects_nonfinite_obstacle_bounds_before_search(self):
        for bad_bound in (float("nan"), float("inf"), -float("inf")):
            obstacle = (0.5, 0.5, bad_bound, 1.0)
            with self.subTest(obstacle=obstacle):
                with patch.object(mission, "HOME", (0.0, 0.0)):
                    with patch.object(mission, "astar") as search:
                        with self.assertRaisesRegex(ValueError, "obstacle.*finite"):
                            mission.plan([], [obstacle])
                        search.assert_not_called()


class RequestedPositionBoundsTests(unittest.TestCase):
    def setUp(self):
        settings = patch.multiple(
            mission, AREA=(0, 1, 0, 1), CELL=0.1, CLEARANCE=0.01, HOME=(0.0, 0.0)
        )
        settings.start()
        self.addCleanup(settings.stop)

    def test_target_outside_area_is_rejected_even_if_rounding_moves_it_inside(self):
        for target in [(-0.02, 0.5), (1.02, 0.5), (0.5, -0.02), (0.5, 1.02)]:
            with self.subTest(target=target):
                with patch.object(mission, "astar") as search:
                    with self.assertRaisesRegex(ValueError, "outside AREA"):
                        mission.plan([target], [])
                    search.assert_not_called()

    def test_home_outside_area_is_rejected_before_search(self):
        for home in [(-0.02, 0.5), (1.02, 0.5), (0.5, -0.02), (0.5, 1.02)]:
            with self.subTest(home=home):
                with patch.object(mission, "HOME", home):
                    with patch.object(mission, "astar") as search:
                        with self.assertRaisesRegex(ValueError, "outside AREA"):
                            mission.plan([], [])
                        search.assert_not_called()


class PointClearanceTests(unittest.TestCase):
    def setUp(self):
        settings = patch.multiple(mission, AREA=(0, 4, 0, 3), CELL=0.25, CLEARANCE=0.375)
        settings.start()
        self.addCleanup(settings.stop)

    def test_inside_edge_near_and_distant_points_against_supplied_rectangles(self):
        obstacle = (1, 1, 2, 2)
        for point in [(6, 6), (4, 6), (3, 6)]:
            with self.subTest(point=point):
                self.assertTrue(mission.is_blocked(point, [obstacle]))
        self.assertFalse(mission.is_blocked((2, 6), [obstacle]))
        self.assertFalse(mission.is_blocked((6, 6), []))
        # A later rectangle still blocks the point when the first is far away.
        self.assertTrue(mission.is_blocked((6, 6), [(3, 2, 4, 3), obstacle]))

    def test_rectangle_corner_uses_straight_line_distance(self):
        # (0.75, 0.75) is sqrt(0.25**2 + 0.25**2) from this rectangle.
        obstacle = (1, 1, 2, 2)
        self.assertTrue(mission.is_blocked((3, 3), [obstacle]))
        with patch.object(mission, "CLEARANCE", 0.3):
            self.assertFalse(mission.is_blocked((3, 3), [obstacle]))


class GridPointSearchTests(unittest.TestCase):
    def setUp(self):
        # Inclusive point indices are x=0..4 and y=0..2 in this example.
        settings = patch.multiple(mission, AREA=(0, 4, 0, 2), CELL=1, CLEARANCE=0.25)
        settings.start()
        self.addCleanup(settings.stop)

    def assert_valid_route(self, route, start, goal, blocked_points, steps):
        self.assertTrue(route, "expected a non-empty route")
        self.assertEqual((route[0], route[-1]), (start, goal))
        self.assertEqual(len(route) - 1, steps)
        for x, y in route:
            self.assertTrue(0 <= x <= 4 and 0 <= y <= 2)
            # Independent expected obstacle points, not the production checker.
            self.assertNotIn((x, y), blocked_points)
        for first, second in zip(route, route[1:]):
            self.assertEqual(abs(first[0] - second[0]) + abs(first[1] - second[1]), 1)

    def test_open_rectangular_map_has_shortest_cardinal_routes(self):
        for start, goal, steps in [((0, 1), (4, 1), 4), ((4, 0), (4, 2), 2)]:
            with self.subTest(start=start, goal=goal):
                route = mission.astar(start, goal, [])
                self.assert_valid_route(route, start, goal, set(), steps)

    def test_single_blocked_point_requires_a_shortest_detour(self):
        obstacle = (1.75, 0.75, 2.25, 1.25)
        route = mission.astar((0, 1), (4, 1), [obstacle])
        self.assert_valid_route(route, (0, 1), (4, 1), {(2, 1)}, steps=6)

    def test_wall_separating_free_endpoints_has_no_route(self):
        obstacle = (1.75, 0, 2.25, 2)
        for start, goal in [((0, 1), (4, 1)), ((4, 1), (0, 1))]:
            with self.subTest(start=start):
                self.assertIsNone(mission.astar(start, goal, [obstacle]))

    def test_same_valid_start_and_goal_returns_one_point(self):
        route = mission.astar((1, 1), (1, 1), [])
        self.assert_valid_route(route, (1, 1), (1, 1), set(), steps=0)


class MapEdgeRouteTests(unittest.TestCase):
    def assert_inside_area(self, point, area):
        x, y = point
        self.assertTrue(
            area[0] <= x <= area[1] and area[2] <= y <= area[3],
            f"waypoint {point} lies outside AREA {area}",
        )

    def test_astar_does_not_detour_beyond_either_map_edge(self):
        # A short detour outside the map must not beat a longer legal detour.
        cases = [
            ((0, 0.26, 0, 0.2), (0.09, 0.09, 0.21, 0.11), (2, 0), (2, 2)),
            ((0, 0.2, 0, 0.26), (0.09, 0.09, 0.11, 0.21), (0, 2), (2, 2)),
        ]
        for area, obstacle, start, goal in cases:
            with self.subTest(area=area):
                with patch.multiple(mission, AREA=area, CELL=0.1, CLEARANCE=0.02):
                    route = mission.astar(start, goal, [obstacle])
                    self.assertIsNotNone(route)
                    self.assertEqual((route[0], route[-1]), (start, goal))
                    for cell in route:
                        self.assert_inside_area(mission.to_meters(cell), area)

    def test_complete_plan_does_not_export_outside_waypoints(self):
        area = (0, 0.26, 0, 0.2)
        obstacle = (0.09, 0.09, 0.21, 0.11)
        with patch.multiple(
            mission, AREA=area, CELL=0.1, CLEARANCE=0.02, HOME=(0.2, 0.0)
        ):
            legs = mission.plan([(0.2, 0.2)], [obstacle])
            self.assertEqual([stop for stop, _ in legs], [(0.2, 0.2), (0.2, 0.0)])
            for _, waypoints in legs:
                for point in waypoints:
                    self.assert_inside_area(point, area)


class ContinuousSegmentTests(unittest.TestCase):
    def assert_route_avoids_rectangle(self, legs, home, obstacle):
        x_min, y_min, x_max, y_max = obstacle
        start = home
        for stop, waypoints in legs:
            self.assertTrue(waypoints, f"expected a route to {stop}")
            for end in waypoints:
                if start[1] == end[1]:
                    crosses = (
                        y_min <= start[1] <= y_max
                        and min(start[0], end[0]) <= x_max
                        and max(start[0], end[0]) >= x_min
                    )
                elif start[0] == end[0]:
                    crosses = (
                        x_min <= start[0] <= x_max
                        and min(start[1], end[1]) <= y_max
                        and max(start[1], end[1]) >= y_min
                    )
                else:
                    self.fail(f"diagonal shortcut from {start} to {end}")
                self.assertFalse(crosses, f"segment {start} to {end} crosses {obstacle}")
                start = end

    def test_plan_detours_around_thin_obstacle_between_grid_points(self):
        cases = [
            ((0, 2, 0, 1), (2.0, 0.0), (0.45, -0.05, 0.55, 0.05)),
            ((0, 1, 0, 2), (0.0, 2.0), (-0.05, 0.45, 0.05, 0.55)),
        ]
        for area, target, obstacle in cases:
            with self.subTest(target=target):
                with patch.multiple(
                    mission, AREA=area, CELL=1, CLEARANCE=0.1, HOME=(0.0, 0.0)
                ):
                    legs = mission.plan([target], [obstacle])
                    self.assertEqual([stop for stop, _ in legs], [target, (0.0, 0.0)])
                    self.assert_route_avoids_rectangle(legs, (0.0, 0.0), obstacle)

    def test_plan_reports_no_path_when_thin_barrier_spans_the_map(self):
        barrier = (0.45, -0.1, 0.55, 1.1)
        with patch.multiple(
            mission, AREA=(0, 2, 0, 1), CELL=1, CLEARANCE=0.1, HOME=(0.0, 0.0)
        ):
            with self.assertRaisesRegex(SystemExit, "No path"):
                mission.plan([(2.0, 0.0)], [barrier])


class CornerReductionTests(unittest.TestCase):
    def setUp(self):
        settings = patch.multiple(mission, AREA=(0, 4, 0, 3), CELL=1)
        settings.start()
        self.addCleanup(settings.stop)

    def test_straight_runs_keep_only_the_final_point_in_each_direction(self):
        for path, expected in [
            ([(0, 1), (1, 1), (2, 1)], [(2, 1)]),
            ([(2, 1), (1, 1), (0, 1)], [(0, 1)]),
            ([(1, 0), (1, 1), (1, 2)], [(1, 2)]),
            ([(1, 2), (1, 1), (1, 0)], [(1, 0)]),
        ]:
            with self.subTest(path=path):
                self.assertEqual(mission.corners(path), expected)

    def test_multiple_turns_and_final_point_are_retained_in_order(self):
        path = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
        self.assertEqual(mission.corners(path), [(2, 0), (2, 2), (0, 2), (0, 1)])

    def test_one_step_path_omits_start_and_keeps_destination(self):
        self.assertEqual(mission.corners([(1, 1), (2, 1)]), [(2, 1)])

    def test_one_point_path_has_no_movement_commands(self):
        self.assertEqual(mission.corners([(2, 1)]), [])

    def test_retained_points_use_configured_origin_and_spacing(self):
        with patch.multiple(mission, AREA=(-1, 0, 0.5, 1.5), CELL=0.25):
            path = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
            self.assertEqual(mission.corners(path), [(-0.5, 0.5), (-0.5, 1.0)])


class CompletePlanTests(unittest.TestCase):
    def setUp(self):
        settings = patch.multiple(
            mission, AREA=(0, 3, 0, 2), HOME=(0.0, 0.0), CELL=1, CLEARANCE=0.25
        )
        settings.start()
        self.addCleanup(settings.stop)

    def test_supplied_targets_are_visited_in_order_then_home(self):
        targets = [(1, 0), (1, 1)]
        legs = mission.plan(targets, [])

        self.assertEqual([stop for stop, _ in legs], targets + [(0.0, 0.0)])
        self.assertEqual(legs[0][1], [(1, 0)])
        self.assertEqual(legs[1][1], [(1, 1)])
        self.assertEqual(legs[2][1][-1], (0, 0))
        self.assertEqual(targets, [(1, 0), (1, 1)])

    def test_no_targets_produces_only_an_empty_home_leg(self):
        self.assertEqual(mission.plan([], []), [((0.0, 0.0), [])])

    def test_blocked_target_reports_which_stop_failed(self):
        with self.assertRaisesRegex(SystemExit, r"Target \(1, 0\).*too close"):
            mission.plan([(1, 0)], [(0.9, -0.1, 1.1, 0.1)])

    def test_blocked_home_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, r"Target \(0\.0, 0\.0\).*too close"):
            mission.plan([], [(-0.1, -0.1, 0.1, 0.1)])

    def test_unreachable_target_reports_no_path(self):
        wall = (1.75, 0, 2.25, 2)
        with self.assertRaisesRegex(SystemExit, r"No path to \(3, 0\)"):
            mission.plan([(3, 0)], [wall])


class CommandLineSafetyTests(unittest.TestCase):
    def test_import_does_not_import_crazyflie_or_start_radio_access(self):
        spec = importlib.util.spec_from_file_location(
            "astrophage_import_safety_probe", Path(mission.__file__)
        )
        module = importlib.util.module_from_spec(spec)
        original_import = builtins.__import__

        def reject_crazyflie_import(name, *args, **kwargs):
            if name == "cflib" or name.startswith("cflib."):
                raise AssertionError(f"unexpected Crazyflie import: {name}")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_crazyflie_import):
            spec.loader.exec_module(module)

        self.assertTrue(callable(module.main))

    def test_dry_run_prints_route_without_calling_fly(self):
        settings = patch.multiple(
            mission,
            AREA=(0, 2, 0, 2),
            HOME=(0, 0),
            CELL=0.1,
            CLEARANCE=0.01,
            TARGETS=[(0.2, 0.0)],
            OBSTACLES=[],
        )
        with settings, patch.object(mission, "fly") as fly:
            with patch("sys.argv", ["astrophage_collection_script", "--dry-run"]):
                output = io.StringIO()
                with redirect_stdout(output):
                    mission.main()

        fly.assert_not_called()
        self.assertIn("To (0.2, 0.0)", output.getvalue())
        self.assertIn("To (0, 0)", output.getvalue())


if __name__ == "__main__":
    unittest.main()
