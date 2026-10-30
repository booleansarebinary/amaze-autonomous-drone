"""Design §12: durable strict records and nonblocking, observable failures."""
import io
import json
import math
from pathlib import Path
import tempfile
import threading
import unittest

from mission1.clock import FakeClock
from mission1.mission_log import MissionLogger
from support import UTC, metadata, strict_loads


class ControlledSink(io.StringIO):
    """Hold only a sample write; metadata can finish without wall-time sleeps."""
    def __init__(self, *, fail=False):
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.metadata_written = threading.Event()
        self.fail = fail
        self.saved = ""

    def write(self, value):
        if '"sample"' in value:
            self.entered.set()
            if not self.release.wait(5.):
                raise OSError("fixture gate not released")
            if self.fail:
                raise OSError("fixture disk failure")
        result = super().write(value)
        if '"metadata"' in value:
            self.metadata_written.set()
        return result

    def close(self):
        if not self.closed:
            self.saved = self.getvalue()
        super().close()


class MissionLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock(initial_s=100.)

    def logger(self, **changes):
        options = dict(clock=self.clock, utc_now=lambda: UTC,
                       run_id_factory=lambda: "fixture-run", queue_capacity=32)
        options.update(changes)
        result = MissionLogger(Path(self.tmp.name), metadata(), **options)
        self.addCleanup(result.close)
        return result

    def read(self, logger):
        return [strict_loads(line) for line in logger.path.read_text(encoding="utf-8").splitlines()]

    def test_metadata_first_and_all_record_types_preserved(self):
        logger = self.logger()
        payloads = {
            "sample": {"requested_command": {"vx": .1}, "final_command": {"vx": 0.},
                       "host_call_returned": True, "observed_state": {"x": 1.},
                       "device_timestamp_ms": 12},
            "colony_event": {"event": "candidate_created", "colony_id": "c1"},
            "planner_decision": {"chosen": "return", "reason": "energy", "options": []},
            "safety_event": {"reason": "clearance", "requested": .1, "final": 0.},
            "map_snapshot": {"cells": [], "colonies": []},
            "event": {"event": "shutdown", "reason": "operator"},
            "summary": {"score": 0., "passed": True},
        }
        for kind, payload in payloads.items():
            self.clock.advance_s(.25)
            outcome = logger.record(kind, payload)
            self.assertTrue(outcome.accepted, outcome.reason)
        health = logger.close()
        rows = self.read(logger)
        self.assertEqual([row["type"] for row in rows], ["metadata", *payloads])
        self.assertEqual([row["sequence"] for row in rows], list(range(8)))
        self.assertTrue(all(row["run_id"] == logger.run_id for row in rows))
        self.assertEqual(rows[0]["software_commit"], "fixture-commit")
        self.assertEqual(rows[0]["safety_parameters"], {})
        self.assertEqual(rows[1]["requested_command"], {"vx": .1})
        self.assertEqual(rows[1]["final_command"], {"vx": 0.})
        self.assertEqual(rows[1]["observed_state"], {"x": 1.})
        self.assertEqual(rows[1]["device_timestamp_ms"], 12)
        self.assertEqual(rows[1]["monotonic_s"], 100.25)
        self.assertEqual(health.written_records, 8)
        self.assertFalse(health.writer_alive)

    def test_explicit_null_with_reason_is_preserved(self):
        logger = self.logger()
        outcome = logger.record("sample", {"battery_v": None,
                                "unavailable_reasons": {"battery_v": "no sample"}})
        self.assertTrue(outcome.accepted, outcome.reason)
        logger.close()
        sample = self.read(logger)[1]
        self.assertIsNone(sample["battery_v"])
        self.assertEqual(sample["unavailable_reasons"]["battery_v"], "no sample")

    def test_nested_nonfinite_rejected_with_reason_and_counter(self):
        logger = self.logger()
        for bad in (math.nan, math.inf, -math.inf):
            outcome = logger.record("sample", {"nested": [{"range_m": bad}]})
            self.assertFalse(outcome.accepted)
            self.assertTrue(outcome.reason)
        self.assertEqual(logger.health().rejected_records, 3)
        logger.close()
        self.assertEqual(len(self.read(logger)), 1)

    def test_reserved_envelope_fields_cannot_be_overwritten(self):
        logger = self.logger()
        for reserved in ("type", "run_id", "sequence", "monotonic_s", "utc"):
            with self.subTest(reserved=reserved):
                outcome = logger.record("event", {reserved: "forged"})
                self.assertFalse(outcome.accepted)
                self.assertTrue(outcome.reason)
        logger.close()
        self.assertEqual(len(self.read(logger)), 1)

    def test_exclusive_creation_never_overwrites_existing_run(self):
        logger = self.logger()
        logger.close()
        before = logger.path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.logger()
        self.assertEqual(logger.path.read_bytes(), before)

    def test_output_name_and_supplied_unique_run_ids(self):
        first = self.logger(run_id_factory=lambda: "first")
        second = self.logger(run_id_factory=lambda: "second")
        first.close()
        second.close()
        self.assertNotEqual(first.path, second.path)
        self.assertTrue(first.path.name.startswith("mission1-"))
        self.assertEqual(first.path.suffix, ".jsonl")

    def test_queue_full_does_not_wait_for_disk_and_counts_drop(self):
        sink = ControlledSink()
        logger = self.logger(queue_capacity=1, opener=lambda *args, **kwargs: sink)
        self.addCleanup(sink.release.set)
        self.assertTrue(sink.metadata_written.wait(5.), "metadata was not written")
        self.assertTrue(logger.record("sample", {"number": 1}).accepted)
        self.assertTrue(sink.entered.wait(5.), "writer did not reach injected gate")
        outcome = {}
        done = threading.Event()
        def enqueue():
            outcome["queued"] = logger.record("event", {"number": 2})
            outcome["full"] = logger.record("event", {"number": 3})
            done.set()
        producer = threading.Thread(target=enqueue, daemon=True)
        try:
            producer.start()
            self.assertTrue(done.wait(5.), "enqueue waited for a blocked disk writer")
            self.assertTrue(outcome["queued"].accepted)
            self.assertFalse(outcome["full"].accepted)
            self.assertTrue(outcome["full"].reason)
            self.assertEqual(logger.health().dropped_records, 1)
        finally:
            sink.release.set()
            producer.join(5.)
            logger.close()

    def test_mutable_payload_is_snapshotted_before_writer_uses_it(self):
        sink = ControlledSink()
        logger = self.logger(opener=lambda *args, **kwargs: sink)
        self.addCleanup(sink.release.set)
        self.assertTrue(sink.metadata_written.wait(5.))
        self.assertTrue(logger.record("sample", {"gate": True}).accepted)
        self.assertTrue(sink.entered.wait(5.))
        payload = {"positions": [1., 2.]}
        self.assertTrue(logger.record("event", payload).accepted)
        payload["positions"][0] = 99.
        sink.release.set()
        logger.close()
        rows = [strict_loads(line) for line in sink.saved.splitlines()]
        self.assertEqual(rows[-1]["positions"], [1., 2.])

    def test_write_failure_surfaces_in_health_and_cleanly_closes(self):
        sink = ControlledSink(fail=True)
        logger = self.logger(opener=lambda *args, **kwargs: sink)
        self.addCleanup(sink.release.set)
        self.assertTrue(sink.metadata_written.wait(5.))
        self.assertTrue(logger.record("sample", {"test": "write failure"}).accepted)
        self.assertTrue(sink.entered.wait(5.))
        sink.release.set()
        health = logger.close()
        self.assertGreaterEqual(health.write_errors, 1)
        self.assertTrue(health.last_error)
        self.assertTrue(health.closed)
        self.assertFalse(health.writer_alive)

    def test_close_is_idempotent_and_later_records_are_rejected(self):
        logger = self.logger()
        first = logger.close()
        second = logger.close()
        self.assertEqual(first.written_records, second.written_records)
        self.assertTrue(second.closed)
        self.assertFalse(second.writer_alive)
        outcome = logger.record("event", {"event": "too late"})
        self.assertFalse(outcome.accepted)
        self.assertTrue(outcome.reason)
