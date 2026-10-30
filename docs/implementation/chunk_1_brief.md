# Chunk 1 brief — foundations and reproducible environment

Date: 2026-10-29. Branch: `astrophage-collection`. Approved predecessor: Chunk 0 commit `cde04f8633c511af0e7cd8ca611c13f040f022da`; pushed branch currently through `7792ac8`.

## Scope and design acceptance

Build the first mission-specific Python 3.10 Docker image and test wrapper, then implement the dependency-light foundations. Applicable design sections: §10 (frames and SI units), §12 (JSONL lifecycle/records), and §18 as superseded for development isolation by Victor's Docker rules. Victor's Chunk 1 acceptance: "Image builds from scratch with one command and tests run inside it with --network none; frame/unit fixtures exact; logger handles all record types, nulls, non-finite values, overflow, write errors, truncated final line; exporter is atomic."

Copied design criteria:

- §5.2: "Each module consumes typed, timestamped inputs and returns outputs plus a reason/status, so every decision can be logged and replayed."
- §10: "Units: meters, meters per second, radians (degrees only at the cflib boundary where required, converted explicitly and tested), seconds."
- §12.1: "JSONL during the run: one strict JSON object per line, appended in order; complete lines remain recoverable after interruption." The design also requires a unique run ID/exclusive creation, metadata first, bounded background writer, surfaced drops/errors, `allow_nan=False`, and atomic validated JSON export.
- §15: "Use Python `unittest`" and no automated test may open physical hardware.
- Docker process: digest-pinned Python 3.10 base, locked exact dependencies, one root command; `docker run --rm --network none`, repo mounted, no privileged/device/USB mounts. Preserve root Docker files.

## Ownership and files

| Role | Files/assignment |
|---|---|
| Builder | `docker/mission1/{Dockerfile,requirements.lock.txt,run.sh,snapshots/chunk_1.json}`, `.dockerignore`; `mission1/{__init__.py,config.py,types.py,frames.py,clock.py,mission_log.py}`; `tools/export_mission_json.py`; `.gitignore` mission_runs entry |
| Validator | `tests/mission1/` and fixtures: failing tests first, then full/adversarial suite and design traceability |
| Scout | Update/read `docs/implementation/scout_notes.md`; cached dependency/API evidence and focused findings for this chunk |
| Orchestrator | This brief, progress, report; independent Docker build/test, diff and ownership review, snapshot review, local chunk commit |

No cflib imports or radio access in this chunk. No other third-party dependency without Victor's approval. Existing root `Dockerfile` and `docker-compose.yml` are out of scope. All physical tunables remain `PROPOSED` with the Stage A measurement that replaces each one. Nonphysical defaults must also live in config rather than decision-code magic numbers.

## Required behavior and tests

- Pure frame/unit conversions return typed scalar/vector values, reject nonfinite or malformed inputs with `ValueError`, and match hand-computed fixtures at yaw 0, ±90°, and 180°, including raw-unit boundary conversions where interfaces are agreed. Decision-making functions return explicit outcome/reason values.
- Typed records carry named frames/units and source timestamps; clock is injectable and pure modules need no wall clock.
- Logger emits metadata first; accepts every §12 record family; serializes null/reason and finite values strictly; rejects NaN/Infinity; unique exclusive paths; bounded nonblocking enqueue with visible overflow/write errors; complete prior lines survive final-line truncation.
- Exporter validates complete JSONL records, reports skipped/truncated lines, and atomically replaces destination without leaving partial output.
- Tests demonstrate assertion-level red before implementation, not import errors. Full suite and determinism runs happen in the tagged image; no host test fallback.
- Image is reproducible from committed files; snapshot records image ID, base digest, Python, complete pip freeze, hashes, Docker/host information, and exact commands.

## Decisions recorded

Victor approved the distinct `HIT`, `NO_RETURN`, and `INVALID` range outcomes on 2026-10-29. Only a trustworthy `NO_RETURN` can clear visibility cells; missing/dropout/stale/invalid readings never prove free space. Raw sensor sentinel decoding remains unverified until Stage A and must fail closed.

For strict JSON records, implementer choice: reject NaN/Infinity and expose an explicit rejection reason/counter; intentional unavailable values are `null` with a reason. Do not silently convert corrupt numeric values to null.

## Out of scope

Simulator, perception, mapping, visibility, planning, hardware adapter, real-radio access, cflib imports, runbook commands, and physical measurements. Do not invent sentinel interpretation or claim runtime firmware/deck presence. Stop for Victor if image cannot be reproducibly built, Docker becomes unavailable, or a new dependency appears necessary.
