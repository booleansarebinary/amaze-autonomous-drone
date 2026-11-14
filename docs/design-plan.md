# Astrophage system design and validation plan

Mission requirements are in [mission.md](mission.md). This document describes implementation choices, milestones and evidence requirements. No hardware or software implementation has been verified by creating these documents.

## Architecture and language choices

| Component | Initial implementation | Later responsibility |
|---|---|---|
| Station firmware | Sensor sampling, validity, terminal output | Versioned measurements and confirmed presence events |
| Laptop receiver | Serial parser and terminal status | Reconnection, event validation and JSON logging |
| Mission controller | Offline state-machine tests | Search, confirm, hold, collect, return, fault handling |
| Navigation | Known station coordinates and static map | A* routes, clearance-aware waypoints and replanning |
| Crazyflie adapter | Mock interface, then telemetry-only radio mode | Waypoint following and position hold |
| Dashboard | Event replay | Animation driven by authoritative collection state |

C++ firmware is the starting choice for a confirmed Arduino/ESP32-compatible board. USB serial provides the simplest first output path. Python is the proposed laptop receiver/integration language unless the repository has a stronger existing convention. A direct-interface sensor may change this choice. Board/sensor identification precedes pins, voltages, libraries and upload instructions.

Existing repository code, including Ansur's reactive algorithm, is evaluated for compatible reuse. Reactive avoidance is distinct from target selection and route planning. Component adapters separate sensor, serial, clock, radio and filesystem I/O from testable behavior.

Docker is used only where existing repository requirements justify it. The setup must account for serial/Crazyradio device access and persistent host logs; the sensor proof should not require a container redesign.

The accompanying `Dockerfile` and `compose.yml` provide an optional Python/C++ tooling scaffold. Source is copied into the image, prompt files are excluded through `.dockerignore`, and only `./logs` is bind-mounted. There is no default hardware access or mission startup. Board-specific toolchains and project dependencies remain Phase 0 decisions. See the package README for commands, limitations and local verification; merge with existing repository Docker configuration rather than replacing it blindly.

## Development phases

### Phase 0 — inspect and isolate

Repository instructions, Git history, existing algorithms, test tools, dependency management and Docker configuration establish the starting point. A clean `mission/astrophage-collection` branch and preferably a separate worktree preserve unfinished work. The hardware inventory explicitly records unknown sensor, board, voltage/interface, port, radio and localization details. Competing starting points are resolved from evidence.

Deliverables: hardware inventory, architecture/layout, supported setup commands and decision log. Mutation testing is not applicable to an inspection-only checkpoint.

### Phase 1 — sensor to terminal

**1A: Raw measurements.** A board-specific hardware adapter uses bounded measurement timeouts and a documented sampling cadence. Shared C++ validation logic is natively testable. Raw readings retain units and validity; no echo does not become a zero-distance hit. Compile/upload and serial-monitor commands match confirmed hardware.

**1B: Presence detection.** A configurable detection band, time-based confirmation and separate release/hysteresis policy distinguish persistent presence from a once-per-entry event. Invalid-data grace periods, if used, are bounded. Boundary readings, spikes, withdrawal, startup and actual timer rollover are tested. Output describes `OBJECT_PRESENT`, not identification of a drone.

A small versioned newline-delimited JSON protocol is preferred where board resources permit. Fields include station ID, boot/session ID, sequence number, device timestamp, nullable distance in millimeters, validity and presence state. Reset/wrap behavior and diagnostic record types are documented. Serial backpressure must not silently stall sampling.

**1C: Physical feasibility.** Trials progress from an empty sensor and measured flat reference targets to a motors-off Crazyflie at multiple heights/offsets, then separately operator-controlled flight. No powered drone is hand-held over the sensor. Threshold tuning and acceptance datasets are separate. Ground truth, misses, false detections, invalid data and latency are recorded, including failures. Motors-off detection does not prove in-flight performance.

Checkpoint: terminal evidence, C++ tests and mutation results, and a go/no-go/pending decision for the actual ultrasonic configuration. Missing hardware leaves the physical gate pending.

### Phase 2 — laptop link and export

The Python receiver offers terminal status, deterministic replay and bounded input buffers/queues. Validation covers split/coalesced lines, malformed/oversized payloads, types, nulls/non-finite numbers, wrong station IDs, duplicate/out-of-order sequences, resets/wraps, disconnects and stale streams. A reconnect handshake/backlog policy prevents buffered old data from appearing fresh merely because it arrived recently.

Unique JSONL run logs preserve configuration, versions, units, device time, host monotonic/wall times, readings, commands, events and errors as available. A strict JSON exporter supports replay and reports corruption; only an interrupted final record may be recovered under an explicit policy. Write failures/dropped records are visible. Normal/interrupted shutdown is tested. Generated logs are excluded from Git.

Checkpoint: reproducible receive/replay/export commands, tests/mutations, and a real serial session or explicit pending hardware status.

### Phase 3 — Crazyradio and localization

An explicitly selected telemetry-only mode connects, discovers/subscribes to available telemetry, records it and disconnects without flight API calls. Tests exercise connection failures, missing variables, stale pose, estimator readiness, link loss and cleanup at the physical adapter boundary. Configuration stays session-owned and secrets are not logged.

Home is recorded only from a fresh valid measured pose after localization is ready. An absolute return capability is not inferred from relative velocity commands or a commander's remembered target. Hardware evidence identifies coordinate frames and estimate quality.

Checkpoint: tests/mutations and an actual radio/localization capability table. Navigation depends on adequate positioning.

### Phase 4 — mission state machine offline

States cover idle/readiness, search, approach, confirmation, hold/collection, return, completion and state-dependent faults. Detection cancels travel and requests hold; settling and qualifying dwell precede collection. Station evidence is fresh and associated with the expected visit. Presence/proximity/velocity conditions remain valid throughout dwell. Animation does not authorize transitions.

Tests cover full missions, fake visits, no real target, wrong/stale/delayed/duplicate events, visit timeout, interrupted dwell, cancellation, sensor/pose/radio failures and repeated completion. One collection and one return transition occur per successful mission. Hidden real/fake ground truth cannot shortcut route selection.

Checkpoint: deterministic fake-I/O mission runs and mutations; no flight.

### Phase 5 — obstacle-aware navigation

A* is a proposed planner for a supplied static grid map; candidate ordering remains a separate simple policy. Fixed-altitude 2D routing requires a suitable operating volume. Obstacles are inflated for the footprint and justified positioning/tracking margins. Diagonal corner cutting is forbidden. Pose-to-grid connections and smoothed segments receive collision checks.

Tests include blocked/out-of-map start and goal, unreachable candidates, changed maps, no path, blocked home routes, transforms, units, waypoint arrival, command limits and stale pose. Return follows a validated route rather than reversing velocity commands. Reactive avoidance has explicit command ownership; detours can trigger replanning or pause progress.

Checkpoint: offline route evidence, tests/mutations and defined later hardware tracking checks.

### Phase 6 — progressive physical integration

Separate operator modes progress through sensor/radio telemetry without flight, controlled approach, hold at a stationary station, collection dwell, short outbound/return and full candidate search. Coding-session automation does not execute flight trials.

Logs distinguish sensor-event-to-receipt from receipt-to-command timing and acknowledge unobservable delays. Trials measure settling, overshoot, false events, stale data and intervention. Approach speed and braking clearance follow measured behavior. Competing command sources cannot continue search after hold/return takes ownership. Fault injection remains offline; airborne radio loss cannot be repaired by assuming a command can traverse a lost link.

Checkpoint: restored software, tests/mutations, measured physical evidence and unresolved operator trials. Unreliable ultrasound yields a no-go for that configuration and a targeted next experiment.

### Phase 7 — dashboard and final acceptance

The existing dashboard consumes authoritative events with mission/run IDs and unique event IDs. Animation occurs once after confirmed collection. Duplicate, reordered, replayed and reconnected streams reconcile state without creating a new collection. Replay is labeled. Sensor hits, commanded hold and verified settled hold are distinct.

Checkpoint: dashboard tests/mutations and a final matrix covering route, sensor detection, physical hold/dwell, single collection/animation and return. A full mission remains unverified until physical acceptance is complete.

## TDD and mutation validation

Behavior changes follow acceptance criteria, failing tests for the intended missing behavior, minimal implementation, and refactoring with tests passing. Deterministic clocks and fake physical I/O support real parser/state-machine integration tests. Firmware tests exercise shared C++ logic used by firmware, not a parallel Python model.

Every behavioral phase checkpoint begins with a green baseline and at least two realistic, relevant code mutants where sufficient behavior exists. Each fault is applied one at a time in an isolated hardware-free copy; existing relevant tests run unchanged. A behavioral assertion must detect the intended fault. Syntax/import failures, unrelated failures and infrastructure timeouts are inconclusive.

Relevant non-equivalent survivors expose a test gap. Correct code is restored, a behavior-based test is added, the same mutation is reapplied and detection is verified. Equivalent/out-of-scope mutations are explained. Every mutation is removed and the normal suite rerun before delivery. Mutated firmware is never flashed and mutated software never accesses physical hardware.

| Checkpoint | Representative deliberate faults |
|---|---|
| Sensor | Timeout becomes a hit; confirmation bypassed; threshold inverted |
| Receiver/export | Stale/malformed data accepted; duplicate check bypassed; invalid JSON exported |
| Radio/localization | Telemetry mode permits flight; stale pose accepted; invalid home recorded |
| Mission | Wrong station accepted; dwell skipped; stale presence reused; duplicate collection |
| Navigation | Inflation removed; corner cutting allowed; axes swapped; obstacle-crossing route |
| Integration | Search commands persist after hold; proximity bypassed; stale reconnect data accepted |
| Dashboard | Unconfirmed hit animates; duplicate event counts twice; animation authorizes success |

## Subsection progress records

The engineering progress record is `docs/astrophage-progress.md`. Each subsection documents:

- Status: PASS, FAIL, BLOCKED or NOT RUN, with a result for each acceptance criterion.
- Files/behavior changed and the reason.
- Exact test commands, pass/fail/skip counts, failures and fixes.
- Mutation baseline, injected fault, intended detecting test, actual result, survivors and restoration evidence; NOT DUE for non-checkpoint subsections.
- Hardware versus simulated evidence, configuration and log paths.
- Unresolved work, required operator actions and next subsection.
- Decision to continue within the phase or stop at its checkpoint/physical gate.

Passing software does not bypass physical gates. Independent work may continue while hardware is blocked, but its verification remains pending. Numerical acceptance criteria are established before trials; preliminary values are labeled provisional. Iterations address the earliest failing requirement with a regression test and the smallest justified change. Physical experiments change one variable at a time and retain prior failed data.

## References

- [Arduino C/C++](https://support.arduino.cc/hc/en-us/articles/360018448219-Can-I-program-the-Arduino-board-in-C) and [serial printing](https://docs.arduino.cc/language-reference/en/functions/communication/serial/print).
- [MaxBotix multicopter interference discussion](https://maxbotix.com/blogs/blog/multi-copter-operation); the selected station sensor still needs its own trials.
- [Bitcraze MotionCommander](https://www.bitcraze.io/documentation/repository/crazyflie-lib-python/master/api/cflib/positioning/motion_commander/), including accumulated position error with velocity setpoints.
