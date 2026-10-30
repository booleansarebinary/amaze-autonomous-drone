"""Importable exporter interface for assertion-level red tests."""
from dataclasses import dataclass
import json
import os
from pathlib import Path

@dataclass(frozen=True)
class ExportReport:
    records_written: int
    skipped_lines: tuple[int, ...]
    truncated_lines: tuple[int, ...]
    reasons: tuple[str, ...]
    output_path: Path

def export_run(input_path, output_path):
    destination = Path(output_path)
    destination.write_text(json.dumps({"schema_version": 1, "records": []}), encoding="utf-8")
    return ExportReport(0, (), (), (), destination)

