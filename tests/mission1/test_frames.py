"""Design §10: independent hand-computed coordinate and unit fixtures."""
import math
import random
import unittest

from mission1.frames import (
    arena_to_world_xy, beam_direction_body, body_to_world_xy,
    degrees_to_radians, mm_to_m, radians_to_degrees,
    world_to_arena_xy, world_to_body_xy,
)


class FrameTests(unittest.TestCase):
    def assertVector(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for value, wanted in zip(actual, expected):
            self.assertAlmostEqual(value, wanted, places=12)

    def test_four_beams_at_four_yaws_match_hand_fixtures(self):
        beams = ((1., 0.), (-1., 0.), (0., 1.), (0., -1.))
        fixtures = (
            (0., ((1., 0.), (-1., 0.), (0., 1.), (0., -1.))),
            (math.pi / 2, ((0., 1.), (0., -1.), (-1., 0.), (1., 0.))),
            (-math.pi / 2, ((0., -1.), (0., 1.), (1., 0.), (-1., 0.))),
            (math.pi, ((-1., 0.), (1., 0.), (0., -1.), (0., 1.))),
        )
        for yaw, expected in fixtures:
            for beam, wanted in zip(beams, expected):
                with self.subTest(yaw=yaw, beam=beam):
                    self.assertVector(body_to_world_xy(beam, yaw), wanted)

    def test_fixed_sensor_axes(self):
        expected = {
            "front": (1., 0., 0.), "back": (-1., 0., 0.),
            "left": (0., 1., 0.), "right": (0., -1., 0.),
            "up": (0., 0., 1.), "down": (0., 0., -1.),
        }
        for beam, direction in expected.items():
            with self.subTest(beam=beam):
                self.assertVector(beam_direction_body(beam), direction)
        with self.assertRaises(ValueError):
            beam_direction_body("unknown")

    def test_world_to_body_hand_fixture(self):
        self.assertVector(world_to_body_xy((0., 2.), math.pi / 2), (2., 0.))

    def test_arena_transform_includes_translation(self):
        self.assertVector(arena_to_world_xy((2., 1.), (10., -3.), math.pi / 2), (9., -1.))
        self.assertVector(world_to_arena_xy((9., -1.), (10., -3.), math.pi / 2), (2., 1.))

    def test_seeded_rotation_inverse_and_norm(self):
        rng = random.Random(12491)
        for _ in range(100):
            value = (rng.uniform(-5., 5.), rng.uniform(-5., 5.))
            yaw = rng.uniform(-4. * math.pi, 4. * math.pi)
            world = body_to_world_xy(value, yaw)
            self.assertVector(world_to_body_xy(world, yaw), value)
            self.assertAlmostEqual(math.hypot(*world), math.hypot(*value), places=12)

    def test_units(self):
        self.assertEqual(mm_to_m(1250.), 1.25)
        self.assertEqual(mm_to_m(0.), 0.)
        self.assertAlmostEqual(degrees_to_radians(180.), math.pi, places=12)
        self.assertAlmostEqual(radians_to_degrees(-math.pi / 2), -90., places=12)

    def test_nonfinite_inputs_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            for convert in (mm_to_m, degrees_to_radians, radians_to_degrees):
                with self.subTest(convert=convert.__name__, bad=bad), self.assertRaises(ValueError):
                    convert(bad)
            for convert in (body_to_world_xy, world_to_body_xy):
                with self.subTest(convert=convert.__name__, field="yaw"), self.assertRaises(ValueError):
                    convert((1., 0.), bad)
                with self.subTest(convert=convert.__name__, field="vector"), self.assertRaises(ValueError):
                    convert((bad, 0.), 0.)
