"""Design §12.1: strict recovery with atomic destination replacement."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.export_mission_json import export_run
from support import metadata_row, row, strict_loads


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source.jsonl"
        self.destination = Path(self.tmp.name) / "export.json"

    def write_rows(self, rows):
        self.source.write_text("".join(json.dumps(record, allow_nan=False) + "\n"
                                       for record in rows), encoding="utf-8")

    def test_exports_strict_document_in_original_record_order(self):
        records = [metadata_row(), row("event", 1, event="connected"),
                   row("summary", 2, score=0., passed=True)]
        self.write_rows(records)
        report = export_run(self.source, self.destination)
        document = strict_loads(self.destination.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["records"], records)
        self.assertEqual(report.records_written, 3)
        self.assertEqual(report.skipped_lines, ())
        self.assertEqual(report.truncated_lines, ())

    def test_reports_malformed_and_truncated_lines_and_recovers_complete_records(self):
        contents = (json.dumps(metadata_row()) + "\n"
                    + "not JSON\n"
                    + json.dumps(row("event", 1, event="ok")) + "\n"
                    + '{"type":"sample","partial":')
        self.source.write_text(contents, encoding="utf-8")
        report = export_run(self.source, self.destination)
        document = strict_loads(self.destination.read_text(encoding="utf-8"))
        self.assertEqual(report.records_written, 2)
        self.assertIn(2, report.skipped_lines)
        self.assertIn(4, report.truncated_lines)
        self.assertTrue(report.reasons)
        self.assertEqual(document["records"][-1]["event"], "ok")

    def test_nonstandard_nan_and_infinity_are_not_exported(self):
        self.source.write_text(json.dumps(metadata_row()) + "\n"
                               + json.dumps(row("sample", 1, value=float("nan"))) + "\n"
                               + json.dumps(row("sample", 2, value=float("inf"))) + "\n",
                               encoding="utf-8")
        report = export_run(self.source, self.destination)
        self.assertEqual(report.records_written, 1)
        self.assertEqual(report.skipped_lines, (2, 3))
        self.assertEqual(len(strict_loads(self.destination.read_text(encoding="utf-8"))["records"]), 1)

    def test_missing_metadata_fails_without_replacing_destination(self):
        self.write_rows([row("sample", 0, value=1.)])
        self.destination.write_text("previous export", encoding="utf-8")
        with self.assertRaises(ValueError):
            export_run(self.source, self.destination)
        self.assertEqual(self.destination.read_text(encoding="utf-8"), "previous export")

    def test_empty_input_fails_without_creating_output(self):
        self.source.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            export_run(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_failed_atomic_replace_preserves_previous_output(self):
        self.write_rows([metadata_row(), row("summary", 1, score=0.)])
        self.destination.write_text("previous export", encoding="utf-8")
        with patch("tools.export_mission_json.os.replace", side_effect=OSError("fixture replace failure")):
            with self.assertRaises(OSError):
                export_run(self.source, self.destination)
        self.assertEqual(self.destination.read_text(encoding="utf-8"), "previous export")
        self.assertEqual(set(Path(self.tmp.name).iterdir()), {self.source, self.destination})
