"""Deterministic fixtures for the Mission 1 foundation contract."""
import json
from datetime import datetime, timezone

UTC = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)


def metadata():
    return {
        "software_commit": "fixture-commit",
        "mode": "sim",
        "controller_parameters": {},
        "planner_parameters": {},
        "safety_parameters": {},
        "frame_conventions": {"body": "+x forward,+y left", "world_local": "home origin"},
        "unit_conventions": {"distance": "m", "angle": "rad", "time": "s"},
        "arena_dimensions_m": [4.0, 4.0],
        "schema_version": 1,
        "radio_uri_redacted": None,
        "firmware_version": None,
        "deck_versions": None,
        "library_versions": {"cflib": "not imported"},
        "planner_method": None,
        "baseline_name": None,
        "unavailable_reasons": {
            "radio_uri_redacted": "simulation",
            "firmware_version": "no aircraft",
            "deck_versions": "no aircraft",
            "planner_method": "foundation fixture",
            "baseline_name": "not baseline",
        },
    }


def strict_loads(value):
    def reject_constant(constant):
        raise ValueError("non-standard JSON number: " + constant)
    return json.loads(value, parse_constant=reject_constant)


def row(record_type, sequence, **payload):
    return {
        "type": record_type,
        "run_id": "fixture-run",
        "sequence": sequence,
        "monotonic_s": float(sequence),
        "utc": UTC.isoformat(),
        **payload,
    }


def metadata_row():
    return row("metadata", 0, **metadata())
