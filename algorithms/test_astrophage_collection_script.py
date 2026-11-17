"""Grid-point conversion tests for the team lead's mission script; no hardware."""

import unittest
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


if __name__ == "__main__":
    unittest.main()
