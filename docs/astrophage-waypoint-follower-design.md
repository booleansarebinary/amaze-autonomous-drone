# Waypoint follower design: inspection only

This is a proposed connection between the existing offline routes and a future
drone adapter. No follower, telemetry connection, or flight behavior is added.
A planned route does not demonstrate physical flight readiness. The current
priority remains offline navigation while sensor hardware is unavailable.

## What the inspected code actually provides

| Source and interface | Observed behavior | Design implication |
|---|---|---|
| `algorithms/grid_navigation.py`: `astar` | Returns cardinal cells, including both endpoints, or no route | Reuse this planner and its supplied clearance map |
| `GridCoordinates.cell_center` / `world_to_cell` | Square cells in meters; origin is the lower-left outer edge | Use these conversions; reject invalid coordinates without clamping |
| `algorithms/candidate_visits.py`: `CandidateVisits` | Orders candidates, accepts explicit visit confirmation, switches to return on a simulated event | Keep mission choices here; the follower reports progress rather than choosing candidates |
| `algorithms/astrophage_collection_script.py`: `to_meters`, `corners`, `fly` | Uses integer grid-point positions, removes straight intermediate points, sends `pc.go_to(x, -y)` and waits between stops | Preserve this separate script; do not connect its coordinate conventions or timed moves directly to cell-center routes |
| Installed cflib 0.1.33: `PositionHlCommander.go_to` | Calculates duration from remembered coordinates, sends a high-level command, sleeps, then updates those coordinates | Return from this method does not confirm measured arrival |
| Same class: `get_position` | Returns remembered `_x`, `_y`, `_z` | This is not the measured pose needed by a feedback loop |
| Installed `high_level_commander.go_to` | Supports absolute/relative commands; documentation describes curved paths from nonzero initial velocity and warns against overlapping commands | A segment between grid cells does not establish that the generated trajectory stays in it |
| Installed `high_level_commander.stop` | Its documentation explicitly says it turns motors off | Never map a generic pause/hover request to this method |
| Installed `MotionCommander.start_linear_motion` / `stop` | Nonblocking body-axis velocity request; `stop` requests zero velocities to hover | Potential reuse for a future interruptible velocity adapter; zero velocity is not proof of holding an absolute location |

External source inspection used the existing sibling checkout:
`C:/Users/victo/amaze-test-flight/algorithms/reactive_nav.py`, and installed
library files below that checkout's `.venv/Lib/site-packages/cflib/`:
`positioning/position_hl_commander.py`, `positioning/motion_commander.py`,
`crazyflie/high_level_commander.py`, and `utils/reset_estimator.py`.
These are inspected local versions, not claims about every library/firmware
version. The installed package metadata identifies version 0.1.33.

Ansur's `ReactiveController.step(ranges, pos, yaw, dt, vel)` is separable
from its radio loop and returns world-axis velocity, yaw rate, and state.
It steers toward a goal and away from range readings, with an escape behavior
when progress stalls. It can leave a grid route and does not guarantee arrival.
Its arrival decision uses distance alone; that is insufficient for settling.
Reuse its pure computation only after reconciling frames and testing command
ownership. Its flight entry point must not be reused as a second command loop.

That entry point subscribes with `LogConfig(period_in_ms=50)` to
`kalman.stateX`, `kalman.stateY`, `kalman.statePX`, `kalman.statePY`, and
`stabilizer.yaw`. It treats the PX/PY fields as velocities and converts yaw
from degrees to radians. Its estimate dictionary starts at zero, ignores
the callback's device timestamp, has no sample-age gate, and lacks altitude
feedback in that log block. Those values are not a ready-made pose provider.
Variable availability, meaning, units, and estimator selection must be checked
against the actual firmware log table before reuse.

The collection script calls `reset_estimator` and comments that this makes
the current position zero. The inspected helper toggles `kalman.resetEstimation`
and waits for a small spread in variance history; it does not explicitly set
a map origin or measure absolute position error. Neither reset nor a detected
Flow deck establishes map alignment, bounded drift, or usable localization.

## Frames, first movement, and home

Use the existing cell-center convention: for cell `(x, y)`, meter position is
`origin + ((x + 0.5) * size, (y + 0.5) * size)`. Diagram +y points up the page;
that does not mean body-left or body-right on the physical drone.
The collection script instead uses `origin + (x * CELL, y * CELL)` and its own
y-sign flip. Combining these would introduce a half-cell offset and possibly
a mirrored route. Its rounding-based `to_cell` is not the containing-cell
conversion used by `GridCoordinates`.

The future adapter needs one explicit, calibrated transform between map
coordinates and estimator coordinates: origin offset, orientation, axis signs,
meters, altitude reference, and yaw units. Apply it exactly once. Convert
world-axis velocity to body axes using measured yaw before a MotionCommander
request, as the reactive adapter demonstrates; no unconditional y-flip is
assumed. Test distinct positive-axis movements and nonzero headings offline.

Before planning, transform a fresh measured pose into the map frame and use
`world_to_cell`. Reject outside/blocked cells and inadequate clearance. Then
validate the continuous movement from that actual pose to the first center,
including the footprint, uncertainty, arena walls, and tracking allowance.
No existing function performs this pose-to-route connection check. Do not
skip the first route cell merely because its index matches the start cell.
Only skip its center if measured settling criteria and the next-segment
clearance check already hold. Replan if a new actual start invalidates a route.

The initial proposal keeps every cell center as a waypoint. Do not use
`corners` or another shortcut until the resulting swept path is independently
checked. Checking waypoint cells alone does not validate turns, tolerance
regions, overshoot, or a command's curved trajectory.

Record home from fresh measured pose after localization is usable. Keep that
exact pose as well as its planning cell. Returning to the home cell center
does not prove arrival at the original takeoff point. Any final connection
to that point and landing area requires a separate collision/arrival check.
Takeoff and landing are vertical movements outside the 2D A* model.

## Proposed measured-position loop

A pose snapshot means one coherent sample of position `(x,y,z)`, velocity,
yaw, validity/estimator health, device sequence/time when available, and host
monotonic receipt time. Monotonic time measures elapsed time without wall-clock
adjustments. Never initialize missing position as a valid zero or combine
fresh x with an old y from an independently updated dictionary.

The initial adapter proposal reuses a single MotionCommander-style streaming
velocity family for an interruptible feedback loop; it does not wrap blocking
`PositionHlCommander.go_to` calls in a second thread. Its concrete control law,
limits, and pause behavior require later offline implementation and validation.
The library's background sender and automatic context-entry takeoff/context-exit
landing must be included in command ownership; constructing a context is not
a harmless way to inspect the adapter. Its takeoff path also resets the
estimator; establish the final frame/home after the last reset and invalidate
any earlier pose-to-map alignment that the reset changes.

1. Accept a route only with its grid/configuration and current mission revision.
   A revision identifies the active plan so canceled work cannot later send
   commands. Validate endpoints, each cell, each cardinal step, and altitude.
2. On each update, require fresh valid pose and usable link/estimator health.
   Validate the current pose and remaining allowed movement region.
3. Compare measured position with the current waypoint, enforce bounded speed
   and acceleration, and keep the path inside the clearance allowance. Send
   only the request chosen by the one command owner.
4. Advance only when horizontal error, altitude error, and measured speed stay
   below configured limits for a continuous settling interval. A momentary
   fly-through, elapsed command time, or repeated old sample is insufficient.
5. Before the next segment, check the actual settled pose's connection to it.
   A tolerance circle can otherwise cut a corner even with cardinal waypoints.
6. At the final candidate, report verified arrival to mission logic before
   it calls `confirm_visit`. Home arrival and landing remain separate events.

All tolerances, sample-age limits, timeouts, speed/acceleration limits, and
settling times are unvalidated configuration requirements, not adopted flight
defaults. Footprint, localization error, tracking error, and braking distance
must fit the chosen margin; an arrival tolerance must not consume it twice.
Excess route deviation, stalled progress, invalid pose, or a changed map pauses
progress and invalidates unsafe remaining movement. Do not snap the drone to
a cell or claim a visit after a timeout.

## Stale data and command ownership

On stale, missing, nonfinite, reordered, or invalid pose: stop advancing and
cancel travel intent. Reset any settling timer. Request the adapter's validated
pause/fault response and report the cause. Reacquire fresh pose and explicitly
revalidate/replan before resuming. A repeat of the same timestamp cannot extend
settling. On reconnect/reset, invalidate old samples, route revisions, and any
home/frame assumptions that no longer hold. Device clock wrap/reset and queued
old messages need an explicit policy; fresh receipt time alone is insufficient.

Do not assume zero commanded velocity guarantees position hold with bad
localization. Do not send high-level motor-off `stop` as a hover request.
If radio is lost, a host pause command cannot be assumed to arrive; firmware
watchdog behavior and the operator response must be established beforehand.
This design does not prescribe an unvalidated universal hold/land action.

One mission-owned command adapter must be the sole writer. Search, return,
reactive avoidance, and operator/fault handling submit intentions to it rather
than sending competing radio requests. Fault/operator intervention has priority;
mission transitions revoke earlier route revisions before accepting new motion.
Do not run the collection script's `fly` loop alongside the reactive flight loop.

With sensors unavailable, reactive avoidance is not enabled and supplied maps
remain static assumptions. Future reactive output may restrict or replace a
navigation request only through the same owner, with current valid measurements.
If it moves outside the validated route region, stop waypoint advancement,
check clearance, and replan from measured pose. An escape maneuver is not
automatic permission to bypass mapped obstacles. Invalid range data is not
evidence of a clear path.

The existing `simulate_detection` immediately switches offline routing to home;
it does not implement the physical mission's hold, verified settling, collection
dwell, and return authorization. A later physical mission integration must
cancel search first, perform those distinct stages, then request return planning
from fresh measured position. Do not attach sensor events directly to movement.

## Hypothetical worked example, not an executed follower

Assume a supplied 5-by-4 map with blocked `(2,1)`, 0.25 m cells, zero origin,
and route `[(1,1), (1,2), (2,2), (3,2)]`. Converted centers are
`[(0.375,0.375), (0.375,0.625), (0.625,0.625), (0.875,0.625)]` meters.
These are hand-calculated design inputs/outputs, not measured flight data.

For illustration only, suppose the horizontal tolerance is 0.04 m, altitude
tolerance 0.03 m, speed limit for settling 0.05 m/s, settling interval 0.30 s,
and maximum sample age 0.15 s. None is an approved physical setting.
Measured map position `(0.38,0.39)` is about 0.016 m from the first center.
After checking the actual-pose connection, fresh samples satisfying all limits
for 0.30 s would permit the next segment toward `(0.375,0.625)`. A speed of
0.08 m/s would prevent advancement despite small position error. A sample aged
0.20 s would pause progress and reset settling, not select the next waypoint.
Resume would require fresh evidence and a validated connection to the route.

## Evidence required before physical use

- Offline fake-pose/fake-command tests: no commands before valid pose; distinct
  coordinate axes and yaw; checked initial/final connections; sustained arrival;
  stale/duplicate/reconnected samples; deviation/timeout; cancellation; sole
  command ownership; no return through obstacles. Mutations are due when that
  implementation exists, not for this design document.
- Telemetry-only inspection: discover actual firmware variables/units, verify
  coherent position/velocity/yaw/altitude, timestamps, estimator health and
  usable update timing. No takeoff, arming, or commander contexts in this step.
- Validate fixed-altitude operating volume, overhangs/ceilings, takeoff/landing
  space, frame alignment, localization accuracy/drift, footprint and uncertainty
  budget. Measure tracking/overshoot, braking, latency, and settled arrival.
- Verify pause behavior, firmware watchdog/link-loss behavior, exclusive command
  ownership, and operator intervention in a separately approved physical plan.
  Proceed to short controlled movements only after the earlier evidence exists.

No radio connection, flight command, hardware measurement, or follower test was
performed for Chunk 9. The integration and all physical requirements remain open.
