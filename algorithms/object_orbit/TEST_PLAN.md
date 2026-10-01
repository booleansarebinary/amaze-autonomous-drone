# Validation and Next Tests

## Executed for this starter

Run from the repository root:

```bash
python -m unittest discover -s algorithms/object_orbit -p "test_*.py" -v
```

| Automated check | Expected result |
| --- | --- |
| Isolated circle | COMPLETE; ground-truth clearance above 0.20 m |
| Isolated box | COMPLETE; ground-truth clearance above 0.20 m |
| Empty scene | ABORT with mission time-limit reason |
| Missing or invalid scan | Zero output and ABORT |
| Target loss | Zero output, REACQUIRE, then ABORT after timeout |
| Surface direction rotates while position stays fixed | Does not report a completed lap |
| A surface inside the stop distance | Zero output and ABORT |
| Abrupt target direction change | REACQUIRE instead of silently switching |

All eight tests were run successfully for the packaged version. Circle and box
plots were generated from actual simulation traces. The README records their
time and clearance results. These checks test the concept controller under its
stated assumptions; they do not establish readiness for flight.

## Before expanding the algorithm

- Add scenarios with an object initially outside detection range and to the
  side of the search corridor; evaluate search coverage separately from orbiting.
- Use multiple objects and room walls to expose nearest-surface target switches.
- Try rectangular, rounded, concave and narrow targets at different orientations.
- Repeat with varied start positions and candidate ranges rather than only the
  current deterministic examples.
- Test brief range dropouts, false returns and sudden object movement.

Record completion rate, target switches, nearest true clearance, recovery count
and time to complete or abort. A failed scenario belongs in the result table,
not hidden by retuning only that scenario.

## Before a hardware adapter

- Replace ideal sweeps with four horizontal beams and realistic fields of view.
- Model the time and yaw changes required to assemble an active scan.
- Add velocity response lag, acceleration and braking behavior.
- Include range noise, message delay, stale packets and odometry drift.
- Test the local/world coordinate transform and yaw unit/sign conventions.
- Make missing packets distinguishable from valid no-return measurements.

## Before supervised flight

Confirm deck detection and actual vehicle dimensions. Validate sensor and pose
logging, time freshness, command rates, link-loss handling and a reviewed landing
path. Test the integration against the team's pinned software versions and
verify emergency-stop behavior with the team's normal procedure. The prototype
does not provide any of these flight capabilities.

Real-flight acceptance criteria should be agreed with the team: target geometry,
search boundary, permitted clearance, height, speed, mission duration and what
constitutes a completed orbit. Simulation gains are initial design values, not
approved flight settings.
