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
TARGET_DISTANCE = 0.4   # (m) desired gap to hold from your hand on each axis
DEADBAND = 0.05         # (m) ignore error smaller than this, to reduce jitter
KP = 1.5                # proportional gain: velocity = KP * error
MAX_VELOCITY = 0.6      # (m/s) clamp so it doesn't lurch
LOOP_DT = 0.05          # (s) ~20 Hz control loop
MIN_DETECT_DISTANCE = 0.12  # (m) closer than this is sensor noise / prop guard
MAX_DETECT_DISTANCE = 1.2   # (m) further than this is a wall, not a hand
MIN_HEIGHT = 0.2            # (m) never command a descent below this height

def proportional_velocity(measured, sign=1.0):
    """
    Turn a single ranger reading into a velocity command that tries to
    hold TARGET_DISTANCE from whatever the sensor sees.
    sign flips which physical direction counts as "closing the gap"
    for that particular sensor's mounting orientation.
    """
    if measured is None or not (MIN_DETECT_DISTANCE <= measured <= MAX_DETECT_DISTANCE):
        return 0.0  # nothing that could be a hand on this axis, don't move on it

    error = measured - TARGET_DISTANCE
    if abs(error) < DEADBAND:
        return 0.0

    velocity = sign * KP * error
    return max(-MAX_VELOCITY, min(MAX_VELOCITY, velocity))


def compute_velocities(front, left, up, height=None):
    """One control tick: three ranger readings in, a body-frame velocity out.

    x-axis: the front sensor reads "how far is my hand in front of me", and
            positive x is forward, so a growing front distance means move
            forward.
    y-axis: the left sensor, and positive y is left in the body frame.
    z-axis: the up sensor; a growing distance above means the hand moved up,
            so follow it upward.

    height (optional) is the down-ranger reading; below MIN_HEIGHT any
    downward command is dropped so a hand overhead can't push the drone
    into the floor.
    """
    vx = proportional_velocity(front, sign=1.0)
    vy = proportional_velocity(left, sign=1.0)
    vz = proportional_velocity(up, sign=1.0)
    if height is not None and height <= MIN_HEIGHT and vz < 0:
        vz = 0.0
    return vx, vy, vz


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    uri = argv[0] if argv else URI

    cflib.crtp.init_drivers(enable_debug_driver=False)

    cf = Crazyflie(rw_cache='./cache')
    with SyncCrazyflie(uri, cf=cf) as scf:
        scf.cf.platform.send_arming_request(True)
        time.sleep(1.0)

        with MotionCommander(scf) as motion_commander:
            with Multiranger(scf) as multi_ranger:
                try:
                    while True:
                        vx, vy, vz = compute_velocities(
                            multi_ranger.front,
                            multi_ranger.left,
                            multi_ranger.up,
                            multi_ranger.down,
                        )
                        motion_commander.start_linear_motion(vx, vy, vz)
                        time.sleep(LOOP_DT)

                except KeyboardInterrupt:
                    print('Landing...')

        print('Demo terminated!')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
