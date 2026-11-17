"""
simple_orbit.py

Crazyflie takes off, orbits an object, and lands.

Coordinates come from the Kalman estimator (Flow deck), whose origin is
wherever the drone was sitting at startup, with +x pointing out the
drone's front. For now the object is assumed to be OBJECT_DISTANCE meters
straight ahead, so the drone already starts on the circle. Later, just pass
a different (center_x, center_y) into orbit() -- e.g. a planet position.

Ctrl-C at any point lands the drone instead of cutting the motors.
"""

import math
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.utils import uri_helper

URI = uri_helper.uri_from_env(default="radio://0/80/2M/E7E7E7E7E7")

OBJECT_DISTANCE = 0.3  # m, object is this far in front of the drone at startup
HEIGHT = 0.3  # m
PERIOD = 15.0  # s per lap
LAPS = 1
HZ = 20  # setpoint rate


def orbit(cf, center_x, center_y, radius, start_angle):
    """Stream position setpoints around a circle, facing the center."""
    steps = int(PERIOD * LAPS * HZ)
    for i in range(steps + 1):
        theta = start_angle + 2 * math.pi * i / (PERIOD * HZ)
        x = center_x + radius * math.cos(theta)
        y = center_y + radius * math.sin(theta)
        yaw = math.degrees(theta + math.pi)  # point the nose at the center
        cf.commander.send_position_setpoint(x, y, HEIGHT, yaw)
        time.sleep(1 / HZ)


def main():
    cflib.crtp.init_drivers()

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
        cf = scf.cf

        # Kalman estimator + high-level commander, then reset position to (0, 0).
        cf.param.set_value("stabilizer.estimator", "2")
        cf.param.set_value("commander.enHighLevel", "1")
        cf.param.set_value("kalman.resetEstimation", "1")
        time.sleep(0.1)
        cf.param.set_value("kalman.resetEstimation", "0")
        time.sleep(2.0)  # let the estimate settle

        hl = cf.high_level_commander
        cf.supervisor.send_arming_request(True)
        time.sleep(1.0)

        try:
            print("Taking off...")
            hl.takeoff(HEIGHT, 2.0)
            time.sleep(3.0)

            # Object straight ahead; drone sits on the circle at angle pi.
            print("Orbiting...")
            orbit(cf, OBJECT_DISTANCE, 0.0, OBJECT_DISTANCE, math.pi)
        except KeyboardInterrupt:
            print("\nCtrl-C -- landing (Ctrl-C again to cut motors)")
        finally:
            # Hand control back to the high-level commander and land gently.
            cf.commander.send_notify_setpoint_stop()
            hl.land(0.0, 2.0)
            time.sleep(2.5)
            hl.stop()
            cf.supervisor.send_arming_request(False)
            time.sleep(0.1)
        print("Done.")


if __name__ == "__main__":
    main()
