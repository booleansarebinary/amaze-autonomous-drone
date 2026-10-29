# Smoother obstacle encounters

The user reported aggressive swerving during real flight after setting the
reaction radius to 1.00 m and wall-following target to 0.30 m. Those distances
and the 0.28 m/s cruise cap remain in place.

## What happens at a wall

1. Below 1.00 m, the sensed obstacle adds a repulsive vector to the goal vector.
   In a head-on approach, these balance around 0.44 m with the flight gains.
2. If best distance-to-goal improves by less than 0.08 m for 2.5 seconds,
   the controller switches to escape: a tangent along the boundary plus a
   correction toward the 0.30 m wall-following distance.
3. After a minimum dwell, a locally clear goal direction allows seeking again.
   Repeated encounters extend that dwell. The visibility test remains heuristic.
4. Below 0.30 m, stronger repulsion takes priority. With a 0.30 m wall target,
   small undershoots can enter this band; smooth motion is not guaranteed there.

## Cause and implementation

The old code normalized every nonzero potential-field result to cruise speed.
Consequently, a tiny sign change around the force balance could request nearly
full-speed motion in the opposite direction. Median and command filtering
softened this but did not remove its cause. State changes and loss of a wall
at a corner also change command direction abruptly.

The revised controller:

- Preserves small field magnitudes near equilibrium, allowing the approach to
  slow naturally instead of amplifying small residuals to cruise speed.
- Limits ordinary world-frame command changes to 2.0 m/s². At 15 Hz this is at
  most 0.133 m/s per tick. This bounds velocity slew, not mathematical jerk or
  the vehicle's actual acceleration.
- Makes the existing command filter depend on elapsed seconds and supplies
  measured monotonic loop time in the flight adapter.
- Limits velocity toward each sensed obstacle to
  `max(0, (range - 0.30 m) / 0.60 s)` after smoothing, preserving tangential
  motion. This is a local closing-speed constraint, not a collision guarantee.
- Uses fresh below-panic readings immediately, bypassing the median window.
  Urgent corrections and closing-speed constraints override comfort smoothing;
  an urgent or spurious close return can still produce a sharp response.

More restrictive slew limits (0.4–1.5 m/s²) and lower cruise speeds were explored.
They introduced additional corner-tracking lag and delayed-sensing failures.
The selected limit retains response speed; merely increasing smoothing is not
an adequate fix.

## Validation

Eleven regression tests pass, including small-range-noise behavior, variable-time
slew bounds, immediate response to a close return, closing-speed limits, and
both profiles across five fixed scenarios at 20 Hz.

A controlled stationary input at the head-on equilibrium, alternating ±5 mm
range perturbations for 30 ticks at 15 Hz, produced:

| Command metric | Before | After |
|---|---:|---:|
| Peak speed | 0.280 m/s | 0.00358 m/s |
| RMS speed | 0.11195 m/s | 0.00201 m/s |
| Peak velocity-command change / dt | 2.835 m/s² | 0.0521 m/s² |

These are synthetic command measurements, not measured physical motion or
estimator drift. Raw results are in `smoothing_noise_test.json`. The test uses
flight defaults and no measured-velocity input; it isolates the cancellation
problem before the stall timer triggers escape.

The separate `smoothing_benchmark.json` compares the immediately preceding
1.00 m / 0.30 m controller with this version using identical randomized layouts.
Its baseline source has Git blob hash
`8da0c1958e2d0d9126c82f9c7e631af4504f97b9`. Earlier `benchmark.json` results used
different settings and should not be read as results for this change.

At 20 Hz, seed 7, a 120-second limit, and 0.09 m drone radius:

| Profile | Before: reached / collided / timeout | After: reached / collided / timeout |
|---|---:|---:|
| Flight | 133 / 2 / 15 | 131 / 0 / 19 |
| Simulation | 142 / 2 / 6 | 140 / 0 / 10 |

Each row uses the same 150 layouts before and after. Collision counts improve
in this sample, at the cost of two fewer arrivals per profile. These layouts
are not certified for reachability, and a single seed does not establish safety.

Delayed sensing still exposes limitations. At 15 Hz the five nominal flight
scenarios finish; with 0.10 s sensor delay and 0.50 s velocity response, slalom
times out. At 0.20 s delay and 0.75 s response, the wall case collides and slalom
times out. Sparse sensing, blind corners, and state-machine loops remain.

No hardware was operated. The smoother commands may reduce abrupt motion, but
this does not establish that swerving caused accumulated position drift or that
drift is fixed. Estimated yaw hold uses the same estimator and cannot independently
correct unobserved gyro bias. Compare flight telemetry with observed motion to
separate commanded oscillation from localization error.

Run the existing flight command with `--diag` to print estimated position,
velocity, yaw, and command vectors. It uses the updated flight defaults.
