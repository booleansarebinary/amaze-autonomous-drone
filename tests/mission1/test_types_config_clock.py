"""Foundation contracts; no future controller or perception decisions."""
import math
import unittest

from mission1.clock import FakeClock
from mission1.config import DEFAULT_CONFIG, MissionConfig, PhysicalConfig
from mission1.types import Command, DroneState, RangeOutcome, RangeReading


class ClockConfigTests(unittest.TestCase):
    def test_clock_is_injected_and_repeatable(self):
        clock = FakeClock(initial_s=10.)
        self.assertEqual(clock.now_s(), 10.)
        clock.advance_s(.25)
        self.assertEqual(clock.now_s(), 10.25)
        clock.advance_s(0.)
        self.assertEqual(clock.now_s(), 10.25)

    def test_clock_rejects_reverse_and_nonfinite_time(self):
        for bad in (-1., math.nan, math.inf, -math.inf):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                FakeClock(initial_s=bad)
            clock = FakeClock(initial_s=5.)
            with self.subTest(delta=bad), self.assertRaises(ValueError):
                clock.advance_s(bad)
            self.assertEqual(clock.now_s(), 5.)

    def test_defaults_carry_proposed_physical_provenance(self):
        self.assertEqual(DEFAULT_CONFIG.physical.status, "PROPOSED")
        self.assertIn("Stage A", DEFAULT_CONFIG.physical.measurement_reference)
        self.assertEqual(DEFAULT_CONFIG.output_dir, "mission_runs")
        self.assertGreater(DEFAULT_CONFIG.queue_capacity, 0)
        self.assertGreater(DEFAULT_CONFIG.shutdown_timeout_s, 0.)

    def test_config_rejects_invalid_limits(self):
        for bad in (0., -1., math.nan, math.inf):
            with self.subTest(height=bad), self.assertRaises(ValueError):
                PhysicalConfig(flight_height_m=bad)
            with self.subTest(timeout=bad), self.assertRaises(ValueError):
                MissionConfig(shutdown_timeout_s=bad)
        for bad in (0, -1):
            with self.subTest(capacity=bad), self.assertRaises(ValueError):
                MissionConfig(queue_capacity=bad)


class TypedRecordTests(unittest.TestCase):
    def state(self, **changes):
        values = dict(monotonic_s=2., pos_world_m=(1., 2., .4),
                      vel_world_mps=(.1, .2, 0.), yaw_rad=math.pi / 2,
                      roll_rad=0., pitch_rad=0., battery_v=None,
                      device_timestamp_ms=600)
        values.update(changes)
        return DroneState(**values)

    def test_named_frames_and_timestamp_domains_preserved(self):
        state = self.state()
        self.assertEqual(state.pos_world_m, (1., 2., .4))
        self.assertEqual(state.vel_world_mps, (.1, .2, 0.))
        self.assertEqual(state.monotonic_s, 2.)
        self.assertEqual(state.device_timestamp_ms, 600)
        self.assertIsNone(state.battery_v)
        command = Command(vel_body_mps=(.2, -.1, 0.), yaw_rate_radps=.5)
        self.assertEqual(command.vel_body_mps, (.2, -.1, 0.))
        self.assertEqual(command.yaw_rate_radps, .5)

    def test_command_and_state_reject_nonfinite(self):
        for bad in (math.nan, math.inf, -math.inf):
            with self.subTest(state=bad), self.assertRaises(ValueError):
                self.state(yaw_rad=bad)
            with self.subTest(position=bad), self.assertRaises(ValueError):
                self.state(pos_world_m=(bad, 0., 0.))
            with self.subTest(command=bad), self.assertRaises(ValueError):
                Command(vel_body_mps=(0., bad, 0.), yaw_rate_radps=0.)
            with self.subTest(yawrate=bad), self.assertRaises(ValueError):
                Command(vel_body_mps=(0., 0., 0.), yaw_rate_radps=bad)

    def test_range_outcomes_remain_distinct(self):
        hit = RangeReading(beam="left", monotonic_s=3., outcome=RangeOutcome.HIT,
                           distance_m=.75, reason="valid", device_timestamp_ms=17,
                           received_monotonic_ns=3_000_000_000)
        empty = RangeReading(beam="front", monotonic_s=3., outcome=RangeOutcome.NO_RETURN,
                             distance_m=None, reason="trustworthy no return")
        invalid = RangeReading(beam="front", monotonic_s=3., outcome=RangeOutcome.INVALID,
                               distance_m=None, reason="dropout")
        self.assertEqual(hit.distance_m, .75)
        self.assertEqual(hit.device_timestamp_ms, 17)
        self.assertEqual(hit.received_monotonic_ns, 3_000_000_000)
        self.assertNotEqual(empty.outcome, invalid.outcome)
        self.assertIsNone(empty.distance_m)
        self.assertIsNone(invalid.distance_m)
        self.assertEqual(invalid.reason, "dropout")

    def test_range_requires_consistent_distance_and_reason(self):
        for bad in (None, 0., -1., math.nan, math.inf):
            with self.subTest(hit=bad), self.assertRaises(ValueError):
                RangeReading("left", 0., RangeOutcome.HIT, bad, "valid")
        for outcome in (RangeOutcome.NO_RETURN, RangeOutcome.INVALID):
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                RangeReading("left", 0., outcome, 1., "not a hit")
            with self.subTest(reason=outcome), self.assertRaises(ValueError):
                RangeReading("left", 0., outcome, None, "")

    def test_range_rejects_invalid_timestamp_and_unknown_beam(self):
        for bad in (-1., math.nan, math.inf):
            with self.subTest(time=bad), self.assertRaises(ValueError):
                RangeReading("left", bad, RangeOutcome.HIT, .5, "valid")
        with self.assertRaises(ValueError):
            RangeReading("unknown", 0., RangeOutcome.HIT, .5, "valid")
        with self.assertRaises(ValueError):
            RangeReading("left", 0., RangeOutcome.HIT, .5, "valid",
                         received_monotonic_ns=-1)
