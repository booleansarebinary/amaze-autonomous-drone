# Reactive navigation analysis

Latest update: see [smoothing.md](smoothing.md) for the obstacle-encounter
command fix, current tests, and a fresh before/after benchmark. The following
sections are historical results from the earlier navigation changes.

Follow-up tuning requested by the user: the flight influence radius is now
1.00 m and its wall-following target is 0.30 m. At 20 Hz, open, wall, trap, and
pocket reach their goals; slalom times out after 120 seconds. No collisions occur
in these five runs. The fixed-scenario regression test consequently fails for
flight/slalom; the other five test methods pass. The 150-layout and delay results
below describe the earlier 1.30 m influence / 0.35 m wall-target configuration
and have not been rerun for this adjustment.

The earlier configuration completed the five fixed scenarios with both profiles at
20 Hz, including a new scenario that starts inside a concave pocket. This is an
improvement, but the algorithm remains incomplete and sensitive to control rate.
It is not yet a reliably collision-free navigation system.

## What failed and what changed

- **Boundary switching:** choosing the nearest beam every tick can switch from
  the followed obstacle to the opposite wall. That reverses the tangent and
  creates repeated loops in slalom layouts. Escape now retains its boundary
  direction, accepts nearby perpendicular handovers, and turns toward the last
  boundary when it disappears at a corner. Panic and proximity checks still use
  the actual nearest obstacle, independently of the tracked boundary.
- **Wrong escape side:** choosing solely by alignment with the goal can select
  the short dead end beside an obstacle attached to a room wall. Escape now
  compares sensed clearance along both candidate tangents first.
- **Incompatible standoff:** the original flight target was 0.60 m in scenarios
  with 0.80 m passages. Targets are now 0.35 m for flight and 0.30 m for simulation.
  These are empirical settings, not clearance guarantees.
- **Optimistic collision checks:** the original simulator treated the drone as
  a point and reported the shortest sensor reading as clearance. The revised
  simulator checks a 0.09 m circular footprint against geometry over the entire
  motion segment, including blind corners and thin obstacles. A collision takes
  precedence over goal arrival.
- **Simulation fidelity and speed:** vectorized ray casting matches the scalar
  ray implementation in regression tests. A stable exponential velocity-lag
  update replaces explicit Euler. Simulation accepts sensor delay and initial
  yaw. The original trap tests the outside of a U; the new pocket test starts
  inside it and requires moving away from the goal.

## Results

Baseline is the user's existing, staged controller at the start of this task,
Git blob `e69c4db9b5b07e63144f0eb969e2649b741fe928`, not repository HEAD.
No hardware or radio connection was used.

The original simulator reported success for all four original scenarios with
simulation gains, but only the open scenario with flight gains. For the fair
comparison below, both old and new controllers run in the **same revised
simulator**, with the same 150 layouts, seed 7, 120-second limit, 20 Hz control,
0.25-second velocity response, and 0.09 m footprint.

| Profile | Version | Reached | Collided | Timed out |
|---|---|---:|---:|---:|
| Simulation | Before | 131/150 | 1 | 18 |
| Simulation | After | 142/150 | 2 | 6 |
| Flight | Before | 98/150 | 0 | 52 |
| Flight | After | 129/150 | 0 | 21 |

The faster profile improves completion but has **one more collision** in this
sample. The flight profile improves from 65.3% to 86.0% completion without
observed collisions. Neither result establishes safety; randomized layouts are
not certified for reachability, and these are a single seed's static rectangles.
Per-scenario durations, true minimum clearance, and failing zero-based trial
indices are stored in `benchmark.json`.

At 15 Hz (the flight loop default), flight-profile sensitivity results are:

| Sensor delay | Velocity response | Reached / 5 | Collisions | Timeouts |
|---|---|---:|---:|---|
| 0 s | 0.25 s | 4 | 0 | wall |
| 0.10 s | 0.50 s | 4 | 0 | wall |
| 0.20 s | 0.75 s | 2 | 0 | wall, slalom, pocket |

Delay is rounded up to whole simulation steps. Ranges and yaw are delayed
 together; position and velocity remain exact. This does not model the full
radio/estimator/autopilot stack, asynchronous sensor rates, drift, noise, or
moving obstacles. Arrival stops the simulation at the tolerance boundary and
does not validate subsequent braking/hover behavior.

## Remaining problems

1. `_goal_visible` is only a local heuristic. It cannot establish visibility
   through diagonal blind wedges or beyond the influence radius. Disabling yaw
   sweeping in the flight profile leaves those wedges unsensed. Smoothing does
   not restore missing coverage.
2. This is not Bug2: there is no m-line, obstacle map, or complete boundary loop
   detector. Minimum dwell and repeated-entry heuristics can still cycle.
3. Normalizing the potential-field vector to a fixed speed magnifies tiny
   residual forces near equilibrium. Median and command filters add delay;
   several filter settings are per sample rather than per second.
4. The flight adapter has no explicit stale-telemetry watchdog. `None` ranger
   readings are treated as clear, and zero ranges are ignored or filtered as
   clear. Actual sensor status and freshness need independent handling.
5. Hardware estimator yaw hold cannot independently observe gyro drift. The
   ideal world-frame simulation does not validate the physical frame conversion.

The next substantive change should address sensing coverage and an explicit
motion safety constraint before increasing speed: scan/align toward unsensed
travel directions, bound closing velocity using measured delay and braking,
and add a boundary-loop recovery policy. Re-tuning gains alone did not remove
the observed control-rate failures.

## Reproduce

The IDE environment tool reported that this file belongs to no module. Runs used
the existing project `.venv` (Python 3.10); no IDE configuration was changed.

```sh
.venv/bin/python -m unittest algorithms.test_reactive_nav -v
.venv/bin/python algorithms/reactive_nav.py --scenario all --profile flight --no-plot
.venv/bin/python dev_scripts/benchmark_reactive_nav.py --output /tmp/nav-current.json
.venv/bin/python dev_scripts/benchmark_reactive_nav.py --baseline /path/to/original/reactive_nav.py --output /tmp/nav-comparison.json
```

Six regression tests pass, including both profiles across all five fixed
scenarios, ray equivalence, blind-corner collision, swept clearance, arrival
precedence, and invalid simulation parameters. These assert nominal behavior;
the sensitivity failures remain explicitly recorded rather than hidden.

The optional `--save` plot path still requires Matplotlib, which is absent from
this virtual environment. Numerical benchmarks do not require it.
