# Mission 1 Scout cache

Updated 2026-10-26, Chunk 0. Owner: persistent `/root/scout`. No prior implementation cache existed. Read-only reconnaissance only except this file; no source module imported, hardware command executed, test run, branch checked out, or production code written. `git fetch origin --prune` succeeded. Recheck cached source only when its version/hash changes.

## Repository and branch inventory

Worktree `C:/Users/victo/amaze-hula-hoop`, clean initially, branch `astrophage-collection`; initial HEAD `a838533025480253e6a592baff163f98a1962208`.

| Reference | Resolved commit | Relevance |
|---|---|---|
| origin/main | 9a056e0de974ebe186add2efc1427994be70c724 | Repository base |
| origin/sarah | 64b37c53218b21a70e5032a4a6e3b8d8ec59ce93 | Sarah orbit sources |
| origin/test_drone_flight | 2d778146bfaf9e8616d749b88d30ee7b98363953 | Reviewed reactive navigation and orbit demo |
| local test_drone_flight | 80561d124a1c19d4e6ceb9e54a4286d0508864c6 | Adjacent worktree; newer telemetry exporter changes excluded |
| origin/feature/autonomous-object-orbit | 222b30445effc8b8da6ef9562f4212b6de1f3983 | Original simulation prototype |
| origin/dashboard_main | 04fc3a38922ea2b3e7b02dd4558b37725daf0062 | Bridge reference |

Local branches: astrophage-collection, dashboard_main, telemetry-integration-combined, test_drone_flight, victor/telemetry-dashboard-demo, victor/telemetry-integration-dashboard.

Remote branches after fetch: AidanTang, AlexWang, Camryn, Matthew, OliviaWu, SasiK, ananya_vinay, ansur_XRV, astrophage-collection, dashboard_main, daxhiel, emily, feature/autonomous-object-orbit, feature/docking, main, matheus, neal, niva-branch, nuzhat, oliviawu, repo_setup, sarah, smithi, telemetry-integration-combined, test, test_drone_flight, victor, victor-telemetry-integration-dashboard, victor-telemetry-integration-flight, yohana, zidan. origin/HEAD points to main.

Other worktrees: `C:/Users/victo/amaze-test-flight` on test_drone_flight at 80561d1; `C:/Users/victo/amaze-dashboard` on telemetry-integration-combined at 0d082ae. No changes made to either.

## Conventions and dependency evidence

- `.python-version:1`: 3.10. `pyproject.toml:6`: Python >=3.10; line 8 onward declares only `cflib>=0.1.33`. Proposed mission image should use Python 3.10, not adjacent host venv version.
- `uv.lock:23` locks cflib 0.1.33; Python 3.10 resolution includes NumPy 2.2.6 and SciPy 1.15.3. Existing cflib dependency closure includes pyusb, libusb-package, packaging, PyYAML, NumPy, SciPy and importlib-resources. Mission lock should preserve declared dependency closure with platform-applicable exact pins/hashes, not add plotting/test dependencies.
- Adjacent `amaze-test-flight/.venv/pyvenv.cfg`: Python 3.14.7. Its `Lib/site-packages/cflib-0.1.33.dist-info/METADATA:1-33` confirms installed 0.1.33, requires Python >=3.10, dependencies pyusb~=1.2, libusb-package~=1.0, scipy~=1.14, numpy~=2.2, packaging~=25.0, pyyaml>=6.0.3. This source is read-only API evidence, not the reproducible mission runtime.
- Current tree has `algorithms/`, `shared/`, `dashboard/`, `dev_scripts/`, root `main.py`, no mission package or test/lint configuration. Flight branch tests use `unittest`. Proposed mission layout fits without relocating teammate files.
- Root `Dockerfile` and `docker-compose.yml` exist and must remain untouched; Docker availability/base digest investigated by orchestrator/Builder.
- Do not discover tests over the entire existing tree: inspect legacy `algorithms/test.py` before any inclusion; mission discovery must target `tests/mission1` only in locked containers.
- No applicable AGENTS.md found by repository inventory. No dependency addition or install performed.

## Sarah orbit review

Evidence: `git log origin/sarah --oneline -30`, `git diff --stat origin/main...origin/sarah`, `git ls-tree -r --name-only origin/sarah`, and `git show` for each source. Branch adds three orbit scripts plus IDE/cache artifacts; no orbit tests found.

History: `3d50bdb` (2026-09-30, sarahnguyen687, `sttnguyen1@gmail.com`) introduced algorithms; `37da5e0` (2026-10-09, ansur, `ansurfnt@gmail.com`) revised basic orbit connection; `e5c890e` (2026-10-19, Sarah Nguyen, `sttnguyen1@gmail.com`) added reactive revision; `64b37c5` (2026-10-22, Sarah Nguyen, same email) renamed orbit_reactive. Credit future ports with exact path/commit header and `Co-authored-by: Sarah Nguyen <sttnguyen1@gmail.com>`; include Ansur if porting his modified logic.

### algorithms/orbit_reactive.py at 64b37c5

`_range_callback`, `compute_velocity_command`, `run_orbit` are relevant symbols (roughly lines 66-156). Input is latest four range values, assumed meters; body axes +x forward/+y left. Rejects None/outside min/max; selects nearest beam each tick. With inward beam unit n and error d-d_ref, radial velocity is K*error*n; tangent is a CCW 90-degree rotation of n at fixed speed; sum magnitude is capped. Returns body vx/vy, or None if nothing valid. Hardware loop uses zero yaw with detections and positive search yaw otherwise. No persistent target state, timestamps, telemetry freshness, or tests. Assumes isolated stationary object; closest beam switches can switch objects.

### algorithms/potential_field_orbit.py at 64b37c5

Related variant: tangential speed = configured angular speed * measured surface range (floored), optionally reduced by radial error. This is surface distance, not center radius; it does not implement design yaw rate `v_orbit/(d_ref+r_est)`. Both reactive files contain an incorrect comment claiming raw uint16 ranges are already meters; actual callback performs no conversion. Do not port this boundary error.

### algorithms/orbit.py at 64b37c5

Fixed object coordinates, radius and time-parametric world position setpoints, optional face-center yaw. Kalman-variance convergence and position read helpers; resets estimator settings. It does not detect objects or regulate relative measured standoff and conflicts with §9.2. Do not reuse its flight/parameter-writing path.

### Design comparison and proposed choice (approval pending)

| §9.2 / §9.3 requirement | Sarah evidence | Required adaptation |
|---|---|---|
| Measured surface range radial correction | Reactive versions have correct radial sign | Port only reviewed pure math |
| Selected colony on left beam; forward tangent; positive coordinated yaw | Nearest-of-four selection, zero tracking yaw, CCW rotation of inward n gives negative x for left-facing n | Replace target selection/tangent/yaw with design formula; do not silently preserve opposite orbit direction |
| Valid band pauses collection | Absent | Collection module gating |
| Facing-beam loss, hold/reacquire, bounded failure exit to PLAN | Searches on complete absence, no target-specific timeout | Explicit timestamped target-loss states using map estimate |
| Every command supervised, clearance includes current colony | Magnitude cap only; no freshness/geofence/battery/acceleration supervisor | Independent safety pipeline |
| Finite values, invalid dt and raw-unit validation | Incomplete, no dt input, incorrect raw-unit assumption | Typed SI input, rejection reasons and adversarial tests |

Recommendation to Victor: keep Sarah's reactive radial/vector decomposition as attributed source, adapt strictly to §9.2, and use the separate prototype only for reviewed loss-state/test concepts. This is a behavioral adaptation requiring checkpoint decision, not a wholesale port. Retaining Sarah's nearest-beam reactive behavior unchanged would require changing the design.

## Separate orbit prototype

`algorithms/object_orbit/prototype.py` and `test_prototype.py` on origin/test_drone_flight are identical to origin/feature/autonomous-object-orbit (`git diff` empty). Original commit 222b304, 2026-09-28, Victor Van <victorvantx2007@gmail.com>; merged by 2d77814. This is separate work, older than Sarah's Sept 30/Oct revisions, not an earlier copy of her controller.

`OrbitController.step` at lines 48-159: synthetic list of (body bearing radians, range meters), local position, CCW yaw radians, dt seconds -> world velocity m/s. SEARCH -> APPROACH -> FOLLOW, with REACQUIRE/COMPLETE/ABORT. Validates dt/pose/scans, stops for close return, holds then aborts after 3 s target loss, compares bearing/range continuity, and heuristically closes a lap from travel/turn/odometry. Uses clockwise rotation of inward normal (left-side target gives forward tangent). `DemoWorld.scan` around lines 211-215 synthesizes instantaneous 360-degree scans every 5 degrees, not four physical beams. No coordinated yaw and no mission geofence/energy/supervisor. Tests: circle/box closure, empty timeout, invalid scan, loss hold/abort, rotation without translation, close obstacle, abrupt target change. Port only selected reviewed state/test concepts with Victor attribution, not the ideal sensing or lap-completion semantics.

## Ansur reactive navigation

Reviewed origin/test_drone_flight `algorithms/reactive_nav.py` (2d77814 tree), requested history eff9058, 3217689, 047b500, all `ansur <ansurfnt@gmail.com>`. Latest algorithm change 047b500 (2026-09-29). Local branch adds telemetry exporter code/tests (80561d1) and is deliberately excluded.

Relevant symbols/lines: `rot` (74), `BEAM_DIRS_BODY` (62), `_repulsion` (185), `step` (262), damping/smoothing/closing projection (421-465). Inputs meters, world position/velocity, radians, positive seconds; output world m/s, rad/s yaw, state. Potential-field attraction and inverse-distance beam repulsion; SEEK/ESCAPE/ARRIVED local-minimum heuristic. Useful for safety port: body/world rotation, bounded inverse-distance repulsion, measured-velocity damping, speed saturation, dt-aware filtering/slew, bypass filters for fresh dangerous returns, project closing velocity away from each beam. Do not port goal attraction, wall-follow navigation states, --fly adapter, JSON writer, benchmarks or IDE artifacts.

Design mismatches: raw zero/None sometimes treated as clear; no freshness/geofence/energy checks; additive panic repulsion alone is not hard no-closing guarantee; early ARRIVED bypasses later clearance checks; emergency corrections can exceed ordinary acceleration limit; hard-coded epsilons/gains must move to config. All beam hazards including current colony must go through final supervisor. Four-beam blind wedges remain a physical limitation.

Existing `algorithms/test_reactive_nav.py` uses unittest: GeometryTests (vectorized/scalar rays, swept clearance, collision precedence, invalid sim params), NavigationTests (noise reversal, slew dt, close-return median/filter bypass, rate-consistent filter, closing-speed bound, scenarios). Reuse reviewed relevant tests under Validator ownership and attribute copied logic.

## Dashboard reference

`origin/dashboard_main:Mission Dashboard/server/crazyflie_bridge.py`, head/file commit 04fc3a38922ea2b3e7b02dd4558b37725daf0062, Camryn Nowlin <camrynnowlin@Camryns-MacBook-Pro.local>, 2026-10-19. Reads pm.vbat and stabilizer roll/pitch/yaw as float at requested 100 ms via LogConfig and SyncLogger/SyncCrazyflie. Reference only: hard-coded URI, blocking wrappers, WebSocket packaging do not meet mission transport requirements. Never executed.

## cflib 0.1.33 API cache (static source inspection)

All paths below relative to `C:/Users/victo/amaze-test-flight/.venv/Lib/site-packages/cflib/`. Read directly, never imported. Public signatures omit self in this table. These are candidates for adapter design, not authorization to invoke them.

| API and source line | Arguments/units | Behavior and mock obligation |
|---|---|---|
| crtp/__init__.py:46 `init_drivers(enable_debug_driver=False, enable_serial_driver=False)` | bool flags | Registers drivers; host transport only |
| crtp/__init__.py:65 `scan_interfaces(address=None)` | optional address | Synchronous driver scan, returns URI/detail list, no API timeout; NOT run. Prefer required CLI/config URI to avoid need for scan |
| crazyflie/__init__.py:76 `Crazyflie(link=None, ro_cache=None, rw_cache=None)` | link/cache paths | Constructs callback containers and subsystems; not a no-side-effect test double |
| crazyflie/__init__.py:241 `open_link(link_uri)` | URI string | Driver open is synchronous, subsequent TOC/param connection proceeds through callbacks; failures reported by callback; caller needs bounded deadline |
| crazyflie/__init__.py:85-98 callbacks | `connected(uri)`, `fully_connected(uri)`, `connection_failed(uri,message)`, `connection_lost(uri,message)`, `disconnected(uri)` | TOCs available at connected; parameter values at fully_connected; preserve callback ordering/fault cases |
| utils/callbacks.py:41/46 `add_callback(cb)`, `remove_callback(cb)` | callable | `call(*args)` dispatches synchronously; callback must not block |
| crazyflie/__init__.py:281 `close_link()` | none | **Sends commander.send_setpoint(0,0,0,0) when link present**, then closes link, joins incoming thread up to 1 s, emits disconnected. Underlying radio thread stop may join without deadline |
| crazyflie/syncCrazyflie.py:49 `SyncCrazyflie(link_uri, cf=None)`; :69 `open_link()`; :98 `wait_for_params()`; :123 `close_link()` | URI / cf object | Event waits have no timeout. Context enter opens, exit closes; inherits hidden setpoint in close |
| crazyflie/param.py:376 `get_value(complete_name, timeout=60)` | qualified name; seconds documented | Cached string value after init. **Implementation ignores timeout argument and waits literal 60 s** if not initialized. Calling from incoming callback before full connection raises |
| crazyflie/param.py:246 `add_update_callback(group=None,name=None,cb=None)`; :233 `remove_update_callback(group,name=None,cb=None)`; :311 `request_param_update(complete_name)` | callback receives name/value | Asynchronous update alternative; no parameter write needed |
| crazyflie/toc.py:71 `get_element_by_complete_name(complete_name)` | qualified variable/param name | Local lookup; returns element/None, for fail-closed presence/type checks |
| crazyflie/log.py:138 `LogConfig(name,period_in_ms)`; :161 `add_variable(name,fetch_as=None)` | ms, qualified names, optional C type | Period encoded as int(ms/10); use exact 10 ms multiples; payload <=26 bytes |
| crazyflie/log.py:451 `cf.log.add_config(logconf)` | config | Checks TOC and type sizes; missing variable KeyError; excessive size/invalid period AttributeError; absent link logs error and returns; do not assume success |
| crazyflie/log.py:292/307/320 `start()`, `stop()`, `delete()` | none | Asynchronous request/acknowledgment operations, not waits for samples/cleanup |
| crazyflie/log.py:334/570/627 callbacks | data `(timestamp,data_dict,logconf)`; error `(logconf,message)` | Raw timestamp is 24-bit firmware counter; preserve separately from host monotonic freshness; mock callbacks/dropouts/errors/reordering/wrap |
| crazyflie/commander.py:167 `send_hover_setpoint(vx,vy,yawrate,zdistance)` | body m/s, degrees/s, absolute height meters | Packet send; no arrival/flight-success wait. Version <=8 wire yaw sign handled inside library; mission converts radians->degrees once |
| crazyflie/commander.py:120 `send_velocity_world_setpoint(vx,vy,vz,yawrate)` | world m/s, degrees/s | Alternative only if consciously selected; version-dependent wire handling internal |
| crazyflie/commander.py:111 `send_stop_setpoint()` | none | Motor stop/drop, **not soft hover or landing** |
| crazyflie/supervisor.py:259 `send_arming_request(do_arm: bool)` | True arm / False disarm | Packet send, legacy platform fallback before protocol 12; no proof of arm success |
| crazyflie/supervisor.py:302 `send_emergency_stop()` | none | Immediate motor stop request, legacy localization fallback before protocol 12; no delivery guarantee on lost link |
| crazyflie/supervisor.py:174 `read_bitfield()`, :220 `is_armed()` | bitfield/bool | Can synchronously wait up to internal 0.2 s via _fetch_bitfield; cache 0.1 s; keep out of emergency hot path |
| crazyflie/platformservice.py:139 `get_protocol_version()` | none | Cached protocol integer; can log for source-path diagnosis |
| positioning/motion_commander.py:56 `MotionCommander(crazyflie,default_height=0.3)`; :387 `start_linear_motion(velocity_x_m,velocity_y_m,velocity_z_m,rate_yaw=0.0)` | body m/s, deg/s | start motion queues streaming thread; take_off(height=None,velocity=VELOCITY) / land(velocity=VELOCITY) block; context automatically takes off/lands; estimator reset writes at :410-414. Avoid wrapper for explicit supervised loop |
| utils/multiranger.py:34 `Multiranger(crazyflie,rate_ms=100,zranger=False)` | ms | Helper logs all six ranges in this version; properties omit per-reading timestamps. :65 converts raw >=8000 to None, else /1000. Prefer explicit timestamped LogConfig blocks |

Blocking findings for checkpoint:

1. Plain cflib `close_link()` violates literal zero-setpoint telemetry-only rule. Keep that rule; use passive cleanup that never invokes commander methods, with a packet guard only as defense in depth, and prove zero calls with adapter-over-fake-cflib tests. Do not silently waive or hide the call using an oversimplified mock.
2. SyncCrazyflie and Param timeout behavior require explicit bounded lifecycle design; source signatures alone do not promise bounded waits.
3. MotionCommander includes autonomous streamer and estimator writes; recommend direct low-level sends only in reviewed flight path with all supervisor/interlock checks.
4. Library imports cannot establish hardware presence or firmware behavior. Model, decks, radio exclusivity, actual firmware, actual log rates, range reliability, and onboard radio-loss timeout await Victor's Stage A/C/D evidence.

Passive-close review decision: recommend (B), a pinned telemetry-specific Crazyflie cleanup subclass that closes without any commander call, preserving link/thread/callback cleanup. This duplicates version-sensitive cflib internals and needs source-diff review on upgrades. Tests must exercise adapter cleanup with fake link objects and prove zero commander/arming/setpoint calls as well as zero outbound command packets. Option (A), a no-op commander facade suppressing the dependency's zero-setpoint call, is rejected as a sole solution because the commander method is still invoked and violates Victor's literal zero-call requirement. An outbound CRTP command-port guard is defense in depth only, not a substitute for zero calls. A guard that raises during ordinary close is also insufficient: it can skip disconnection. Orchestrator resolved this review in Chunk 0 consistently with Builder; no implementation or requirement waiver is authorized by these notes.

Single-owner limitation: `crtp/radiodriver.py:209-233` RadioManager uses an in-process list and threading semaphore, not a cross-process dongle lock. Proposed mission-owned OS lock prevents duplicate mission owners; it cannot by itself identify or stop cfclient/dashboard/other noncooperating software. Runtime preflight needs explicit known-conflict checks and fail-closed handling for device-busy/unknown ownership, with the supported Windows ownership-detection strategy reviewed before Chunk 9. Do not claim universal owner detection from a lockfile or process-name check; no process or USB scan was performed during this recon.

Source fingerprints (SHA-256): crazyflie/__init__.py `FD3339C372148702AD378328933702378AC76D4E1DF08CE40537BCEC7B9CFF2D`; param.py `89E3CC2151C5FEEA5320FAF3320AA1860980A8C0D75D83F1DFA2C6D40CDE8F0D`; commander.py `33A000502846668583447859D5DF03DC800B8EDFEA59E35EA2F4E02CD6EC345B`.

## Telemetry names, units and design correction needed

Official current [Bitcraze log reference](https://www.bitcraze.io/documentation/repository/crazyflie-firmware/master/api/logs/), inspected 2026-10-26, documents `kalman.stateX/Y/Z` as global position, `kalman.statePX/PY/PZ` as **body velocity**; `stateEstimate.vx/vy/vz` are global m/s. `range.front/back/left/right/up/zrange` are uint16 millimeters; stabilizer roll/pitch/yaw correspond to attitude degrees; `pm.vbat` is float volts. Altitude diagnostics may use stateEstimate.z meters. These current docs are not evidence of the aircraft's installed firmware/TOC.

Design §11.2 line 377 labels Kalman PX/PY as world_local velocity, conflicting with documented body frame and reactive-nav adapter comments. Decision required: retain raw PX/PY with explicit body->world conversion using matching pose, or prefer documented global stateEstimate.vx/vy and update the design's source list. Scout's research recommendation is global velocity with a fail-closed TOC check; this is an alternative, not the orchestrator's decision. The orchestrator's checkpoint recommendation and Victor's approval govern the selection. No silent reinterpretation.

[Bitcraze parameter reference](https://www.bitcraze.io/documentation/repository/crazyflie-firmware/master/api/params/) confirms read-only uint8 `deck.bcFlow2` and `deck.bcMultiranger`, nonzero when detected. Stage A must independently confirm physical installation; recorded/cached TOCs do not prove currently mounted hardware.

Suggested future log grouping (PROPOSED, implementation deferred): position/velocity <=24 bytes; attitude+battery 16 bytes; six raw ranges 12 bytes. Independent source timestamps require alignment and per-stream freshness; cannot put every required variable into one 26-byte block. Missing vars/decks fail closed, no set_value for firmware/PID/arming/failsafe configuration.

## Chunk 1 research brief from cache

Keep proposed mission layout; Python 3.10 plus exact cflib 0.1.33 dependency closure, unittest, no plotting/test dependency. Base digest and lock provenance must be verified before image build. Tests only inside no-network/no-device mission containers. Frame fixtures must include raw mm->m, deg->rad, four body beams at yaw 0/±90/180, and explicitly distinguish body velocity from world velocity. Config physical defaults remain PROPOSED with Stage A replacement references. Logger must expose overflow/error state and preserve non-finite rejection reason rather than silently imply valid measurement. Exporter handles truncated last JSONL line and atomically replaces output. No cflib import outside transport, no hardware CLI in this chunk.

Orchestrator-reported Docker evidence: Engine 29.8.0, Desktop 4.92.0, linux/amd64; proposed `python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370` manifest index, amd64 digest `sha256:db6ee5170ebce0f4d165af242e8e77addc08bd9ffc37e8b1815752cf027aa4f8`, annotated Python 3.10.22. Scout did not independently repeat Docker commands; see Chunk 0 report for direct evidence. Runtime Python and package freeze await Chunk 1 image build.

## Commands / research limits

Read-only commands used: git status/branch/worktree/log/diff/ls-tree/rev-parse/show, authorized git fetch origin --prune, rg, Get-Content/Get-ChildItem/Get-FileHash. Git show content was never executed. Website reads limited to official Bitcraze reference. No Python, hardware tool, radio scan, process/device scan, firmware command, or host test was run by Scout. No production/test files written; only this cache.

## Chunk 1 targeted brief — 2026-10-29

Read the existing cache first, then current PROGRESS and Chunk 0 report. Chunk 0 approved at `cde04f8633c511af0e7cd8ca611c13f040f022da`. Victor approved distinct HIT/NO_RETURN/INVALID outcomes on 2026-10-29; raw sensor sentinel mapping still awaits Stage A evidence. No unchanged branch/cflib research repeated. Only previously uncached complete lock closure/wheel-platform evidence and exact §12 requirements were inspected. No build, test, Docker command or hardware access performed by Scout.

### Environment and lock review

`uv.lock` contains this Python 3.10 dependency closure: cflib==0.1.33 (line 22), importlib-resources==7.1.0 (43), libusb-package==1.0.30.0 (52), numpy==2.2.6 (70), packaging==25.0 (293), pyusb==1.3.1 (302), PyYAML==6.0.3 (311), scipy==1.15.3 (375). These are existing project dependencies, not newly proposed additions. Do not accidentally export the Python 3.11/3.12 NumPy/SciPy branches or install the placeholder root project itself.

Evidence for CPython 3.10 Linux x86_64 and Windows amd64 wheel hashes already in the lock: NumPy lines 83/87, SciPy 391/394, PyYAML 320/324; libusb-package platform wheels lines 62/66. Universal wheels cover the remaining packages. Preserve both supported-platform hashes in the mission requirements lock so the later native Windows setup uses the same package versions. This is static compatibility evidence only: actual metadata compatibility and registry artifact availability require a successful image build. The native runbook must require Python 3.10, rather than reuse the unrelated Python 3.14 venv.

Use the approved cached digest, not a new moving tag resolution. The approved index includes the linux/amd64 child recorded above; choosing linux/amd64 explicitly keeps architecture stable across builds and snapshots. Record both index and selected manifest provenance. Install only exact hash-checked locked requirements; no unpinned pip upgrade, uv download, apt packages or source-build toolchain. Wheel-only installation is a conservative way to fail clearly rather than silently fetch extra build dependencies. Keep the dependency layer before source and mount the repository for tests. Any unavailable/incompatible pin is a reproducibility blocker to report, not permission to substitute a version. No need for a third-party test, lock-generation, export or schema dependency.

### Foundation pitfalls derived from §§10, 12 and 18

- Frames: body +x forward/+y left, yaw CCW radians; distinguish point transforms (rotation plus origin) from vector transforms (rotation only). At yaw +90 degrees, body-left maps to negative world-x. Sensor mounting offsets rotate with the beam. Raw mm/deg conversions must be explicit; never label Kalman body velocity world velocity. Unit conversion helpers do not authorize a transport import.
- Time: keep UTC, host monotonic receipt time and device counter separate. Fake clock supports deterministic tests; no module import should consult wall time or start threads. Reject non-finite values and invalid/reversed time steps with visible reasons rather than allowing corrupt command/state outputs. Logger's intentional I/O/thread lifecycle should be explicit and dependencies injectable.
- Config/types: physical defaults stay PROPOSED with Stage A replacement references, including offsets/arena assumptions. Preserve frame/unit names in fields. Implement the approved HIT/NO_RETURN/INVALID distinction: only trustworthy NO_RETURN may clear visibility cells; missing, dropout, stale and invalid readings never prove free space. Do not invent raw sensor sentinel mapping before Stage A evidence; ambiguous raw readings fail closed.
- JSONL lifecycle: exclusive unique file creation, metadata first, all eight record types, and no control-path disk wait. Metadata includes schema/software/mode/parameters/frame/arena provenance, nullable hardware fields when unavailable and redacted URI. The URI redaction rule must cover metadata and subsequent records consistently.
- Queue correctness: records must preserve their values at enqueue time even if caller mutates a dict later; sequence/order assignment and metadata-first ordering must be safe across producer calls. Bounded overload and background write failures remain observable through logger health even when the log cannot accept its own error event. Do not block enqueue to rescue a full queue. Flush/close semantics and error status must be explicit and tested separately from nonblocking enqueue.
- Strict serialization: `allow_nan=False` must apply recursively, including nested samples/options. Per the orchestrator's Chunk 1 brief, reject NaN/Infinity with an explicit rejection reason/counter; do not silently convert corrupt numbers to null. Intentional unavailable values use null with a reason. Do not treat invalid telemetry as a trustworthy no-return reading. Unknown/unserializable data must yield a visible error, not kill the writer without status.
- Export: validate JSON objects and required envelope consistently; do not let the parser's permissive NaN/Infinity support undermine strict JSON. Report invalid/skipped/truncated lines. Preserve valid complete records after interruption. Write a temporary file in the destination directory and atomically replace only after successful complete export; failure must leave an existing destination intact. These are implementation/test cautions, not invented mission behavior.
- §18 process override: all executable builds/tests use the mission image; hardware remains host-only and Victor-only. No host test fallback. Snapshot records actual Python/freeze/image ID/commands and both file hashes; do not record expected values as observed. Tests must target mission tests, not indiscriminately discover legacy examples.

### Decision boundary

Victor's 2026-10-29 approval resolves the foundational range outcome semantics. Raw sensor sentinel decoding remains pending firmware/Stage A evidence and must fail closed. Logger serialization follows the explicit non-finite rejection choice in the Chunk 1 brief. Export recovery and other interfaces remain reviewable through tests; any disagreement changing design behavior returns to the orchestrator instead of Scout deciding it.
