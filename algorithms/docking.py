"""
The docking mission! Turns the Crazyflie 2, flies it forward, and then lands it.
"""

import math
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.motion_commander import MotionCommander
from cflib.utils import uri_helper


URI = uri_helper.uri_from_env(default="radio://0/80/2M/E7E7E7E7E7")
# In meters
HEIGHT = 0.4
# In m/s
SPEED = 0.3


def dock(angle: float, distance: float) -> None:
    """Turn by `angle` degrees, then fly `distance` meters forwards in the new heading."""
    if not math.isfinite(angle):
        raise ValueError("Angle must be a finite number of degrees.")
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError("Distance must be a positive, finite number of meters.")

    cflib.crtp.init_drivers()
    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
        if int(scf.cf.param.get_value("deck.bcFlow2")) != 1:
            raise RuntimeError("Flow deck v2 not detected, flight aborted.")

        scf.cf.supervisor.send_arming_request(True)
        time.sleep(1.0)

        # MotionCommander takes off on entry and lands on exit for safety.
        with MotionCommander(scf, default_height=HEIGHT) as mc:
            time.sleep(1.0)
            if angle > 0:
                mc.turn_left(angle)
            elif angle < 0:
                mc.turn_right(-angle)

            time.sleep(1.0)
            mc.forward(distance, velocity=SPEED)
            time.sleep(1.0)
