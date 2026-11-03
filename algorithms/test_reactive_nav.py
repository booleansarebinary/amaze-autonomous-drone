"""Simulation regressions; no radio or hardware access."""
import math
import unittest
from unittest.mock import patch

import numpy as np

from algorithms import reactive_nav as nav


class GeometryTests(unittest.TestCase):
    def test_vectorized_ranger_matches_scalar_rays(self):
        _, world, _, _ = nav.scenario_slalom()
        rng = np.random.default_rng(24)
        for _ in range(30):
            pos = rng.uniform([0.1, 0.1], [4.9, 3.9])
            yaw = rng.uniform(-math.pi, math.pi)
            readings = nav.simulate_ranger(world, pos, yaw, rays_per_beam=7)
            for name, direction in nav.BEAM_DIRS_BODY.items():
                base = math.atan2(direction[1], direction[0]) + yaw
                expected = nav.BEAM_MAX_RANGE
                for off in np.linspace(-math.radians(13.5), math.radians(13.5), 7):
                    ray = np.array([math.cos(base + off), math.sin(base + off)])
                    for rect in world.all_rects():
                        expected = min(expected, nav._ray_rect(pos, ray, rect))
                self.assertAlmostEqual(readings[name], expected, places=10)

    def test_continuous_cone_detects_object_between_sampled_rays(self):
        world = nav.SimWorld([0, 0], [5, 4], [nav.Rect([2, 2.035], [2.01, 2.04])])
        exact = nav.simulate_ranger(world, [1, 2], 0)['front']
        sampled = nav.simulate_ranger(world, [1, 2], 0, rays_per_beam=7)['front']
        self.assertAlmostEqual(exact, math.hypot(1, .035))
        self.assertGreater(sampled, 3)

    def test_continuous_cones_match_dense_sampling(self):
        _, world, _, _ = nav.scenario_slalom()
        rng = np.random.default_rng(81)
        for _ in range(20):
            pos, yaw = rng.uniform([.1, .1], [4.9, 3.9]), rng.uniform(-math.pi, math.pi)
            exact = nav.simulate_ranger(world, pos, yaw)
            dense = nav.simulate_ranger(world, pos, yaw, rays_per_beam=2001)
            for name in exact:
                self.assertLessEqual(exact[name], dense[name] + 1e-10)
                self.assertAlmostEqual(exact[name], dense[name], delta=.002)

    def test_blind_corner_still_counts_as_collision(self):
        world = nav.SimWorld([0, 0], [4, 4], [nav.Rect([1.05, 1.05], [1.1, 1.1])])
        self.assertGreater(min(nav.simulate_ranger(world, [1, 1], 0).values()), 0.9)
        log = nav.simulate(world, [1, 1], [3, 3])
        self.assertTrue(log['collided'])
        self.assertFalse(log['arrived'])
        self.assertLess(log['min_clearance'], 0)

    def test_swept_clearance_detects_thin_obstacle_and_corner(self):
        world = nav.SimWorld([0, 0], [4, 4], [nav.Rect([2, 1], [2.01, 2])])
        self.assertEqual(world.segment_clearance([1, 1.5], [3, 1.5]), 0)
        self.assertAlmostEqual(world.segment_clearance([1, 0.95], [3, 0.95]), 0.05)
        self.assertAlmostEqual(world.clearance([1.97, 0.96]), 0.05)

    def test_collision_takes_precedence_over_arrival(self):
        world = nav.SimWorld([0, 0], [4, 4])
        log = nav.simulate(world, [0.05, 2], [0.05, 2])
        self.assertTrue(log['collided'])
        self.assertFalse(log['arrived'])

    def test_invalid_simulation_parameters(self):
        world = nav.SimWorld([0, 0], [4, 4])
        for kwargs in ({'dt': 0}, {'tau': -1}, {'t_limit': 0}, {'sensor_delay': -1},
                       {'dt': math.nan}, {'t_limit': math.inf}, {'initial_yaw': math.nan}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                nav.simulate(world, [1, 1], [3, 3], **kwargs)

    def test_exact_displacement_and_terminal_sample(self):
        class ConstantController:
            SEEK, ESCAPE, ARRIVED = 'seek', 'escape', 'arrived'

            def __init__(self, goal, gains):
                self.goal, self.state = np.array(goal), self.SEEK

            def step(self, *args, **kwargs):
                return np.array([.3, 0]), 0, self.SEEK

        world = nav.SimWorld([0, 0], [5, 4])
        with patch.object(nav, 'ReactiveController', ConstantController):
            log = nav.simulate(world, [1, 2], [4, 2], dt=.13, tau=.25, t_limit=.5)
        expected = .3 * (.5 - .25 * (1 - math.exp(-.5 / .25)))
        self.assertAlmostEqual(log['pos'][-1, 0], 1 + expected)
        self.assertEqual(log['t'][-1], .5)
        self.assertEqual(log['duration'], .5)
        self.assertAlmostEqual(log['path_length'], expected)


class NavigationTests(unittest.TestCase):
    def test_shortcuts_cannot_clip_blocked_grid_corners(self):
        planner = nav.SensorMapPlanner(np.array([1., 1.]), nav.Gains())
        planner.origin = np.zeros(2)
        blocked = np.zeros((5, 5), dtype=bool)
        blocked[0, 1] = True
        self.assertFalse(planner._line_clear(np.array([0., 0.]), np.array([.2, .2]), blocked))
        self.assertTrue(planner._line_clear(np.array([0., 0.]), np.array([.2, 0.]), blocked))

    def test_mapping_waits_for_blind_wedges_to_be_observed(self):
        controller = nav.ReactiveController([3, 3])
        command, yaw_rate, state = controller.step(dict.fromkeys(nav.BEAM_DIRS_BODY, 4.), [1, 1], 0, .05)
        np.testing.assert_array_equal(command, [0, 0])
        self.assertGreater(yaw_rate, 0)
        self.assertNotEqual(state, nav.ReactiveController.ARRIVED)

    def test_mapping_arrival_requires_settled_velocity(self):
        controller = nav.ReactiveController([1, 1])
        _, _, state = controller.step({}, [1, 1], 0, .05, vel=[.2, 0])
        self.assertNotEqual(state, nav.ReactiveController.ARRIVED)
        _, _, state = controller.step({}, [1, 1], 0, .05, vel=[.01, 0])
        self.assertEqual(state, nav.ReactiveController.ARRIVED)

    def test_delayed_scan_uses_its_acquisition_position(self):
        controller = nav.ReactiveController([3, 2])
        controller.step({'front': 1.}, [1.5, 2], 0, .05, sensor_pos=np.array([1., 2.]))
        grid = controller._planner
        self.assertTrue(grid.obstacles[grid._cell(np.array([2., 2.]))])
        self.assertFalse(grid.obstacles[grid._cell(np.array([2.5, 2.]))])

    def test_concave_layout_efficiency(self):
        _, world, start, goal = nav.scenario_pocket()
        log = nav.simulate(world, start, goal)
        self.assertTrue(log['arrived'])
        self.assertFalse(log['collided'])
        self.assertLess(log['duration'], 35)
        self.assertLess(log['path_length'], 8)

    def test_mapping_with_lag_and_delayed_sensors(self):
        for name in ('slalom', 'pocket'):
            with self.subTest(name=name):
                _, world, start, goal = nav.SCENARIOS[name]()
                log = nav.simulate(world, start, goal, dt=1/15, tau=.75,
                                   sensor_delay=.2, initial_yaw=.8)
                self.assertTrue(log['arrived'])
                self.assertFalse(log['collided'])

    def test_thin_wall_and_narrow_passage(self):
        layouts = [
            [nav.Rect([2, 1.1], [2.01, 2.9])],
            [nav.Rect([2, 0], [2.3, 1.7]), nav.Rect([2, 2.3], [2.3, 4])],
        ]
        for obstacles in layouts:
            with self.subTest(obstacles=obstacles):
                world = nav.SimWorld([0, 0], [5, 4], obstacles)
                log = nav.simulate(world, [.5, 2], [4.5, 2])
                self.assertTrue(log['arrived'])
                self.assertFalse(log['collided'])
                self.assertLess(log['duration'], 30)

    def test_unreachable_goal_does_not_report_success_or_cross_wall(self):
        world = nav.SimWorld([0, 0], [5, 4], [nav.Rect([2, 0], [2.3, 4])])
        log = nav.simulate(world, [.5, 2], [4.5, 2], t_limit=20)
        self.assertFalse(log['arrived'])
        self.assertFalse(log['collided'])
        self.assertEqual(log['duration'], 20)

    def test_missing_and_invalid_scans_do_not_mark_unknown_space_free(self):
        controller = nav.ReactiveController([3, 2])
        command, _, _ = controller.step({'front': None, 'back': math.nan,
                                        'left': -1, 'right': 0}, [1, 2], 0, .05)
        self.assertFalse(controller._planner.free.any())
        self.assertFalse(controller._planner.trail)
        np.testing.assert_array_equal(command, [0, 0])

    def test_new_obstacle_evidence_allows_retreat_from_inflated_cell(self):
        # Seed 7, layout 68: a cone handover at a corner used to permanently
        # mark the current cell unsafe, prohibiting every possible command.
        from dev_scripts.benchmark_reactive_nav import layouts
        world, start, goal = list(layouts(69, 7))[-1]
        log = nav.simulate(world, start, goal, t_limit=60)
        self.assertTrue(log['arrived'])
        self.assertFalse(log['collided'])
        self.assertGreater(log['min_clearance'], .04)

    def test_small_range_noise_does_not_create_cruise_speed_reversals(self):
        gains = nav.Gains.flight()
        gains.cmd_smooth = 1.0
        gains.cmd_accel = math.inf
        gains.range_median = 1
        balance = 1.0 / (1.0 / gains.d_influence + gains.k_attract / gains.k_repel)
        controller = nav.ReactiveController([5, 0], gains)
        commands = [controller.step({'front': balance + offset}, [0, 0], 0, 1/15)[0]
                    for offset in [-.005, .005] * 10]
        self.assertLess(max(np.linalg.norm(v) for v in commands), .02)

    def test_command_slew_limit_uses_elapsed_time(self):
        gains = nav.Gains.flight()
        controller = nav.ReactiveController([5, 0], gains)
        previous = np.zeros(2)
        for dt in [.04, .08, .06, .1] * 5:
            controller.goal *= -1
            command, _, _ = controller.step({}, [0, 0], 0, dt)
            self.assertLessEqual(np.linalg.norm(command - previous), gains.cmd_accel * dt + 1e-12)
            previous = command

    def test_close_return_bypasses_median_and_comfort_filter(self):
        gains = nav.Gains.flight()
        controller = nav.ReactiveController([5, 0], gains)
        for _ in range(10):
            controller.step({'front': 4.0}, [0, 0], 0, 1/15)
        command, _, _ = controller.step({'front': .18}, [0, 0], 0, 1/15)
        self.assertLess(command[0], 0)

    def test_command_filter_is_consistent_across_loop_rates(self):
        gains = nav.Gains.flight()
        gains.cmd_accel = math.inf
        commands = []
        for steps, dt in [(3, 1/15), (6, 1/30)]:
            controller = nav.ReactiveController([5, 0], gains)
            for _ in range(steps):
                command, _, _ = controller.step({}, [0, 0], 0, dt)
            commands.append(command)
        np.testing.assert_allclose(commands[0], commands[1], atol=1e-12)

    def test_closing_speed_bound_overrides_lagging_command(self):
        gains = nav.Gains.flight()
        controller = nav.ReactiveController([5, 0], gains)
        for _ in range(10):
            controller.step({'front': 4.0}, [0, 0], 0, 1/15)
        command, _, _ = controller.step({'front': .31}, [0, 0], 0, 1/15)
        self.assertLessEqual(command[0], (.31 - gains.d_panic) / gains.brake_time + 1e-12)

    def test_fixed_scenarios_both_profiles(self):
        for profile, gains in [('sim', nav.Gains()), ('flight', nav.Gains.flight())]:
            for name, make in nav.SCENARIOS.items():
                with self.subTest(profile=profile, scenario=name):
                    _, world, start, goal = make()
                    log = nav.simulate(world, start, goal, gains)
                    self.assertTrue(log['arrived'], f"{profile}/{name} failed to arrive")
                    self.assertFalse(log['collided'])
                    self.assertGreater(log['min_clearance'], 0)


if __name__ == '__main__':
    unittest.main()
