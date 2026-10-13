"""Focused checks for the concept controller, not hardware certification."""
import math
import unittest

from prototype import OrbitController, simulate


class OrbitTests(unittest.TestCase):
    def following_controller(self):
        controller = OrbitController()
        for _ in range(5):
            controller.step([(0.0, 0.55)], (0.0, 0.0), 0.0, 0.1)
        self.assertEqual(controller.state, "FOLLOW")
        return controller

    def test_circle_closes_lap_with_clearance(self):
        _, controller, log = simulate("circle")
        self.assertEqual(controller.state, "COMPLETE")
        self.assertGreater(min(r["clearance"] for r in log), 0.20)

    def test_box_closes_lap_with_clearance(self):
        _, controller, log = simulate("box")
        self.assertEqual(controller.state, "COMPLETE")
        self.assertGreater(min(r["clearance"] for r in log), 0.20)

    def test_empty_scene_times_out(self):
        _, controller, _ = simulate("empty")
        self.assertEqual(controller.state, "ABORT")
        self.assertEqual(controller.reason, "Mission time limit")

    def test_invalid_scan_aborts(self):
        for scan in ([], [(0.0, float("nan"))], [(0.0, -1.0)]):
            controller = OrbitController()
            self.assertEqual(controller.step(scan, (0, 0), 0, 0.1), (0.0, 0.0))
            self.assertEqual(controller.state, "ABORT")

    def test_target_loss_holds_then_aborts(self):
        controller = self.following_controller()
        velocity = controller.step([(0.0, None)], (0, 0), 0, 0.1)
        self.assertEqual(controller.state, "REACQUIRE")
        self.assertEqual(velocity, (0.0, 0.0))
        for _ in range(31):
            controller.step([(0.0, None)], (0, 0), 0, 0.1)
        self.assertEqual(controller.state, "ABORT")

    def test_rotating_without_translation_is_not_a_lap(self):
        controller = self.following_controller()
        for angle in range(5, 725, 5):
            controller.step([(math.radians(angle), 0.55)], (0, 0), 0, 0.1)
        self.assertEqual(controller.state, "FOLLOW")
        self.assertEqual(controller.travel, 0.0)

    def test_close_obstacle_aborts(self):
        controller = self.following_controller()
        velocity = controller.step([(0.0, 0.1)], (0, 0), 0, 0.1)
        self.assertEqual(velocity, (0.0, 0.0))
        self.assertEqual(controller.state, "ABORT")

    def test_abrupt_surface_change_does_not_silently_switch_targets(self):
        controller = self.following_controller()
        velocity = controller.step([(math.pi, 0.55)], (0, 0), 0, 0.1)
        self.assertEqual(controller.state, "REACQUIRE")
        self.assertEqual(velocity, (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
