# Mission 1 Design: Astrophage Collection — Adaptive Hoop Lock

**Status:** Design proposal. No mission code or flight-controller settings have been changed.
**Base branch:** `main`.
**Flight intent:** remain centered relative to an upright, hand-moved hula hoop; do not fly through it.
**Primary constraint:** use only sensors actually installed and demonstrated on the Crazyflie.
**Hardware verification:** pending. No radio, sensor, or flight test was run during this design inspection.

## 1. Executive summary

The proposed mission is a moving-target stabilization task, not ordinary obstacle avoidance. A person moves an upright hula hoop; the Crazyflie estimates where the opening’s center is relative to itself and adjusts its position to remain centered. To be more technically meaningful than static hover, the first mission combines:

- **Target-relative tracking:** estimate the hoop’s center and, if observable, its plane/orientation rather than follow a room-fixed waypoint.
- **Motion compensation:** use onboard odometry and attitude to distinguish drone movement from hoop movement.
- **Short-horizon prediction:** compensate for sensing/control latency using an estimated target velocity only when that estimate is sufficiently reliable.
- **Uncertainty-aware safety:** limit command speed and acceleration based on available clearance and measurement confidence; stop chasing when observations become stale or ambiguous.
- **Reacquisition:** recover a target only after multiple mutually consistent sensor observations.
- **Forensic logging:** record observations, telemetry, commands, link state, timing, and events to a per-run JSONL file and export a standards-compliant JSON document.

The main feasibility risk is **target observability**. The Flow deck can provide local drone-motion estimates, but does not see the hoop. The Multi-ranger provides sparse distance readings, not an object label or an automatic center/orientation estimate. Its readings may support a constrained, range-only hoop model, but that has not been demonstrated. If the hoop can rotate arbitrarily, the current sensor set may not provide enough information at a safe rate. The project must prove this on the bench before implementing or enabling flight tracking. If it fails, a marker/camera or external tracker is a hardware requirement, not a controller-tuning problem.

## 2. Repository evidence and base selection

### Clean source branch

The development branch is based on `origin/main`, not the current `test_drone_flight` checkout. At inspection time, `origin/main` was commit `9a056e0`; `git fetch origin` was performed before creating the new worktree and branch. The current `test_drone_flight` checkout was clean but one local commit ahead of its remote (`80561d1`, JSON export). The clean `main` tree does not contain `algorithms/reactive_nav.py`, the Mission Dashboard prototype, or the combined telemetry demo. This is intentional isolation, not a claim that those useful components do not exist elsewhere.

Ansur’s reactive navigation implementation is in `algorithms/reactive_nav.py` in the history of `test_drone_flight`; relevant author commits include `eff9058`, `3217689`, and `047b500`. The later commit `047b500` also includes tests, benchmark artifacts, documentation, and IDE files, so importing that entire commit would add unrelated work. When implementation begins, port only the reviewed, relevant math and tests into mission-specific modules after writing tests. Do not overwrite the new mission branch with the entire flight branch.

The current dashboard prototype is on `dashboard_main`, not `main`. It has a React/Vite interface and a separate Crazyflie telemetry bridge, but adding it wholesale is not necessary to establish the flight mission. First agree whether the mission PR should remain backend-only or also include a dashboard adapter. If included later, use a narrow integration commit or PR based on the team’s review of that UI branch.

### Applicable instructions

The inspected `main` tree has no `AGENTS.md`. The separate `dashboard_main` tree has `Mission Dashboard/AGENTS.md`; it describes the Figma/Vite frontend scaffold and applies if frontend work is later done there. It does not define the flight backend or controller architecture.

## 3. Existing systems: reuse boundaries

| Existing component | Evidence and capability | Reuse decision |
|---|---|---|
| Ansur reactive navigation | `algorithms/reactive_nav.py` on `test_drone_flight`; controller inputs include range readings, local position, yaw, `dt`, and optional velocity. It outputs world-frame velocity, yaw rate, and a state. The simulation models obstacles. | Reuse selected coordinate, damping, saturation, and test ideas. Do not use its “repel every nearby range return” policy as the hoop tracker: the hoop is the desired target, not an obstacle to flee. |
| Reactive flight adapter | The flight branch checks Flow v2/Multi-ranger deck parameters, reads `kalman.stateX/Y`, `statePX/PY`, and yaw at a configured 50 ms period, then runs a nominal 15 Hz loop. It rotates world velocity into body coordinates and calls `MotionCommander.start_linear_motion`. It arms and takes off; it is not a connection-only mode. | Reference only. Create a separately tested connection-only path and a mission-specific flight supervisor; do not run this script for Mission 1. |
| Dashboard Crazyflie bridge | On `dashboard_main`, `Mission Dashboard/server/crazyflie_bridge.py` connects with `SyncCrazyflie` and logs `pm.vbat`, `stabilizer.roll`, `stabilizer.pitch`, and `stabilizer.yaw` at a configured 100 ms period. It publishes JSON over a local WebSocket. | Useful starting point for radio and logging API usage. It does not observe hoop pose, export mission JSON, receive dashboard commands, or publish full connection-health events. Harden before depending on it. |
| Dashboard telemetry UI | `Mission Dashboard/src/telemetry/types.ts` models GPS, attitude, battery, flight state, and other values; `useTelemetry.ts` can consume WebSocket JSON or local mock data. Some displayed scenario values are mock/prototype data. | Dashboard is optional for the first sensor/control milestone. Clearly mark real versus mock values and do not treat the UI model as installed sensors. |
| Orbit prototype | `algorithms/object_orbit/prototype.py` on the experimental flight branch is a simulation-only object-boundary/orbit concept. It has reacquisition and failure tests but no physical radio integration. | Use only as a reference for explicit target-loss states; it is not a hoop-center tracker. |
| Radio flight example | `algorithms/hop.py` connects via `cflib` and demonstrates MotionCommander/high-level commands; the real mode arms and flies. | Reference APIs only. Do not use as the no-flight hardware check. |
| Existing JSON writer | `algorithms/reactive_nav.py` writes only X/Y arrays to `telemetry/*.json`. It rewrites the arrays synchronously from a 20 Hz telemetry callback. | Do not reuse unchanged: it lacks mission metadata, hoop observations, command/status events, unique run records, monotonic timing, bounded asynchronous writing, and interrupted-run recovery. |

The repository configures no physical camera, camera driver, fiducial detection, motion-capture client, GPS hardware, or hoop sensor. The dashboard’s 3D-scene camera is a visual UI camera, not a real sensor. The code checks for `deck.bcFlow2` and `deck.bcMultiranger` in the experimental flight path, but hardware presence is not confirmed here. The actual Crazyflie model and propeller/guard footprint are unknown.

## 4. Proposed mission behavior

### 4.1 Mission phases and state transitions

| State | Purpose | Permitted output |
|---|---|---|
| `DISCONNECTED` | No confirmed radio connection | No flight command. Report connection failure/status. |
| `CONNECTED_IDLE` | Connection-only telemetry mode | Subscribe/log telemetry only. Must not arm, take off, or send motion setpoints. |
| `SENSOR_CHECK` | Check expected deck parameters, sample freshness, and sensor values | No movement setpoint. Fail closed if required sensors or telemetry are missing. |
| `OBSERVE` | Collect hoop range signatures and characterize detection quality | No autonomous tracking command. This phase can be a bench test. |
| `ACQUIRE` | Require a configured number of valid, geometrically consistent observations | Zero horizontal tracking command until acquisition is accepted. |
| `TRACK` | Estimate hoop-relative error and velocity; issue bounded corrections | Only within validated speed, acceleration, altitude, and clearance limits. |
| `REACQUIRE` | Stop chasing stale/inconsistent detections and collect fresh observations | Zero horizontal correction or a reviewed safe hold; never extrapolate indefinitely. |
| `FALLBACK` | Lost link, impossible clearance, sensor fault, or target outside envelope | Use only a previously reviewed, still-connected fallback. If radio is lost, rely on a verified onboard failsafe; host cannot send a recovery command. |
| `COMPLETE` / `ABORT` | Mission ends or cannot safely continue | Stop target tracking; landing behavior must be explicit and tested. |

Transitions need timestamps and an event record. Flight must require an explicit operator-selected mode; starting a bridge, dashboard, simulation, or connection-only check must never imply flight authorization.

### 4.2 Sensing concept: prove range-only observability first

The initial design assumption is an upright circular hoop observed by the Crazyflie’s onboard range sensors. The existing reactive-navigation notes describe four horizontal Multi-ranger beams (front/back/left/right), plus an upward beam, with a limited field of view. Those are distances in sensor directions; they are not a dense scan or object detections. The Flow deck provides a way to estimate the Crazyflie’s own motion over the floor. Together, the readings might support a constrained hoop fit if the hoop is visible to enough beams and its movement is slow enough to scan.

Potential first experiment, with props removed and motors disabled: hold the sensor package at a fixed pose relative to a hoop, then move the hoop through a measured set of offsets and yaw angles. Record all range returns, timestamps, and deck data. Check whether the same hoop yields a unique, repeatable center and orientation estimate rather than just one nearest distance. Then repeat while rotating the sensor package slowly to evaluate scan coverage and timing.

Potential range-only estimator:

1. Associate only readings compatible with a ring/hoop geometry; reject invalid, missing, out-of-range, or isolated returns.
2. Transform each range ray from sensor frame to body frame and then into a local world frame using the Crazyflie’s timestamped attitude/odometry. This compensates for drone motion while collecting a scan (deskewing).
3. Fit a constrained circle/plane or an agreed simplified model to a window of readings. Use robust fitting and report residual, confidence, and age. If hoop diameter is unknown, estimate it only if the collected geometry makes it observable; do not invent a radius.
4. Estimate center velocity from successive accepted observations using monotonic timestamps and bounded filtering. The Flow deck supplies ego-motion compensation; it does not supply hoop velocity by itself.
5. Reject fits when the hoop may be occluded by a hand/person, when the surface returns are ambiguous with room obstacles, or when motion during a scan exceeds the deskew model’s validated limit.

**This is a hypothesis, not a demonstrated capability.** A few fixed beams may not uniquely determine the plane, center, and radius of a freely rotating hoop, especially if the ring is only partially visible. The center height may also be unobservable from horizontal range rays alone. If the bench test cannot establish observability, stop and revisit constraints or add a marker/camera/tracker. Do not attempt to solve missing perception with controller gains.

### 4.3 Coordinate frames and units

Use explicit frame names in types, variables, tests, and JSON:

- `sensor`: individual range ray origin/direction and raw distance.
- `body`: Crazyflie axes; the existing navigation code assumes +x forward and +y left.
- `world_local`: Flow/Kalman local x/y position frame, meters; yaw is transformed into this frame.
- `hoop`: estimated center and hoop-plane orientation in a documented convention.
- `dashboard`: presentation coordinates only; never use normalized UI coordinates for flight control.

Proposed equations, subject to validated measurement semantics:

```text
e_world = hoop_center_world - drone_position_world
v_rel_world = hoop_velocity_world - drone_velocity_world
v_requested_world = clamp(Kp * e_world + Kd * v_rel_world, speed_limit)
v_requested_body = R(-yaw) * v_requested_world
```

`Kp` and `Kd` are software outer-loop parameters with units that must be documented. The velocity term damps relative motion; it is not the Crazyflie onboard PID D gain. If measurements have measurable latency, a short-horizon prediction may use `hoop_center + hoop_velocity * latency`; prediction must stop when age/confidence bounds are exceeded. Validate signs, yaw convention, degrees/radians, and velocity units with deterministic tests before radio work.

### 4.4 Tracking, limits, and clearance

The controller should be independent of camera/range parsing and radio transport. It consumes a validated, timestamped target estimate and drone state; it outputs a requested world-frame velocity plus state/reason. A separate safety layer enforces:

- Maximum speed and acceleration/jerk from the approved test envelope.
- A safe aperture margin based on measured propeller/guard dimensions, hoop inner radius, sensing uncertainty, loop latency, and expected overshoot.
- A no-chase boundary: if the target’s estimated speed, acceleration, or clearance requirement exceeds capability, enter `REACQUIRE` or `FALLBACK` instead of saturating indefinitely.
- Finite values only; reject NaN/Infinity and invalid timing.
- No movement when error is zero; no command reversal spikes after abrupt target changes.
- No continuing a prediction with stale target data.

Initial limits must be selected after measuring the actual Crazyflie, hoop, sensor latency, and loop timing. The existing script’s 0.28 m/s flight profile is for its unrelated goal-seeking test and is not an approved Mission 1 limit. No PID gain, firmware setting, altitude, speed, or flight command is changed by this design.

The mission should treat the hoop as a **target geometry**, not an ordinary obstacle. Existing repulsive-field avoidance would push away from any beam return near the hoop and fight the centering controller. The first version should separate target measurements from unrelated obstacle returns. Any combined safety planner must preserve a valid aperture corridor and prioritize collision avoidance; if it cannot establish both safety and the mission target, it must stop tracking and request fallback.

### 4.5 Aerodynamic concerns and D-gain proposal

No repository evidence establishes that rotor wash will pull the Crazyflie toward this hoop or destabilize it. Airflow near a thin ring is not equivalent to wall/ceiling/ground effect, and there is no aerodynamic model in the simulation. A larger hoop may improve geometric/propeller clearance but cannot be claimed to eliminate airflow effects.

Do not increase onboard D gain as a first response. The current `k_damp` is software-level velocity feedback; the repository’s flight path does not configure the Crazyflie PID derivative gain. First log target/drone relative velocity, command, measured response, target confidence, and latency in a safe stationary/ground test. If real data shows repeatable oscillation, distinguish controller lag, estimator noise, command saturation, setpoint timing, and airflow before changing a gain. Any gain change requires a testable hypothesis, configuration capture in the log, and reviewed controlled test.

## 5. Radio and telemetry architecture

### 5.1 Single radio owner

For flight, one host process must own Crazyradio and coordinate cflib telemetry, hoop sensing, controller, command sender, and mission logger. The dashboard should receive the resulting telemetry over a local API/WebSocket and must not start a second cflib connection. The existing dashboard bridge currently owns the radio for its own telemetry stream; it must not run concurrently with a mission process using the same dongle.

Proposed physical path:

```text
hoop/range measurements ─┐
                         ├─> host mission process: validate -> estimate -> track -> safety limit
Flow/Kalman + yaw data ──┘                                  │
                                                            ├─> cflib setpoint -> Crazyradio -> Crazyflie
                                                            ├─> cflib telemetry <- Crazyradio <- Crazyflie
                                                            ├─> bounded writer -> per-run JSONL -> host disk
                                                            └─> read-only dashboard stream -> dashboard UI
```

The Crazyflie’s onboard stabilization loops are separate from the laptop control loop. Sending a setpoint is not proof it was received or executed. Record (1) requested output, (2) final output after limits, (3) whether the host call returned, and (4) observed telemetry separately.

### 5.2 Connection-only and link failure

Connection-only mode should use the radio to connect, read deck parameters, start telemetry logs, report sample freshness, then stop logs and close `SyncCrazyflie` cleanly. It must never invoke an arm request, `MotionCommander`, takeoff/land, high-level commander, or velocity/position setpoint. Mocked tests should assert these forbidden calls are absent.

Telemetry subscriptions available in repository examples:

| Source | Values | Repository-requested period | Limitation |
|---|---|---:|---|
| Mission Dashboard bridge | `pm.vbat`, `stabilizer.roll`, `stabilizer.pitch`, `stabilizer.yaw` | 100 ms | Existing dashboard bridge; does not log hoop or position. |
| Experimental flight adapter | `kalman.stateX`, `kalman.stateY`, `kalman.statePX`, `kalman.statePY`, `stabilizer.yaw` | 50 ms | Existing branch config; not proof that a real link sustains 20 Hz. |
| Multi-ranger helper | `front`, `back`, `left`, `right`, `up` range readings | Read by host loop, nominally 15 Hz in that adapter | Actual sensor refresh, missing returns, and update rate must be measured. |

These are configured request rates, not guaranteed effective rates or a complete list of fields available on every firmware/deck combination. Connection-only mode must discover/log which required variables and deck parameters are actually present. Use host wall-clock UTC for external correlation and host monotonic time for interval/freshness analysis; preserve the Crazyflie log timestamp separately and do not label it UTC unless documented.

When telemetry or hoop measurements time out while connected, stop chase commands, report the timeout, and follow the reviewed fallback state. On radio loss, the host cannot send a recovery command. The onboard watchdog/commander-loss behavior and configuration must be verified separately before flight; this repository does not establish that behavior. Link loss must be a logged failure when possible, but a host log cannot record an event after abrupt host power loss.

### 5.3 No-flight command modes

The new mission program should expose separate explicit modes (final CLI names to be implemented and tested):

- **Simulation/replay:** deterministic fake sensor stream or recorded data, no cflib import required and no radio access.
- **Connection-only:** physical radio and telemetry only, no arm/takeoff/setpoints.
- **Flight:** explicit additional opt-in, safety checks, and supervised procedure; never the default.

The current dashboard bridge command documented on `dashboard_main` is a connection-only-ish telemetry server, but its URI is hard-coded and its worker-thread error/clean-stop handling is limited. Do not describe it as fully verified or run it alongside another radio owner. No physical radio was available during this inspection.

## 6. Mission log design

### 6.1 Format and lifecycle

Use JSONL while the run is active: one strict JSON object per line, appended in order. This is easier to append and recover than rewriting one growing JSON array; after interruption, consumers can retain all complete lines and ignore a final incomplete line. At normal shutdown, flush and close. A converter should export a valid ordinary `.json` object/array for tools that require a single JSON document.

- Create a unique run ID and file such as `mission_runs/mission1-<UTC>-<uuid>.jsonl` using exclusive file creation.
- Put a `metadata` record first. Include software commit/version, operating mode, radio URI with any secret/private portions redacted if appropriate, deck/firmware/library versions when available, controller and limit configuration, coordinate frame/unit conventions, hoop model assumptions, and logger schema version.
- Add `sample` records for timestamped sensing/telemetry/control and `event` records for state changes, stale/missing data, rejection, saturation, disconnection, queue loss, write failures, and shutdown.
- Write through a bounded queue on a background worker. Do not make the control loop wait on disk. Count queue drops and surface them on stderr/status and subsequent events. Logger failure must not silently masquerade as a successful run.
- Flush periodically; choose interval based on acceptable data-loss window. `fsync` improves durability but can block and should remain off the control path. No software can recover data still only in RAM after abrupt power loss.
- Strictly serialize with `allow_nan=False`; normalize non-finite/unavailable values to explicit `null` plus a reason/status field. Never output `NaN`/`Infinity` tokens.
- Store output under `mission_runs/` and add it to `.gitignore`; archive/share runs separately from code review.

### 6.2 Proposed record schema

Metadata example:

```json
{"type":"metadata","schema_version":1,"run_id":"<uuid>","mode":"simulation|connect_only|flight","software_commit":"<git-sha>","config":{"radio_uri":"radio://...","loop_rate_hz":null,"speed_limit_mps":null,"hoop_inner_diameter_m":null},"frames":{"position":"world_local","velocity":"world_local","body_x":"forward","body_y":"left"},"units":{"position":"m","velocity":"m/s","yaw":"rad","time":"ns elapsed + UTC"},"hardware":{"crazyflie_model":null,"firmware":null,"decks":[]}}
```

Sample example (fields shown as null until an actual source provides them):

```json
{"type":"sample","run_id":"<uuid>","seq":42,"measurement_utc":null,"received_utc":"2026-10-22T18:00:00.123Z","elapsed_ns":1230000000,"measurement_age_ms":null,"hoop":{"center_body_m":null,"center_world_m":null,"orientation_xyzw":null,"confidence":null,"fit_residual_m":null},"drone":{"position_world_m":[0.0,0.0,0.0],"velocity_world_mps":[0.0,0.0,0.0],"yaw_rad":0.0},"tracking_error_world_m":null,"command":{"requested_world_velocity_mps":null,"final_body_velocity_mps":null,"limits_applied":[],"host_transmit_call_returned":null},"telemetry":{"pm_vbat_v":null,"stabilizer_roll_deg":null,"stabilizer_pitch_deg":null,"stabilizer_yaw_deg":null,"kalman_state_x_m":null,"kalman_state_y_m":null,"kalman_state_px_mps":null,"kalman_state_py_mps":null,"ranger_front_m":null,"ranger_back_m":null,"ranger_left_m":null,"ranger_right_m":null,"ranger_up_m":null},"connection":{"connected":true,"last_telemetry_age_ms":null},"mission_state":"OBSERVE"}
```

The sample is illustrative only; do not fabricate values or use an example as a claim about hardware. Measurement time, host receipt UTC, monotonic elapsed time, and sensor age are separate concepts. A successful host transmission call is not a telemetry acknowledgement.

Proposed converter interface, not yet implemented:

```bash
python tools/export_mission_json.py mission_runs/<run>.jsonl --output mission_runs/<run>.json
```

The exporter should validate every complete line, report skipped/truncated/corrupt records, and write the destination atomically so a failed conversion does not leave a misleading partial `.json` file.

## 7. TDD plan and test matrix

Use Python `unittest`, which is already used by the flight-branch tests. The Mission Dashboard Vite package declares dev/build/preview/format scripts but no frontend test script. The initial tests should target pure geometry/controller/logger interfaces and use deterministic fake sensors, a controllable monotonic clock, and a mocked radio. No automated test may open physical hardware.

For each feature: define expected behavior and measurable acceptance first; write tests; run and confirm they fail at the intended assertion; implement the minimum; rerun; refactor while green. If needed, create an importable no-behavior module/interface before the first test so the red test is a semantic assertion (for example, wrong correction direction), not a missing import.

| Area | Cases | Expected observable result |
|---|---|---|
| Hoop observations | None, low confidence, stale, out-of-order, NaN/Infinity, occlusion, reacquisition | Reject invalid data; never chase stale data; reacquire only after consistent fresh observations. |
| Geometry | Known body/world transforms, ±90° yaw, frame sign, meters/degrees/radians, changing hoop orientation | Computed center/error matches a hand-calculated fixture within tolerance; ambiguous geometry lowers confidence or refuses tracking. |
| Observability | Hoop at known offsets/orientations/diameters, partial ring, hand/person occlusion, nearby wall | Accepted estimates remain within a team-set bench tolerance; ambiguous returns do not become confident target estimates. |
| Control | Zero error, each axis, abrupt target changes, target/drone velocity, saturation, clearance, stale→reacquire transitions | Zero command at zero error; direction reduces error; finite bounded speed/acceleration; stale transitions stop chasing. |
| Timing | `dt=0`, negative, NaN, unusually large interval, delayed updates | Invalid/large intervals do not create a command spike; time base remains monotonic. |
| Radio mock | Connect failure, missing variables, telemetry timeout, disconnect, shutdown, command-only guards | Errors/status are visible; handles close; connection-only calls no arm/takeoff/setpoint method. |
| JSONL | Null fields, non-finite values, per-run unique path, ordering, overflow, disk failure, normal close, truncated final line | Strict JSON lines; explicit nulls; queue drops/write errors visible; complete lines recover and converter produces valid JSON. |

Suggested first failing-test milestone: establish the importable `HoopObservation` / controller interface and fake clock, then test that a valid positive-axis center error produces a correction toward the hoop and that zero error produces zero correction. The expected first failure must be a wrong/missing behavior assertion, not an unrelated environment/import error. Do not tune gains or enable flight while this test suite is red.

## 8. Staged implementation and acceptance

### Stage A — hardware/sensor inventory and bench observability

1. Confirm Crazyflie model, firmware, decks, prop guards/footprint, and supported log variables through connection-only inspection.
2. With props removed/motors disabled, collect real ranger returns while moving/rotating the hoop through known positions. Save data with timestamps.
3. Determine whether the center and orientation are observable and at what effective update rate/latency. Include occlusion and off-axis cases.

**Gate:** do not write the flight tracker until sensor results meet a tolerance agreed with the mentor. If the range-only setup cannot estimate center/orientation, document the smallest required hoop constraint or request marker/camera hardware.

### Stage B — deterministic geometry/controller and TDD

1. Create mission-specific pure modules, not a rewrite of the old reactive script.
2. Write failing geometry/controller tests against fake observations and clock.
3. Implement target estimation interface, frame transforms, PD/relative-velocity control, saturation, stale-data behavior, and explicit state transitions.
4. Build synthetic and recorded-data replay scenarios, without any cflib import or radio initialization.

**Gate:** all deterministic edge tests pass; commands are bounded and stale observations cannot generate chase commands.

### Stage C — connection-only hardware and logs

1. Mock-test radio wrapper and logger, proving no arm/takeoff/setpoint calls.
2. Connect to the actual radio/Crazyflie with props removed; verify deck IDs, log variables, link status, update intervals, and clean disconnect.
3. Run JSONL writer against both simulated and actual read-only telemetry; inspect/export files.

**Gate:** physical link and telemetry checks pass and record actual rates/freshness; mocked tests alone do not satisfy this gate.

### Stage D — controlled supervised flight

1. Review measured sensor envelope, clearance, speed/acceleration caps, fallback, battery/flight area, and onboard loss-link behavior with mentor/operator.
2. First hover with stationary hoop, then tiny slow movements, then expand only within measured envelope.
3. Keep a dedicated safety operator; avoid people inside rotor hazard area; stop if sensor confidence, radio, estimator, or clearance falls below thresholds.
4. Review position error, target age, commands versus observed state, saturation, link gaps, and log completeness after each run.

**Gate:** acceptance thresholds are team-approved before flight and met in supervised runs. Never treat simulation, synthetic feeds, or a successful radio handshake as this gate.

## 9. Preliminary acceptance criteria

Numeric hardware values remain open until the hoop, drone, and sensors are measured. The following software criteria can be tested now without inventing those physical numbers:

- Frame/sign fixtures produce the exact expected target/error coordinates.
- Zero error yields zero correction; each axis yields a correction toward the target.
- Every output is finite and within configured speed/acceleration limits.
- Stale, invalid, out-of-order, or low-confidence target data cannot keep commanding toward an old target.
- Lost radio is surfaced; no host-side recovery is claimed after link loss.
- Connection-only fake-radio tests observe zero arm/takeoff/setpoint calls.
- Every sample/event is strict JSONL, metadata is first, run filenames are unique, and export is valid JSON.
- Queue overflow, write errors, and interrupted final lines are reported/recoverable according to policy.

Physical criteria must include a center-error tolerance, minimum ring/prop clearance, target update latency/rate, max hoop speed/rotation, max permitted confidence/residual, and a tested fallback deadline. The mentor/operator must agree these before a flight attempt.

## 10. Docker and development environment

Docker is not required for Mission 1 as it exists on `main`. Docker images can snapshot a selected source tree and its pinned dependencies so teammates can reproduce a software environment; they are not Git branches, and they do not automatically snapshot flight data. The root `Dockerfile` is a generic Python 3.9 image and runs `python -m myapp`; the root `docker-compose.yml` defines only a generic `drone-app`. Neither is a usable mission image. `main` has no mission-specific Compose file, USB radio/device pass-through, camera mapping, GUI, GPU, or data-volume configuration.

The separate telemetry integration branch has a `compose.telemetry.yml` with a read-only JSON-file bridge and a static OpenMCT server. It does not open Crazyradio and is not this mission’s runtime. Docker Desktop’s daemon was not available during inspection, so existing images/containers could not be confirmed. Do not rebuild or start that unrelated stack for Mission 1.

For the initial implementation, use native host processes: Windows owns Crazyradio and any onboard/USB sensor, the Python process owns the mission/logger, and the browser runs the UI. If a container is later justified for a non-radio service, mount a host directory for output; container-local files disappear when the container is removed. Keep radio/camera access outside Docker unless the team verifies a concrete device pass-through configuration. A separate Git worktree does not alter main branch mounts; any relative bind path is resolved from that compose project/file location and must be rechecked if a Docker setup is later introduced.

## 11. Commands and current limitations

The branch is docs-only at this point. The commands below describe existing code paths, not completed Mission 1 modes.

### Existing simulation (not hoop tracking)

On the existing flight checkout, the old obstacle-navigation simulation is:

```bash
cd ~/amaze-test-flight
./.venv/Scripts/python.exe algorithms/reactive_nav.py --scenario all --no-plot
```

It simulates obstacle avoidance to a fixed goal. It does not simulate a hand-moved hoop, camera/range target fitting, or Mission 1 commands.

### Existing radio connection/telemetry (not flight, but not yet hardened)

On a checkout of `dashboard_main`, the documented host bridge command is:

```bash
cd ~/amaze-hula-hoop
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r "Mission Dashboard/server/requirements.txt"
./.venv/Scripts/python.exe "Mission Dashboard/server/crazyflie_bridge.py"
```

This uses the bridge’s hard-coded `radio://0/80/2M/E7E7E7E7E7` URI and logs battery/attitude at its configured period. It does not log hoop center or mission JSON, and its graceful-stop/status handling needs work. Do not run it while another process owns Crazyradio. **It has not been physically verified here.**

The clean mission worktree from `main` does not contain `Mission Dashboard`. If the team wants to view the existing dashboard prototype, create a separate detached worktree of the dashboard branch (this does not alter the mission branch):

```bash
cd ~/amaze-test-flight
git worktree add --detach ../amaze-dashboard-main origin/dashboard_main
```

The dashboard branch pins Node 22 and pnpm 10.34.3 in `Mission Dashboard/.mise.toml`. Run its frontend from that worktree:

```bash
cd ~/amaze-dashboard-main/"Mission Dashboard"
pnpm install --frozen-lockfile
pnpm dev
```

To point it at the real bridge, copy `.env.example` to `.env.local`, set `VITE_TELEMETRY_URL=ws://localhost:8765`, then restart Vite. The dummy server is `python server/dummyTest.py` from that folder; it is dashboard-only synthetic telemetry, not hoop simulation or flight evidence. Mission Dashboard integration is a separate follow-up decision; do not merge its UI code into this backend/docs-only branch without agreement.

### Eventual Mission 1 flight

No Mission 1 CLI or flight command exists yet. Do not use `reactive_nav.py --fly` as a substitute: it takes off and flies a fixed-goal obstacle-avoidance behavior. The implementation should introduce distinct simulation, connection-only, and explicit flight modes; their exact command line must be documented only after the tested CLI exists.

## 12. Decisions required before the flight design is frozen

1. **Hoop geometry:** inner diameter, tube thickness/material/reflectivity, and the range of orientations allowed while upright.
2. **Mission geometry:** should the drone’s body center stay at the hoop’s geometric center in 3D, or should its projection remain centered in the hoop plane? Confirm that it never crosses the hoop plane.
3. **Movement envelope:** expected maximum translation speed, acceleration, angular speed, abrupt reversals, and movement area. “Adapt regardless” must be replaced with a testable envelope plus fallback outside it.
4. **Hardware:** exact Crazyflie model/firmware, whether Flow v2 and Multi-ranger are actually installed, and propeller/guard dimensions. The current answer suggests the decks may be available but does not identify them.
5. **Sensor observability:** are only the existing Crazyflie sensors permitted, even if the bench test proves they cannot recover hoop pose? If not, may the team add a passive marker/camera or external tracker as a contingency?
6. **Safety:** who supervises flight, what space/net/propeller safety setup is available, and what should the system do after target loss versus radio loss?
7. **Integration boundary:** should the initial PR remain a backend/mission design based on `main`, or must it also connect to the React Mission Dashboard on `dashboard_main`?

Until these are answered and the sensor-only observation gate passes, the recommended deliverable is a tested sensor/logger prototype and a no-flight radio check—not autonomous hoop tracking in the air.
