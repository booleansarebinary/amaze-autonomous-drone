"""Offline controller regression tests; no radio drivers or hardware required."""

import importlib.util
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch


def load_controller():
    path = Path(__file__).resolve().parents[1] / 'algorithms' / 'orbit_reactive.py'
    spec = importlib.util.spec_from_file_location('orbit_reactive_under_test', path)
    module = importlib.util.module_from_spec(spec)
    # Stub only hardware imports; execute the actual controller unchanged.
    names = ('cflib', 'cflib.crtp', 'cflib.crazyflie',
             'cflib.crazyflie.syncCrazyflie', 'cflib.crazyflie.log', 'cflib.utils')
    with patch.dict(sys.modules, {name: MagicMock() for name in names}):
        spec.loader.exec_module(module)
    return module


orbit = load_controller()


def ranges(**values):
    return dict.fromkeys(orbit.SENSOR_DIRECTIONS) | values


class OrbitTests(unittest.TestCase):
    def test_raw_millimeters_are_detected(self):
        orbit._range_callback(0, {'range.front': 500, 'range.back': 8000,
                                 'range.left': 0, 'range.right': 65535}, None)
        sample = orbit.read_ranges()
        self.assertEqual(sample, ranges(front=0.5))
        vx, vy, yaw = orbit.OrbitController().command(sample, 0.0)
        self.assertAlmostEqual(vx, 0.0)
        self.assertGreater(vy, 0.0)
        self.assertLess(yaw, 0.0)

    def test_missing_fields_clear_old_readings(self):
        orbit._range_callback(0, {'range.front': 500}, None)
        orbit._range_callback(1, {}, None)
        self.assertEqual(orbit.read_ranges(), ranges())

    def test_stale_telemetry_is_rejected(self):
        with patch.object(orbit.time, 'monotonic', return_value=1.0):
            orbit._range_callback(0, {'range.front': 500}, None)
        with patch.object(orbit.time, 'monotonic', return_value=2.0):
            with self.assertRaises(RuntimeError):
                orbit.read_ranges()

    def test_acquisition_distance_and_timeout(self):
        controller = orbit.OrbitController()
        self.assertEqual(controller.command(ranges(front=1.1), 0.0),
                         (0.0, 0.0, orbit.SEARCH_YAW_RATE))
        self.assertIsNone(controller.command(ranges(), orbit.SEARCH_TIMEOUT))
        controller = orbit.OrbitController()
        controller.command(ranges(front=orbit.DETECTION_DISTANCE), 0.0)
        self.assertEqual(controller.target_sensor, 'front')

    def test_target_lock_and_tracking_outside_acquisition_distance(self):
        controller = orbit.OrbitController()
        controller.command(ranges(front=0.8, left=0.9), 0.0)
        cmd = controller.command(ranges(front=1.2, left=0.3), 0.1)
        self.assertEqual(controller.target_sensor, 'front')
        self.assertGreater(cmd[0], 0.0)

    def test_loss_hovers_then_searches_and_reacquires(self):
        controller = orbit.OrbitController()
        controller.command(ranges(front=0.5), 0.0)
        self.assertEqual(controller.command(ranges(left=0.4), 0.1), (0, 0, 0))
        self.assertEqual(controller.command(ranges(), 0.6),
                         (0, 0, orbit.SEARCH_YAW_RATE))
        controller.command(ranges(left=0.4), 0.7)
        self.assertEqual(controller.target_sensor, 'left')

    def test_radial_correction_and_limits_for_all_sensors(self):
        for sensor, (dx, dy) in orbit.SENSOR_DIRECTIONS.items():
            for distance in (0.06, 0.3, 0.5, 0.9):
                with self.subTest(sensor=sensor, distance=distance):
                    vx, vy, yaw = orbit.OrbitController().command(
                        ranges(**{sensor: distance}), 0.0)
                    radial = vx * dx + vy * dy
                    self.assertGreaterEqual(radial * (distance - orbit.DESIRED_STANDOFF), 0)
                    self.assertLessEqual(math.hypot(vx, vy), orbit.MAX_SPEED + 1e-12)
                    self.assertLessEqual(abs(yaw), orbit.MAX_ORBIT_YAW_RATE + 1e-12)
                    self.assertAlmostEqual(math.radians(yaw), -(-dy * vx + dx * vy) / distance)

    def test_simulated_point_target_completes_orbit(self):
        # Integrate ideal body velocities around the origin and ensure the
        # front sensor stays aimed at it, rather than spinning on the spot.
        controller = orbit.OrbitController()
        x, y, heading = -0.5, 0.0, 0.0
        dt = 0.01
        for step in range(2200):
            distance = math.hypot(x, y)
            bearing = math.atan2(-y, -x)
            error = math.atan2(math.sin(bearing - heading), math.cos(bearing - heading))
            self.assertLess(abs(error), math.radians(3))
            vx, vy, yaw = controller.command(ranges(front=distance), step * dt)
            x += (vx * math.cos(heading) - vy * math.sin(heading)) * dt
            y += (vx * math.sin(heading) + vy * math.cos(heading)) * dt
            heading += math.radians(yaw) * dt
        self.assertLess(heading, -2 * math.pi)
        self.assertAlmostEqual(math.hypot(x, y), 0.5, delta=0.02)

    def test_stale_ranges_stop_motion_in_flight_loop(self):
        cf = MagicMock()
        with patch.object(orbit, 'read_ranges', side_effect=RuntimeError('stale')):
            orbit.run_orbit(cf, 1.0)
        cf.commander.send_hover_setpoint.assert_called_once_with(0, 0, 0, orbit.FLIGHT_HEIGHT)


if __name__ == '__main__':
    unittest.main()
