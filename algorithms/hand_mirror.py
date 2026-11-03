"""
Hand-mirroring for the Crazyflie 2.x using the Flow deck + Multiranger deck.

This program keeps the drone trying to hold a fixed TARGET_DISTANCE from your hand,
seen by one of the front/back/left/right/up rangers. Move your hand further
away -> the drone follows to close the gap. Move it closer -> the drone
backs off. Only one ranger is followed at a time: the one whose reading
jitters most, since a hand is never perfectly still and a wall is. This is a proportional "leash" controller, not true absolute
position tracking, but for slow, roughly axis-aligned hand motion it feels
like mirroring.

If the drone climbs above KILL_HEIGHT it stops following and lands.

Press Ctrl-C to land and exit
"""
import logging
import statistics
import sys
import time
from collections import deque

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
KP = 7.0                # proportional gain: velocity = KP * error
KD = 2.5                # gain on how fast the gap is changing (hand speed relative to drone)
MAX_VELOCITY = 0.8      # (m/s) clamp so it doesn't lurch
LOOP_DT = 0.05          # (s) ~20 Hz control loop
MIN_DETECT_DISTANCE = 0.12  # (m) closer than this is sensor noise / prop guard
MAX_DETECT_DISTANCE = 0.8   # (m) a new hand must appear within this to be picked up
LOST_DISTANCE = 1.3         # (m) once locked on, keep following the hand out to this
JUMP_REJECT = 0.3           # (m) a jump bigger than this in one tick means the hand left the beam
FILTER_ALPHA = 0.5          # 0..1, weight of each new distance reading (higher = less smoothing)
RATE_ALPHA = 0.3            # 0..1, weight of each new rate-of-change estimate
MIN_HEIGHT = 0.2            # (m) never command a descent below this height
KILL_HEIGHT = 3.5           # (m) above this, stop following and land
SAFE_CLEARANCE = 0.35       # (m) don't move toward an obstacle closer than this
LIVELINESS_WINDOW = 1.0     # (s) how much rate history to measure jitter over
SWITCH_RATIO = 2.0          # another track must jitter this many times more to steal the target
MIN_LIVELINESS = 0.0005     # (m/s)^2 rate variance below this is too still to be a hand

# Which axis each ranger drives, and the sign that makes "gap growing" mean
# "move toward it". Positive x is forward, positive y is left, positive z is up.
SENSOR_AXES = {
    'front': ('x', 1.0),
    'back': ('x', -1.0),
    'left': ('y', 1.0),
    'right': ('y', -1.0),
    'up': ('z', 1.0),
}


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
        self.rates = deque(maxlen=max(2, round(LIVELINESS_WINDOW / LOOP_DT)))

    @property
    def locked(self):
        return self.distance is not None

    @property
    def liveliness(self):
        """Variance of rate over the last LIVELINESS_WINDOW: high for a hand, ~0 for a wall."""
        if len(self.rates) < 2:
            return 0.0
        return statistics.pvariance(self.rates)

    def update(self, measured, dt):
        if not self.locked:
            if measured is not None and MIN_DETECT_DISTANCE <= measured <= MAX_DETECT_DISTANCE:
                self.distance, self.rate = measured, 0.0
                self.rates.clear()
                self.rates.append(self.rate)
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
        self.rates.append(self.rate)


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

    """
    Main velocity calculation

    error is the difference between the current and target distance.
    track rate is the rate of change of the error.
    KP and KD are constants, the proportional and derivative gains, respectively.
    """
    velocity = sign * (KP * error + KD * track.rate)
    return max(-MAX_VELOCITY, min(MAX_VELOCITY, velocity))


def respect_clearance(velocity, positive, negative):
    """Cancel motion toward an obstacle closer than SAFE_CLEARANCE."""
    if velocity > 0 and positive is not None and positive < SAFE_CLEARANCE:
        return 0.0
    if velocity < 0 and negative is not None and negative < SAFE_CLEARANCE:
        return 0.0
    return velocity


class HandFollower:
    """Holds one HandTrack per ranger, picks a single target and turns readings into velocities."""

    def __init__(self):
        self.tracks = {name: HandTrack() for name in SENSOR_AXES}
        self.target = None  # name of the track being followed, or None

    def step(self, dt, front, left, up, height=None, back=None, right=None):
        readings = {'front': front, 'back': back, 'left': left, 'right': right, 'up': up}
        for name, measured in readings.items():
            self.tracks[name].update(measured, dt)
        self.target = choose_target(self.tracks, self.target)
        return compute_velocities(self.tracks, self.target, front, left, height, back, right, up)


def choose_target(tracks, current):
    """Pick the one track to follow: the liveliest locked one.

    Following every locked ranger at once makes the drone hold distance from
    walls and furniture too, and settle somewhere between them and the hand.
    A hand jitters, a wall doesn't, so prefer the track whose rate varies
    most, and ignore anything stiller than MIN_LIVELINESS so a lone wall is
    never followed. The current target is kept unless it is lost or another
    track is SWITCH_RATIO times livelier, so two similar tracks don't make it flip.
    """
    lively = [name for name, track in tracks.items()
              if track.locked and track.liveliness >= MIN_LIVELINESS]
    if not lively:
        return None
    best = max(lively, key=lambda name: tracks[name].liveliness)
    if current not in lively:
        return best
    if tracks[best].liveliness > SWITCH_RATIO * tracks[current].liveliness:
        return best
    return current


def compute_velocities(tracks, target, front, left, height=None, back=None, right=None, up=None):
    """One control tick: hand tracks, the target name and raw ranger readings in, a body-frame velocity out.

    Only the target track moves the drone, along its axis (see SENSOR_AXES):
    a hand moving away in front pulls the drone forward, behind pulls it
    backward, and likewise left/right. The up sensor works the same way:
    a hand moving up pulls the drone up, a hand coming down pushes it down.

    height (optional) is the down-ranger reading; descent is dropped at
    MIN_HEIGHT. Too high is handled by landing (see KILL_HEIGHT in main).
    back/right are optional so the drone still works with only front/left/up.
    """
    velocity = {'x': 0.0, 'y': 0.0, 'z': 0.0}
    if target is not None:
        axis, sign = SENSOR_AXES[target]
        velocity[axis] = track_velocity(tracks[target], sign)
    vx, vy, vz = velocity['x'], velocity['y'], velocity['z']

    # Don't descend below MIN_HEIGHT above whatever is below.
    if height is not None and height <= MIN_HEIGHT and vz < 0:
        vz = 0.0

    # Don't move toward anything too close on the side we're heading for.
    # Downward clearance is covered by MIN_HEIGHT above.
    vx = respect_clearance(vx, front, back)
    vy = respect_clearance(vy, left, right)
    vz = respect_clearance(vz, up, None)
    return vx, vy, vz


def limit_climb_rate(vz, commanded_z):
    """Limit vz so the commanded height never drops below MIN_HEIGHT.

    MotionCommander turns vz into a height setpoint that keeps integrating,
    and the drone lags behind that setpoint. Checking the *measured* height
    is too late: by the time it reads MIN_HEIGHT the setpoint is already
    near the floor, and the drone follows it down. So bound the setpoint
    itself, over the next tick.
    """
    lowest = (MIN_HEIGHT - commanded_z) / LOOP_DT
    vz = max(lowest, vz)
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
                        # The down ranger only reads to ~4 m, so also check
                        # the integrated setpoint in case it reads None.
                        height = multi_ranger.down
                        commanded_z += last_vz * dt
                        if (height is not None and height > KILL_HEIGHT) or commanded_z > KILL_HEIGHT:
                            print('Above %.1f m, landing...' % KILL_HEIGHT)
                            break
                        vx, vy, vz = follower.step(
                            dt,
                            multi_ranger.front,
                            multi_ranger.left,
                            multi_ranger.up,
                            height=height,
                            back=multi_ranger.back,
                            right=multi_ranger.right,
                        )
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
