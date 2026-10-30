"""Importable logger interface for assertion-level red tests."""
from dataclasses import dataclass
from pathlib import Path
from .types import Outcome

@dataclass(frozen=True)
class LoggerHealth:
    accepted_records: int = 0
    written_records: int = 0
    dropped_records: int = 0
    rejected_records: int = 0
    write_errors: int = 0
    last_error: str | None = None
    closed: bool = False
    writer_alive: bool = False

class MissionLogger:
    def __init__(self, output_dir, metadata, *, clock, utc_now, run_id_factory,
                 queue_capacity, opener=open, shutdown_timeout_s=2.0):
        self.run_id = run_id_factory()
        self.path = Path(output_dir) / ("mission1-" + self.run_id + ".jsonl")
        self._sink = opener(self.path, "x", encoding="utf-8")

    def record(self, record_type, payload):
        return Outcome(False, "red-test interface")

    def health(self):
        return LoggerHealth()

    def close(self):
        self._sink.close()
        return LoggerHealth(closed=True)

