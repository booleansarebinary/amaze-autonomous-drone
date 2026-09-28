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

if len(sys.argv) > 1:
    URI = sys.argv[1]

logging.basicConfig(level=logging.ERROR)

# --- Tuning knobs ---
TARGET_DISTANCE = 0.4   # (m) desired gap to hold from your hand on each axis
DEADBAND = 0.05         # (m) ignore error smaller than this, to reduce jitter
KP = 1.5                # proportional gain: velocity = KP * error
MAX_VELOCITY = 0.6      # (m/s) clamp so it doesn't lurch
LOOP_DT = 0.05          # (s) ~20 Hz control loop


def proportional_velocity(measured, sign=1.0):
    """
    Turn a single ranger reading into a velocity command that tries to
    hold TARGET_DISTANCE from whatever the sensor sees.
    sign flips which physical direction counts as "closing the gap"
    for that particular sensor's mounting orientation.
    """
    if measured is None:
        return 0.0  # nothing detected on this axis, don't move on it

    error = measured - TARGET_DISTANCE
    if abs(error) < DEADBAND:
        return 0.0

    velocity = sign * KP * error
    return max(-MAX_VELOCITY, min(MAX_VELOCITY, velocity))


if __name__ == '__main__':
    cflib.crtp.init_drivers(enable_debug_driver=False)

    cf = Crazyflie(rw_cache='./cache')
    with SyncCrazyflie(URI, cf=cf) as scf:
        scf.cf.platform.send_arming_request(True)
        time.sleep(1.0)

        with MotionCommander(scf) as motion_commander:
            with Multiranger(scf) as multi_ranger:
                try:
                    while True:
                        # x-axis: front sensor reads "how far is my hand in
                        # front of me" -> positive x is forward, so a
                        # growing front-distance should mean move forward.
                        vx = proportional_velocity(multi_ranger.front, sign=1.0)

                        # y-axis: left sensor -> positive y is left in the
                        # Crazyflie body frame.
                        vy = proportional_velocity(multi_ranger.left, sign=1.0)

                        # z-axis: up sensor -> growing distance above means
                        # your hand moved further up, so follow upward.
                        vz = proportional_velocity(multi_ranger.up, sign=1.0)

                        motion_commander.start_linear_motion(vx, vy, vz)
                        time.sleep(LOOP_DT)

                except KeyboardInterrupt:
                    print('Landing...')

        print('Demo terminated!')