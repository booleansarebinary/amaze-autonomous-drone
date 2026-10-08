"""Simulation regressions; no radio or hardware access."""
import math
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from algorithms import reactive_nav as nav


class GeometryTests(unittest.TestCase):
    def test_vectorized_ranger_matches_scalar_rays(self):
        _, world, _, _ = nav.scenario_slalom()
        rng = np.random.default_rng(24)
        for _ in range(30):
            pos = rng.uniform([0.1, 0.1], [4.9, 3.9])
            yaw = rng.uniform(-math.pi, math.pi)
            readings = nav.simulate_ranger(world, pos, yaw)
            for name, direction in nav.BEAM_DIRS_BODY.items():
                base = math.atan2(direction[1], direction[0]) + yaw
                expected = nav.BEAM_MAX_RANGE
                for off in np.linspace(-math.radians(13.5), math.radians(13.5), 7):
                    ray = np.array([math.cos(base + off), math.sin(base + off)])
                    for rect in world.all_rects():
                        expected = min(expected, nav._ray_rect(pos, ray, rect))
                self.assertAlmostEqual(readings[name], expected, places=10)

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
        for kwargs in ({'dt': 0}, {'tau': -1}, {'t_limit': 0}, {'sensor_delay': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                nav.simulate(world, [1, 1], [3, 3], **kwargs)


class TelemetryJsonTests(unittest.TestCase):
    def test_writer_creates_timestamped_x_and_y_time_series(self):
        with TemporaryDirectory() as temporary:
            writer = nav.TelemetryJsonWriter(temporary)
            writer.record(1_700_000_000_123, 1.25, -0.5)

            directory = Path(temporary)
            x = json.loads((directory / "kalman_state_x.json").read_text())
            y = json.loads((directory / "kalman_state_y.json").read_text())

        self.assertEqual(x, [{"timestamp": 1_700_000_000_123, "value": 1.25}])
        self.assertEqual(y, [{"timestamp": 1_700_000_000_123, "value": -0.5}])


class NavigationTests(unittest.TestCase):
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
