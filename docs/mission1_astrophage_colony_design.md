# Mission 1 Design: Astrophage Collection — Petrova Line Hunt

**Status:** Design proposal. Supersedes the hoop-centering design (`mission1_astrophage_hoop_design.md`). No mission code or flight-controller settings have been changed.
**Base branch:** `main`.
**Flight intent:** discover stationary colonies (tall floor-standing objects) inside a taped arena, harvest them by orbiting at a safe standoff distance, and return to a home pad within one battery. Never fly over, through, or into a colony.
**Primary constraint:** use only sensors actually installed and demonstrated on the Crazyflie (Flow deck v2 and Multi-ranger, pending confirmation).
**Hardware verification:** pending. No radio, sensor, or flight test has been run for this design.

## 1. Executive summary

Mission 1 is an autonomous, energy-constrained search-and-harvest task. Colonies are solid objects taller than the drone's flight height, placed at unknown positions by someone outside the team. The drone sees them with the Multi-ranger's horizontal beams, maps them, and decides what to do with a limited battery. Its options are to explore unseen space, travel to a colony, keep harvesting the current one, or return home.

The mission is technically meaningful because of the decisions it makes, not because of any single maneuver:

- **Sparse-sensor mapping:** four single-point range beams, swept by rotating the drone, are converted into a map of discrete colonies with position, width, and confidence estimates.
- **Robust object promotion:** a cluster of returns becomes a colony only if it is repeatedly observed, stationary, and within the allowed size range. Walls, people, and noise are rejected by geofencing and consistency checks.
- **Explore vs. exploit:** a visibility grid tracks which parts of the arena have been seen. Exploration is valued by how much unseen area a viewpoint would reveal; harvesting is valued by colony richness.
- **Foraging with depletion:** collection rate decays as a colony is harvested. The drone leaves when the current rate falls below the best achievable alternative, following the marginal value theorem.
- **Budgeted route planning:** choosing which colonies to visit, and in what order, under a battery constraint is an orienteering problem. The colony count is small, so exact enumeration over orderings is feasible at each replanning step.
- **Relative-range orbit control:** while harvesting, the standoff distance is controlled directly from the range beam facing the colony. This measurement is relative and does not suffer from Flow-deck position drift.
- **Layered safety:** a separate safety supervisor enforces minimum clearance from all returns, a geofence, speed and altitude caps, an energy reserve, and stale-data timeouts, and can override the planner at any time.
- **Measured evaluation:** the planner is compared against scripted baselines (lawnmower sweep, nearest-first, largest-first) on the same randomized layouts in simulation and, later, in supervised flights.
- **Forensic logging:** telemetry, colony events, and every planner decision (with the scores of the options considered) are recorded to a per-run JSONL file.

The main feasibility risk moves from "can we see the target at all" to "how reliably and how far can we detect colonies at flight height, and how fast does position drift." Both are measurable in a no-flight bench test before any flight code is enabled.

## 2. Why the mission changed

The hoop-centering design required estimating the center and orientation of a hand-moved hoop from a handful of fixed horizontal range beams. That design's own feasibility analysis (its section 4.2) flagged this as unproven and possibly unobservable without added hardware. It also produced a narrow behavior (hold position relative to one target) with limited room for algorithmic depth.

This design keeps everything that was sound in the previous one (the explicit state machine, connection-only mode, single radio owner, strict JSONL logging, TDD gates, and staged hardware progression) and replaces the perception and control core:

| Concern | Hoop design | Colony design |
|---|---|---|
| Target | Thin moving ring, arbitrary orientation | Solid stationary objects at flight height |
| Perception risk | High: center and plane may be unobservable | Moderate: detection range and width accuracy must be measured |
| Core challenge | Tracking one target | Mapping, exploration, foraging, budgeted planning |
| Role of `reactive_nav.py` | Conflicted with target (repelled from hoop) | Natural fit as the clearance safety layer |
| Role of `object_orbit/prototype.py` | Reference only | Directly relevant to harvest orbit and target-loss handling |
| Evaluation | Center error within tolerance | Collected amount vs. baselines, with zero safety violations |

## 3. Repository evidence and reuse boundaries

### Clean source branch

Development continues from `origin/main` in an isolated mission branch, as in the previous design. At the time of the previous inspection, `origin/main` was commit `9a056e0`. The `test_drone_flight` branch contains Ansur's reactive navigation work (`algorithms/reactive_nav.py`, relevant commits `eff9058`, `3217689`, `047b500`) and an experimental orbit prototype. The dashboard prototype lives on `dashboard_main`. As before, port only reviewed, relevant code and tests into mission-specific modules; do not merge whole branches into the mission branch.

### Reuse decisions

| Existing component | Evidence and capability | Reuse decision for this mission |
|---|---|---|
| Ansur reactive navigation | `algorithms/reactive_nav.py` on `test_drone_flight`. Inputs: range readings, local position, yaw, `dt`, optional velocity. Outputs: world-frame velocity, yaw rate, state. Simulation models obstacles. | **Reuse as the basis of the safety layer.** Its repulsion from nearby returns is exactly the behavior needed to enforce minimum clearance. Port the coordinate, damping, and saturation logic and its tests. The colony currently being orbited is exempted from repulsion only beyond the hard minimum clearance; inside that distance, repulsion always wins. |
| Orbit prototype | `algorithms/object_orbit/prototype.py` on the experimental flight branch. Simulation-only object-boundary/orbit concept with reacquisition and failure tests. | **Review as the starting point for the harvest orbit controller** and its target-loss states. Validate against this design's frame conventions before porting. |
| Reactive flight adapter | Checks `deck.bcFlow2` / `deck.bcMultiranger`, reads `kalman.stateX/Y`, `kalman.statePX/PY`, and yaw at a 50 ms period, runs a nominal 15 Hz loop, rotates world velocity to body frame, calls `MotionCommander.start_linear_motion`. Arms and takes off. | Reference only for API usage and frame rotation. Do not run it for Mission 1; it is not a connection-only mode. |
| Dashboard Crazyflie bridge | `Mission Dashboard/server/crazyflie_bridge.py` on `dashboard_main`. Logs `pm.vbat` and stabilizer roll/pitch/yaw at 100 ms over a local WebSocket. | Starting point for radio and logging API usage. Must not run concurrently with the mission process (single radio owner). |
| Dashboard telemetry UI | React/Vite app with WebSocket or mock telemetry. Some displayed values are mock data. | Optional. A read-only mission view (arena map, colony states, battery, collected total, planner reasoning) is a good demo addition after the backend works. Clearly mark real vs. mock values. |
| Radio flight example | `algorithms/hop.py` demonstrates MotionCommander/high-level commands; real mode arms and flies. | Reference APIs only. |
| Existing JSON writer | `reactive_nav.py` rewrites X/Y arrays to `telemetry/*.json` synchronously. | Do not reuse; replaced by the JSONL logger in section 12. |

The repository configures no camera, fiducial detection, motion capture, external positioning system, or GPS. Deck presence is checked in code but not physically confirmed. The exact Crazyflie model, propeller/guard footprint, and battery are unknown and must be recorded in Stage A.

## 4. Arena and physical setup

All values below are **proposed starting points** to be confirmed or replaced by Stage A measurements.

| Item | Proposed starting value | Why |
|---|---|---|
| Arena | Taped rectangle, about 4 m x 4 m (fit to room) | Large enough for 4–6 colonies with spacing; small enough for one battery |
| Floor | Textured (patterned mat or tape strips if the floor is plain or glossy) | Flow deck needs visible texture to estimate motion |
| Home pad | Marked rectangle at one edge, inside the arena | Fixed takeoff/landing reference and origin of `world_local` |
| Flight height | About 0.4 m, held constant | High enough to avoid strong ground-effect disturbance; low enough that ordinary objects reach above it |
| Colony height | At least about 2x flight height (about 0.8–1.0 m) | Margin for altitude bobbing and beam cone spread |
| Colony width tiers | About 20 cm (small), 35 cm (medium), 50 cm (large) | Tiers must be distinguishable despite rough width estimates |
| Colony material | Solid, matte, opaque (bins, stacked boxes, large cardboard tubes) | Thin, shiny, or transparent objects return unreliably |
| Colony spacing | At least about 1 m apart and 1 m from the tape | Prevents two colonies merging into one cluster; keeps walls out of range of association |
| Exclusion | No walls, furniture, bags, or people inside the tape | Any solid return inside the arena can then be treated as a colony candidate |

Demo protocol:

1. A person outside the team places the colonies before each run (layout unknown to the drone and team).
2. At least one colony should be occluded from the home pad by another colony, so exploration is required.
3. The safety operator confirms the arena is clear of people, records the layout (photo and tape-measure positions) for later evaluation, and only then authorizes flight.

The recorded ground-truth layout is used only for post-run evaluation and is never fed to the drone.

## 5. Mission behavior

### 5.1 States and transitions

| State | Purpose | Permitted output |
|---|---|---|
| `DISCONNECTED` | No confirmed radio connection | No flight command. Report status. |
| `CONNECTED_IDLE` | Connection-only telemetry mode | Telemetry subscription and logging only. Never arm, take off, or send setpoints. |
| `SENSOR_CHECK` | Confirm decks, required log variables, sample freshness, battery above takeoff minimum | No movement. Fail closed if anything required is missing. |
| `TAKEOFF` | Climb to flight height over the home pad | Vertical motion only, within approved limits. |
| `SCAN` | Rotate in place to sweep the arena with side beams | Yaw rate only; zero horizontal velocity. |
| `PLAN` | Choose next action from the current map and battery state | No new motion; hold position. Runs within one control cycle. |
| `EXPLORE` | Fly to a viewpoint chosen to reveal unseen space, then scan there | Bounded horizontal velocity and yaw rate under the safety layer. |
| `TRANSIT` | Fly to the orbit entry point of the chosen colony | Bounded horizontal velocity and yaw rate under the safety layer. |
| `HARVEST` | Orbit the chosen colony at the standoff distance and accumulate collection | Orbit controller output under the safety layer. |
| `RETURN` | Fly to the home pad | Bounded horizontal velocity under the safety layer. Cannot be overridden by the planner. |
| `LAND` | Descend on the home pad | Vertical descent only. |
| `FALLBACK` | Safety trigger: lost data, clearance violation, geofence breach, battery critical, unexpected obstacle | Stop horizontal motion and execute the reviewed landing behavior in place or at the nearest safe point while connected. On radio loss, rely only on the verified onboard failsafe. |
| `COMPLETE` / `ABORT` | Mission ended normally or cannot continue | No further tracking or planning. Landing state must be explicit and tested. |

Typical flow: `CONNECTED_IDLE` -> `SENSOR_CHECK` -> `TAKEOFF` -> `SCAN` -> `PLAN` -> (`EXPLORE` -> `SCAN` | `TRANSIT` -> `HARVEST`) -> `PLAN` -> ... -> `RETURN` -> `LAND` -> `COMPLETE`.

Rules:

- `PLAN` is re-entered on arrival at any destination, when a new colony is promoted, when a colony is lost, and periodically (proposed: every 1 s) during `HARVEST` to evaluate whether to leave.
- `RETURN` is forced by the energy check (section 8.5) regardless of planner preference.
- Any state can transition to `FALLBACK`. Only the operator can leave `FALLBACK`/`ABORT`.
- Every transition is logged with timestamps, the triggering condition, and the previous state.
- Flight requires an explicit operator-selected mode. Starting a bridge, dashboard, simulation, or connection-only check must never imply flight authorization.

### 5.2 Architecture

The mission process is split into pure, independently testable modules. Only the transport adapter touches `cflib`.

```text
telemetry (Kalman x/y, vx/vy, yaw, ranges, vbat)
        |
        v
[validate + timestamp] -> [beam projector] -> [colony mapper] -> [visibility grid]
                                                    |                  |
                                                    v                  v
                         [energy model] ------> [planner / state machine]
                                                    |
                                                    v
                            [transit / scan / orbit controllers]
                                                    |
                                                    v
                                  [safety supervisor (clearance, geofence, caps)]
                                                    |
                                                    v
                         [cflib transport]   [JSONL logger]   [read-only dashboard stream]
```

Each module consumes typed, timestamped inputs and returns outputs plus a reason/status, so every decision can be logged and replayed.

## 6. Perception: from range beams to a colony map

### 6.1 Beam projection

Each Multi-ranger reading is a distance along a known sensor direction. For a horizontal beam `i` with body-frame unit direction `u_i` and mounting offset `o_i`, a valid return at distance `d` is projected into the world frame using the drone state sampled closest in time to the reading:

```text
hit_body  = o_i + d * u_i
hit_world = drone_position_world + R(yaw) * hit_body
```

A reading is rejected (not projected) when:

- it is missing, non-finite, or outside the reliable range window measured in Stage A;
- the drone's roll or pitch exceeds a threshold (the beam is no longer horizontal enough to trust its height);
- the matching state sample is too old relative to the reading;
- the projected point falls outside the arena geofence (walls and anything beyond the tape).

A beam with **no return** within its reliable range is also useful: it proves the cells along that ray are empty. Both kinds of readings update the visibility grid (6.5).

### 6.2 Clustering and candidates

Projected hits are grouped by proximity into **candidates**. A spatial hash on a coarse grid (proposed: 10 cm cells) keeps association fast. A new hit joins the nearest existing candidate or colony within a gating distance (proposed: colony radius estimate plus a margin); otherwise it seeds a new candidate.

Each candidate stores its hit points (bounded ring buffer), first/last seen times, the set of distinct viewing bearings, the centroid, and the spread.

### 6.3 Promotion rules

A candidate is promoted to a **colony** only when all checks pass (thresholds set from Stage A data):

| Check | Purpose |
|---|---|
| At least `N_min` hits over at least `T_min` seconds | Rejects isolated noise returns |
| Hits from at least `B_min` distinct bearings or scans | Rejects one-off artifacts from a single view |
| Estimated width within `[w_min, w_max]` | Rejects tiny noise and large structures (walls, people) |
| Centroid stable within `s_max` over the observation window | Rejects moving things (a hand or person entering the arena) |
| Centroid at least the clearance margin inside the geofence | Rejects returns near the tape line |

Promoted colonies receive a stable ID. Two colonies whose estimates converge within the merge distance are merged, and the merge is logged.

### 6.4 Size and center estimation

The beams hit the colony's surface, not its center. Two estimators are used, chosen by how much of the colony has been seen:

- **Arc fit (preferred):** when hits span enough of the surface (always true after an orbit), fit a circle to the hits with a robust algebraic circle fit. This gives the center and radius directly. Box-shaped colonies are approximated by their circumscribing circle, which is conservative for clearance.
- **Angular extent (early estimate):** from a single viewpoint, width is estimated from the angular span over which the beam returns hits, times the range, minus a correction for the beam's cone width. The center is placed half a width behind the observed surface along the viewing direction.

Every colony carries a width estimate, a width uncertainty, and a **tier** (small/medium/large) with a confidence. Early estimates are deliberately treated as uncertain; the orbit refines them.

### 6.5 Visibility grid

A 2D grid covering the arena (proposed: 10 cm cells) tracks what has been observed. Each beam reading marks every cell along its ray as `seen-free` up to the return (or up to the reliable range if there was no return), and the hit cell as `occupied`. Cells never crossed by a beam stay `unseen`. Connected regions of `unseen` cells adjacent to `seen-free` cells form **frontiers**, which drive exploration (section 8.2).

### 6.6 Colony loss

If beams repeatedly pass through a colony's estimated position without a return (more than `L_max` contradicting rays), the colony is marked `lost`, removed from planning, and an event is logged. This handles a colony being moved mid-run and bad early estimates.

### 6.7 Position drift (known limitation and stretch goal)

Flow-deck position estimates drift over time, so the colony map slowly misaligns with reality. Mitigations, in order:

1. **Baseline:** keep missions short, inflate all clearance and geofence margins by a drift budget measured in Stage A, and run orbit standoff control from direct range measurements (section 9.2), which is immune to drift.
2. **Stretch goal, landmark correction:** colonies are stationary, so re-observing a known colony gives information about the drone's own position. A small estimator (for example an extended Kalman filter over the drone's x/y offset) can use repeated colony sightings to correct drift. This is a lightweight form of SLAM and should be attempted only after the baseline mission works.

## 7. Collection model

Collection is simulated in software from measured quantities. Nothing physical is collected.

### 7.1 Richness

A colony's initial Astrophage amount is proportional to its estimated cross-sectional area:

```text
M0 = k * w_est^2
```

where `w_est` is the current width estimate (updated as the estimate improves) and `k` is a scoring constant. Using area rather than width makes the size tiers matter more, which creates real trade-offs.

### 7.2 Depletion

While the drone is in `HARVEST` and within the valid orbit band (section 9.2), the colony depletes exponentially:

```text
collection_rate(t) = M_remaining(t) / tau
dM_remaining/dt   = -collection_rate(t)
```

`tau` is a fixed harvest time constant (proposed starting value: 15–20 s, tuned so a full mission can harvest two to four colonies). Time spent outside the valid orbit band (too close, too far, or unstable) earns nothing. This both prevents gaming the score and rewards good control.

### 7.3 Score

The mission score is total collected Astrophage, reported alongside: colonies found / placed, colonies harvested, battery remaining at landing, minimum clearance observed, and the count of safety interventions. A run with any safety violation is marked failed regardless of score.

## 8. Planning and decision-making

### 8.1 Decision epochs

The planner runs whenever `PLAN` is entered (section 5.1). At each epoch it scores a small set of options:

- **Continue harvesting** the current colony.
- **Go harvest colony j**, for each known, unexhausted colony.
- **Explore frontier f**, for each frontier region (via a chosen viewpoint).
- **Return home.**

Only options that pass the energy feasibility check (8.5) are considered. The best-scoring option wins, ties broken toward lower energy use. All options and their scores are logged.

### 8.2 Exploration value

For each frontier, the planner samples candidate viewpoints in free space and estimates how many `unseen` cells each viewpoint would reveal with one scan, ray-casting against known colonies as occluders. The expected value of exploring is:

```text
V_explore = P(colony in revealed area) * E[colony value] - travel_cost - scan_cost
```

`P(colony in revealed area)` comes from a simple prior: colony density (expected colonies per square meter of unseen arena), updated as the mission discovers how many colonies there are. Early in the mission, large unseen areas make exploration attractive; as the arena is covered, exploration value falls toward zero.

### 8.3 Leaving a colony (marginal value theorem)

While harvesting, the planner compares the current collection rate with the best long-run rate achievable elsewhere:

```text
best_alternative_rate = max over options of (expected gain) / (travel time + harvest time)
leave when current collection_rate < best_alternative_rate
```

This is the patch-leaving rule from optimal foraging theory: stay while the current patch beats the average achievable rate; leave once it doesn't. Because collection rate decays exponentially, the drone naturally leaves rich colonies later than poor ones and never drains a colony completely when better options exist.

### 8.4 Route choice (orienteering)

Choosing an ordered sequence of colonies to visit under a time budget, maximizing collected value, is an orienteering problem (NP-hard in general). With four to six colonies, the planner can enumerate all orderings of the remaining known colonies at each epoch (at most 720 permutations), simulating travel time, harvest gain (with the leaving rule), and the final return home. It commits only to the **first** step of the best sequence and replans at the next epoch. This receding-horizon approach adapts when new colonies are found or estimates change.

If the colony count ever makes enumeration too slow for one control cycle, fall back to greedy insertion with the same objective; log which method was used.

### 8.5 Energy model and reserve

Battery state is estimated from `pm.vbat` with a model fitted to Stage A/D measurements (voltage under load vs. remaining flight time, for this exact aircraft and battery). The planner works in **seconds of remaining flight**, not volts.

Feasibility for any option:

```text
time_to_complete(option) + time_home_from(option end) + landing_time + reserve <= remaining_flight_time
```

The reserve is a fixed safety margin agreed before flight (proposed: enough for a full return from the farthest point in the arena plus landing, with a further fixed buffer). If no option except `RETURN` is feasible, the drone returns. If remaining time falls below the critical threshold at any point, the safety supervisor forces `FALLBACK` (land in place if needed).

### 8.6 Baselines

Implemented on the same interfaces and evaluated on the same layouts:

| Baseline | Behavior |
|---|---|
| Lawnmower | Fixed back-and-forth sweep of the arena; harvest each colony found for a fixed time; return at reserve |
| Nearest-first | After an initial scan, repeatedly harvest the nearest known colony for a fixed time |
| Largest-first | After an initial scan, harvest colonies in order of estimated size for a fixed time |

The full planner should beat all baselines on mean collected value across randomized layouts while matching them on safety (zero violations).

## 9. Control

### 9.1 Transit and scan

Transit uses a bounded proportional velocity command toward the target point in `world_local`, rotated into the body frame:

```text
e_world            = target_world - drone_position_world
v_requested_world  = clamp(Kp * e_world, v_max_transit)
v_requested_body   = R(-yaw) * v_requested_world
```

Scan holds position and commands a constant yaw rate for one full rotation (proposed: slow enough that each beam samples densely; set from measured ranger update rate in Stage A).

### 9.2 Harvest orbit

The orbit keeps one side beam (proposed: the left beam) pointed at the colony and flies forward tangentially. The standoff distance is controlled from that beam's **measured range**, which is a direct relative measurement unaffected by position drift:

```text
d          = left-beam range to colony surface
d_ref      = agreed standoff distance (surface to drone)
vx_body    = v_orbit                               (forward, tangential)
vy_body    = clamp(K_r * (d - d_ref), v_r_max)     (left is +y: move toward colony if too far)
yaw_rate   = v_orbit / (d_ref + r_colony_est)      (turn toward the colony to keep it on the left)
```

Valid orbit band: `|d - d_ref| <= band` and beam return valid. Outside the band, collection pauses (section 7.2). If the facing beam loses the colony for longer than a timeout, the controller stops tangential motion, holds, and attempts reacquisition using the map estimate; repeated failure ends the harvest and returns to `PLAN`.

While orbiting, hits from the facing beam are fed into the colony's arc fit, refining center and width (section 6.4).

### 9.3 Safety supervisor

The safety supervisor sits between every controller and the transport and can only reduce or override commands:

- **Hard clearance:** if any beam reports a return closer than `d_min` (proposed: well below `d_ref`), zero motion toward that return and command a bounded retreat. This applies to the colony being orbited as well. Derived from the reactive navigation repulsion logic.
- **Geofence:** keep the estimated position inside the arena minus a margin that includes the measured drift budget; commands that would exit are clipped to zero outward velocity.
- **Altitude:** hold the agreed flight height; never exceed the cap set below colony height minus margin.
- **Speed and acceleration caps** for every state.
- **Stale data:** if range or state telemetry is older than its timeout, stop horizontal motion and enter `FALLBACK`.
- **Unexpected obstacle:** a promoted-size object appearing where the visibility grid says free space existed recently and moving (for example a person entering) triggers stop and `FALLBACK`.
- **Finite outputs only:** reject NaN/Infinity and invalid `dt`.

The supervisor logs every intervention with the requested command, final command, and reason.

### 9.4 Gains and onboard settings

`Kp`, `K_r`, `v_orbit`, and all caps are software outer-loop parameters with documented units. They are tuned in simulation first, then validated in supervised flight. No onboard PID gains, firmware settings, or failsafe configuration are changed by this design. Any proposed change requires logged evidence and review.

## 10. Coordinate frames and units

- `sensor`: individual range beam origin/direction and raw distance.
- `body`: Crazyflie axes; +x forward, +y left, as in the existing navigation code.
- `world_local`: Flow/Kalman local x/y frame in meters, origin at takeoff on the home pad; yaw in radians in this frame.
- `arena`: the taped rectangle expressed in `world_local` (defined by measuring the home pad's position and heading relative to the tape).
- `dashboard`: presentation coordinates only; never used for control.

Units: meters, meters per second, radians (degrees only at the `cflib` boundary where required, converted explicitly and tested), seconds. Validate signs, yaw convention, and the units expected by `MotionCommander.start_linear_motion` with deterministic tests before any radio work.

## 11. Radio and telemetry

### 11.1 Single radio owner

One host process owns the Crazyradio and runs telemetry ingestion, mapping, planning, control, safety, transport, and logging. The dashboard receives a read-only stream over a local WebSocket and never opens its own `cflib` connection. The existing dashboard bridge must not run at the same time as the mission process.

```text
ranges + Flow/Kalman + yaw + vbat --> host mission process: validate -> map -> plan -> control -> safety
                                                            |
                                                            +-> cflib setpoint -> Crazyradio -> Crazyflie
                                                            +-> cflib telemetry <- Crazyradio <- Crazyflie
                                                            +-> bounded writer -> per-run JSONL -> host disk
                                                            +-> read-only stream -> dashboard UI
```

The Crazyflie's onboard stabilization loops are separate from the host loop. Sending a setpoint is not proof it was received or executed. The log records the requested command, the final command after safety limits, whether the host call returned, and observed telemetry separately.

### 11.2 Required telemetry

| Values | Purpose | Notes |
|---|---|---|
| `kalman.stateX`, `kalman.stateY`, `kalman.statePX`, `kalman.statePY` | Position and velocity in `world_local` | Requested at 50 ms in the existing adapter; actual rate must be measured |
| `stabilizer.yaw`, `stabilizer.roll`, `stabilizer.pitch` | Beam projection and tilt rejection | Convert units explicitly |
| Multi-ranger `front`, `back`, `left`, `right`, `up` | Colony detection, orbit standoff, clearance | Effective update rate, dropout rate, and reliable range measured in Stage A |
| Flow-deck downward range | Height holding (onboard) and logging | Logged for diagnosis only |
| `pm.vbat` | Energy model | Fit voltage-to-remaining-time model per aircraft and battery |
| Deck parameters (`deck.bcFlow2`, `deck.bcMultiranger`) | Sensor check | Fail closed if absent |

Configured log periods are requests, not guarantees. Connection-only mode records which variables are present and their effective rates. Use host wall-clock UTC for external correlation, host monotonic time for freshness and intervals, and keep the Crazyflie log timestamp as a separate field.

### 11.3 Modes

- **Simulation/replay:** deterministic simulated world or recorded data; no `cflib` import, no radio access.
- **Connection-only:** physical radio and telemetry only; must never arm, take off, or send setpoints. Mocked tests assert these calls are absent.
- **Flight:** explicit opt-in, passes `SENSOR_CHECK`, supervised procedure; never the default.

### 11.4 Link and data loss

When telemetry or ranges time out while connected: stop horizontal motion, log the timeout, enter `FALLBACK`. On radio loss, the host cannot send recovery commands; the onboard commander-timeout behavior must be verified separately before flight. A host log cannot record events after abrupt host power loss.

## 12. Mission log design

### 12.1 Format and lifecycle

Carried over from the previous design, unchanged in principle:

- JSONL during the run: one strict JSON object per line, appended in order; complete lines remain recoverable after interruption.
- Unique run ID and exclusive file creation: `mission_runs/mission1-<UTC>-<uuid>.jsonl`; `mission_runs/` in `.gitignore`.
- `metadata` record first: software commit, mode, redacted radio URI, firmware/deck/library versions when available, all controller/planner/safety parameters, frame and unit conventions, arena dimensions, and logger schema version.
- Bounded queue with a background writer; the control loop never waits on disk. Queue drops and write errors are counted and surfaced.
- Strict serialization (`allow_nan=False`); unavailable values are explicit `null` with a reason.
- A converter exports a validated `.json` document atomically and reports skipped or truncated lines.

### 12.2 Record types

| Type | Contents |
|---|---|
| `metadata` | As above, plus the planner method and baseline name if running a baseline |
| `sample` | Timestamps, drone state, raw ranges, projected hits, current state, commands (requested and final), safety limits applied, battery estimate, link status |
| `colony_event` | `candidate_created`, `promoted`, `merged`, `estimate_updated`, `lost`, `harvest_started`, `harvest_paused`, `harvest_ended`, with colony ID, position, width, tier, confidence, remaining amount |
| `planner_decision` | Epoch time, trigger, every option considered with its score and feasibility, chosen option, reason, method (enumeration or greedy) |
| `safety_event` | Clearance, geofence, stale data, unexpected obstacle, energy reserve, with requested vs. final command |
| `map_snapshot` | Periodic compact visibility grid and colony list (proposed: every 2 s), for replay and dashboard |
| `event` | State transitions, connection changes, logger health, shutdown |
| `summary` | Final score, colonies found/harvested, battery at landing, minimum clearance, intervention count, pass/fail |

Illustrative `planner_decision` record (values are placeholders, not measurements):

```json
{"type":"planner_decision","run_id":"<uuid>","seq":812,"elapsed_ns":74200000000,"trigger":"harvest_periodic","state":"HARVEST","remaining_flight_s":null,"options":[{"kind":"continue","colony_id":2,"score":null,"feasible":true},{"kind":"harvest","colony_id":3,"score":null,"feasible":true},{"kind":"explore","frontier_id":1,"score":null,"feasible":false,"reason":"energy"},{"kind":"return","score":null,"feasible":true}],"chosen":{"kind":"harvest","colony_id":3},"reason":"current_rate_below_best_alternative","method":"enumeration"}
```

Post-run analysis reads `planner_decision` records to explain why the drone did what it did, which is the core of the demo narrative.

## 13. Dashboard (optional, read-only)

After the backend passes Stage C, a mission view on the existing dashboard can show: the arena outline and home pad; projected beam hits; candidates and colonies (colored by status: found, harvesting, depleted, lost); the visibility grid with frontiers; the drone's pose and path; battery as remaining seconds with the reserve marked; the collected total; and the latest planner decision with option scores. All data comes from the mission process's read-only stream. The dashboard must never send commands and must label any mock data.

## 14. Simulation and evaluation harness

A 2D kinematic simulator lets the planner, mapper, and controllers be developed and evaluated before hardware is involved.

- **World:** arena rectangle, home pad, circular or rectangular colonies of configurable size and position.
- **Drone:** first-order velocity response with configurable lag, yaw dynamics, and a configurable position-drift model.
- **Sensors:** ray-cast beams against colony shapes with configurable range limits, beam cone, noise, dropout rate, and update rate, all set from Stage A measurements once available.
- **Battery:** remaining-time model with configurable consumption.
- **Layouts:** randomized generator that respects the spacing rules and always includes at least one occluded colony; fixed seeds for reproducibility.

Evaluation protocol: run the planner and each baseline on the same set of seeded layouts (proposed: at least 100). Report mean and spread of collected value, colonies found, battery at landing, and minimum clearance, plus any safety violations (must be zero). Recorded real-flight logs can be replayed through the mapper and planner offline to compare simulated and real behavior.

## 15. TDD plan and test matrix

Use Python `unittest`, as in the flight-branch tests. No automated test may open physical hardware. Use deterministic fake sensors, a controllable monotonic clock, seeded randomness, and a mocked radio. For each feature: define the expected behavior, write the test, confirm it fails at the intended assertion (not an import error), implement the minimum, rerun, refactor while green.

| Area | Cases | Expected observable result |
|---|---|---|
| Beam projection | Each beam at yaw 0, ±90°, 180°; mounting offsets; tilt rejection; stale state; non-finite ranges | World hit points match hand-calculated fixtures; invalid readings are rejected with a reason |
| Geofence filtering | Hits outside, on, and inside the boundary margin | Wall and outside returns never create candidates |
| Clustering | Two separated colonies; two close colonies; single noise hit; moving object | Correct candidate count; noise and moving objects are not promoted |
| Promotion | Below/above hit count, time span, bearing count; width too small/large | Promotion happens exactly when all checks pass |
| Size/center | Full arc, partial arc, single-view extent, boxes | Width and center within fixture tolerance; uncertainty larger for partial views |
| Visibility grid | Ray with return, ray without return, occlusion by a colony | Correct seen-free/occupied/unseen cells; frontiers detected behind occluders |
| Colony loss | Repeated contradicting rays | Colony marked lost after `L_max`, not before |
| Collection model | Inside/outside orbit band; depletion over time | Exponential depletion; zero gain outside band; totals conserved |
| Leaving rule | Rich vs. poor colony with fixed alternatives | Leaves when rate drops below best alternative; leaves poor colonies sooner |
| Orienteering | Small hand-solvable layouts | Enumeration matches the known optimal order; replans when a colony is added |
| Energy feasibility | Options near the reserve boundary | Infeasible options excluded; `RETURN` forced at the threshold |
| Orbit controller | Too close, too far, on band, beam dropout | Correct sign of radial correction; bounded outputs; reacquisition then exit after timeout |
| Safety supervisor | Return inside `d_min` (including orbited colony), geofence edge, stale data, NaN, invalid `dt` | Overrides always win; zero motion toward hazards; interventions logged |
| State machine | All transitions, including from every state to `FALLBACK` | Only allowed transitions occur; each is logged |
| Radio mock | Connect failure, missing variables, timeouts, disconnect, connection-only guards | Errors visible; handles close; connection-only performs zero arm/takeoff/setpoint calls |
| JSONL | All record types, nulls, non-finite values, overflow, disk failure, truncated final line | Strict lines; metadata first; drops and errors visible; exporter produces valid JSON |
| Simulator end-to-end | Seeded layouts, planner and baselines | Deterministic results per seed; zero safety violations; planner beats baselines on the evaluation set |

Suggested first failing tests: beam projection for the left beam at yaw +90° produces the expected world point, and a hit outside the geofence produces no candidate.

## 16. Staged implementation and gates

### Stage A — hardware inventory and no-flight sensor characterization

1. Connection-only inspection: Crazyflie model, firmware, decks, available log variables, effective update rates, prop/guard footprint.
2. With propellers removed and motors disabled, carry the drone at flight height through a test arena. Record ranges, timestamps, and state while approaching and circling each colony type from several angles and distances.
3. Measure: reliable detection range per beam; dropout rate; width-estimate error per tier; minimum spacing at which two colonies remain separable; Flow-deck drift over a typical mission duration (compare the estimated path with tape-measured positions).
4. Short supervised battery test (if approved): fit the voltage-to-remaining-flight-time model.

**Gate:** colonies are detected repeatably at the planned flight height and standoff distances; size tiers are distinguishable; spacing and drift budgets are recorded. If detection is unreliable, change colony size, material, flight height, or spacing before any flight work.

### Stage B — algorithms, simulation, and TDD

1. Implement pure modules (projection, mapping, visibility, collection, planner, controllers, safety) test-first.
2. Build the simulator using Stage A sensor parameters.
3. Implement baselines and run the evaluation protocol.
4. Replay Stage A recordings through the mapper to confirm detections match ground truth.

**Gate:** full test suite green; zero safety violations in simulation; planner beats baselines on the evaluation set; Stage A replay produces correct colony maps.

### Stage C — connection-only hardware and logging

1. Mock-test the radio wrapper and logger, proving no arm/takeoff/setpoint calls.
2. Connect to the real aircraft with propellers removed; verify decks, variables, rates, freshness, and clean disconnect.
3. Run the full perception pipeline live while carrying the drone by hand (no flight); check the live map against the real layout. Export and inspect logs.

**Gate:** live hand-carried mapping matches the real layout; logs are complete; actual rates are recorded.

### Stage D — supervised flight progression

Each step requires the previous one to pass, a reviewed checklist, a dedicated safety operator, and a clear arena.

1. Takeoff, hover over the home pad, land.
2. Takeoff, `SCAN`, land. Compare the in-flight map with the real layout.
3. Single colony: `TRANSIT` and `HARVEST` orbit at a conservative standoff, then return. Verify standoff tracking and clearance.
4. Two colonies with the planner, generous reserve.
5. Full mission on randomized layouts, then baselines on the same layouts for comparison.

After every run, review clearance minimums, safety interventions, planner decisions, link gaps, drift, and battery margin before expanding the envelope.

**Gate:** team- and mentor-approved thresholds met across repeated supervised runs. Simulation, synthetic feeds, or a successful radio handshake never satisfy this gate.

## 17. Acceptance criteria

Software (testable now, without physical numbers):

- Projection, frame, and unit fixtures produce exact expected values.
- Noise, walls, and moving objects are never promoted to colonies in tests.
- Collection, leaving, orienteering, and energy-feasibility behavior match hand-solved cases.
- Every command is finite, bounded, and passes through the safety supervisor; overrides always win.
- Stale or missing data always stops horizontal motion.
- Connection-only tests observe zero arm/takeoff/setpoint calls.
- Logs are strict JSONL with metadata first, unique filenames, all record types, and valid export.
- In simulation, zero safety violations across the evaluation set, and the planner's mean collected value exceeds every baseline.

Physical (thresholds agreed after Stage A, before Stage D):

- Detection reliability at flight height and the agreed ranges.
- Standoff error during orbit within tolerance; minimum clearance never below `d_min`.
- Battery at landing never below the agreed reserve.
- Zero safety violations across supervised runs.
- Planner outperforms at least the nearest-first baseline on the same physical layouts.

## 18. Docker and development environment

Unchanged from the previous design: Docker is not required. Use native host processes for the mission, with Windows owning the Crazyradio and the browser running any dashboard. The root `Dockerfile` and `docker-compose.yml` are generic and not mission images. If containers are later used for non-radio services, mount host directories for output and verify any device pass-through explicitly.

## 19. Commands and current limitations

The branch is docs-only. No Mission 1 CLI exists yet. Existing commands (the obstacle-navigation simulation in `reactive_nav.py`, the dashboard bridge, and the dashboard frontend) are documented in the previous design and remain unrelated to this mission's behavior. Do not use `reactive_nav.py --fly` as a substitute: it arms and flies a fixed-goal behavior. The new simulation, connection-only, and flight modes will be documented only after their CLI exists and is tested.

## 20. Decisions required before the flight design is frozen

1. **Colony objects:** what will be used (bins, boxes, tubes), their exact widths, heights, materials, and how many are available.
2. **Arena:** available floor area in the demo room, floor texture, home pad location, and how people will be kept outside the tape.
3. **Hardware:** exact Crazyflie model and firmware; confirmation that Flow v2 and Multi-ranger are installed; prop guard footprint; battery type and count.
4. **Envelope:** flight height, standoff distance, `d_min`, speed caps, and energy reserve, all from Stage A data.
5. **Scoring:** the richness constant, harvest time constant, and whether colony value uses area or tiers.
6. **Safety:** who supervises flight, kill-switch procedure, behavior on target loss versus radio loss, and verified onboard commander-timeout behavior.
7. **Integration boundary:** backend-only PR first, with the dashboard mission view as a separate follow-up.

## 21. Stretch goals

- **Landmark-based drift correction** using repeated colony sightings (section 6.7).
- **Moving colonies:** colonies relocated mid-run; the mapper must detect loss and rediscover them.
- **Contested harvest:** a slowly moving "Taumoeba" obstacle (a person-carried board, or a second drone in a later phase) that the planner must avoid while harvesting.
- **Cooperative harvest:** two Crazyflies sharing one colony map and dividing colonies between them (requires multi-drone radio and safety review).
