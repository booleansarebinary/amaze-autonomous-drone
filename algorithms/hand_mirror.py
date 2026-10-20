"""
Hand-mirroring demo for the Crazyflie 2.x using the Flow deck + Multiranger deck.

Instead of fleeing from a nearby hand (like the original "push" example),
this keeps the drone trying to hold a fixed TARGET_DISTANCE from your hand
on each axis (front/back, left/right, up). Move your hand further away on
an axis -> the drone follows to close the gap. Move it closer -> the drone
backs off. This is a proportional "leash" controller, not true absolute
position tracking, but for slow, roughly axis-aligned hand motion it feels
like mirroring.

Press Ctrl-C to land and exit (the old "hand above drone = land" gesture is
removed since the up-sensor is now used continuously for z control).
"""
import logging
import sys
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander
from cflib.utils.multiranger import Multiranger

URI = 'radio://0/80/2M'

logging.basicConfig(level=logging.ERROR)

# --- Tuning knobs ---
TARGET_DISTANCE = 0.5   # (m) desired gap to hold from your hand on each axis
DEADBAND = 0.03         # (m) ignore error smaller than this, to reduce jitter
KP = 1.5                # proportional gain: velocity = KP * error
KD = 0.8                # gain on how fast the gap is changing (hand speed relative to drone)
MAX_VELOCITY = 0.8      # (m/s) clamp so it doesn't lurch
LOOP_DT = 0.05          # (s) ~20 Hz control loop
MIN_DETECT_DISTANCE = 0.12  # (m) closer than this is sensor noise / prop guard
MAX_DETECT_DISTANCE = 0.8   # (m) a new hand must appear within this to be picked up
LOST_DISTANCE = 1.3         # (m) once locked on, keep following the hand out to this
JUMP_REJECT = 0.3           # (m) a jump bigger than this in one tick means the hand left the beam
FILTER_ALPHA = 0.5          # 0..1, weight of each new distance reading (higher = less smoothing)
RATE_ALPHA = 0.3            # 0..1, weight of each new rate-of-change estimate
MIN_HEIGHT = 0.2            # (m) never command a descent below this height
MAX_HEIGHT = 1.0            # (m) never command an ascent above this height
DESCEND_ABOVE_HEIGHT = 0.7  # (m) a hand above can only push the drone down above this
SAFE_CLEARANCE = 0.35       # (m) don't move toward an obstacle closer than this


class HandTrack:
    """Tracks a hand seen by one ranger: lock-on, smoothing and closing rate.

    A hand is picked up only within MAX_DETECT_DISTANCE (so walls aren't
    grabbed), but once locked it is followed out to LOST_DISTANCE. Without
    that hysteresis, a hand pulled away leaves the 0.5-0.8 m window before
    the drone catches up, and the drone stops dead.
    """

    def __init__(self):
        self.distance = None  # filtered distance while locked, else None
        self.rate = 0.0       # filtered d(distance)/dt, m/s

    @property
    def locked(self):
        return self.distance is not None

    def update(self, measured, dt):
        if not self.locked:
            if measured is not None and MIN_DETECT_DISTANCE <= measured <= MAX_DETECT_DISTANCE:
                self.distance, self.rate = measured, 0.0
            return

        if measured is None or measured > LOST_DISTANCE:
            self.distance = None
            return
        # A hand closer than the noise floor should push hardest, not vanish.
        measured = max(measured, MIN_DETECT_DISTANCE)
        if abs(measured - self.distance) > JUMP_REJECT:
            # Hand slid out of the beam and the sensor now sees what's behind it.
            self.distance = None
            return

        previous = self.distance
        self.distance += FILTER_ALPHA * (measured - self.distance)
        if dt > 0:
            new_rate = (self.distance - previous) / dt
            self.rate += RATE_ALPHA * (new_rate - self.rate)


def track_velocity(track, sign=1.0):
    """
    Turn a locked hand track into a velocity command that tries to
    hold TARGET_DISTANCE from it. The KD term reacts to the hand moving
    before the gap has grown, which is what makes it feel responsive.
    sign flips which physical direction counts as "closing the gap"
    for that particular sensor's mounting orientation.
    """
    if not track.locked:
        return 0.0  # nothing that could be a hand on this axis, don't move on it

    error = track.distance - TARGET_DISTANCE
    if abs(error) < DEADBAND:
        error = 0.0

    velocity = sign * (KP * error + KD * track.rate)
    return max(-MAX_VELOCITY, min(MAX_VELOCITY, velocity))


def axis_velocity(positive, negative):
    """Velocity along one axis from the two opposite-facing sensor tracks.

    positive is the track facing the +axis direction (front or left),
    negative the one facing the -axis direction (back or right). Only the
    nearer locked track is followed, since that is most likely the hand;
    following both would make the drone settle midway between your hand and
    whatever is on the other side.
    """
    if positive.locked and (not negative.locked or positive.distance <= negative.distance):
        return track_velocity(positive)
    if negative.locked:
        return track_velocity(negative, sign=-1.0)
    return 0.0


def respect_clearance(velocity, positive, negative):
    """Cancel motion toward an obstacle closer than SAFE_CLEARANCE."""
    if velocity > 0 and positive is not None and positive < SAFE_CLEARANCE:
        return 0.0
    if velocity < 0 and negative is not None and negative < SAFE_CLEARANCE:
        return 0.0
    return velocity


class HandFollower:
    """Holds one HandTrack per ranger and turns readings into velocities."""

    def __init__(self):
        self.tracks = {name: HandTrack() for name in ('front', 'back', 'left', 'right', 'up')}

    def step(self, dt, front, left, up, height=None, back=None, right=None):
        readings = {'front': front, 'back': back, 'left': left, 'right': right, 'up': up}
        for name, measured in readings.items():
            self.tracks[name].update(measured, dt)
        return compute_velocities(self.tracks, front, left, height, back, right)


def compute_velocities(tracks, front, left, height=None, back=None, right=None):
    """One control tick: hand tracks plus raw ranger readings in, a body-frame velocity out.

    x-axis: front/back sensors. Positive x is forward, so a hand moving away
            in front pulls the drone forward, and a hand moving away behind
            pulls it backward.
    y-axis: left/right sensors. Positive y is left in the body frame.
    z-axis: the up sensor; a growing distance above means the hand moved up,
            so follow it upward. A hand close above only pushes the drone
            down while it is higher than DESCEND_ABOVE_HEIGHT.

    height (optional) is the down-ranger reading; descent is dropped below
    MIN_HEIGHT (and below DESCEND_ABOVE_HEIGHT, or when height is unknown)
    and ascent above MAX_HEIGHT. back/right are optional so the
    drone still works with only front/left/up.
    """
    vx = axis_velocity(tracks['front'], tracks['back'])
    vy = axis_velocity(tracks['left'], tracks['right'])
    vz = track_velocity(tracks['up'])

    # Only climb, unless the drone is high enough that descending is safe.
    if vz < 0 and (height is None or height <= DESCEND_ABOVE_HEIGHT):
        vz = 0.0

    # Keep the drone between MIN_HEIGHT and MAX_HEIGHT above whatever is below.
    if height is not None:
        if (height <= MIN_HEIGHT and vz < 0) or (height >= MAX_HEIGHT and vz > 0):
            vz = 0.0

    # Don't move toward anything too close on the side we're heading for.
    vx = respect_clearance(vx, front, back)
    vy = respect_clearance(vy, left, right)
    return vx, vy, vz


def limit_climb_rate(vz, commanded_z):
    """Limit vz so the commanded height stays within [MIN_HEIGHT, MAX_HEIGHT].

    MotionCommander turns vz into a height setpoint that keeps integrating,
    and the drone lags behind that setpoint. Checking the *measured* height
    is too late: by the time it reads MIN_HEIGHT the setpoint is already
    near the floor, and the drone follows it down. So bound the setpoint
    itself, over the next tick.
    """
    lowest = (MIN_HEIGHT - commanded_z) / LOOP_DT
    highest = (MAX_HEIGHT - commanded_z) / LOOP_DT
    vz = max(lowest, min(highest, vz))
    return max(-MAX_VELOCITY, min(MAX_VELOCITY, vz))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    uri = argv[0] if argv else URI

    cflib.crtp.init_drivers(enable_debug_driver=False)

    cf = Crazyflie(rw_cache='./cache')
    with SyncCrazyflie(uri, cf=cf) as scf:
        scf.cf.platform.send_arming_request(True)
        time.sleep(1.0)

        with MotionCommander(scf) as motion_commander:
            # zranger=True so .down is populated for the height limits;
            # 50 ms matches LOOP_DT so each tick sees a fresh reading.
            with Multiranger(scf, rate_ms=50, zranger=True) as multi_ranger:
                # Track the height setpoint the same way MotionCommander
                # integrates it, so limit_climb_rate can bound it.
                commanded_z = motion_commander.default_height
                follower = HandFollower()
                last_vz = 0.0
                last_time = time.time()
                try:
                    while True:
                        now = time.time()
                        dt = now - last_time
                        vx, vy, vz = follower.step(
                            dt,
                            multi_ranger.front,
                            multi_ranger.left,
                            multi_ranger.up,
                            height=multi_ranger.down,
                            back=multi_ranger.back,
                            right=multi_ranger.right,
                        )
                        commanded_z += last_vz * dt
                        vz = limit_climb_rate(vz, commanded_z)
                        motion_commander.start_linear_motion(vx, vy, vz)
                        last_vz, last_time = vz, now
                        time.sleep(LOOP_DT)

                except KeyboardInterrupt:
                    print('Landing...')

        print('Demo terminated!')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
