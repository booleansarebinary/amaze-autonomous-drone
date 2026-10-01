"""
Makes a Crazyflie 2.x fly a circular orbit around a fixed point in space
(e.g. an object sitting on the floor).

This script streams position setpoints directly (low-level position
control), rather than using the high-level commander, so you get full
control over the shape/speed of the circle.
"""

import time
import math
import sys

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncLogger import SyncLogger
from cflib.utils import uri_helper

# ---------------------------------------------------------------------
# CONFIG - edit these for your setup
# ---------------------------------------------------------------------
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')

# Coordinates of the stationary object, in your positioning system's frame (meters)
OBJECT_X = 0.0
OBJECT_Y = 0.0

ORBIT_RADIUS = 0.8      # meters
ORBIT_HEIGHT = 0.5      # meters (flight altitude)
ORBIT_PERIOD = 8.0      # seconds for one full revolution
NUM_LAPS = 3
SETPOINT_HZ = 10        # rate at which setpoints are streamed
FACE_CENTER = True      # if True, the drone yaws to always face the object
# ---------------------------------------------------------------------


def wait_for_position_estimate(scf, timeout=10.0):
    """Block until the Kalman filter's position estimate has converged."""
    log_config = LogConfig(name='Kalman Variance', period_in_ms=200)
    log_config.add_variable('kalman.varPX', 'float')
    log_config.add_variable('kalman.varPY', 'float')
    log_config.add_variable('kalman.varPZ', 'float')

    threshold = 0.001
    start = time.time()

    with SyncLogger(scf, log_config) as logger:
        for log_entry in logger:
            data = log_entry[1]
            var_x = data['kalman.varPX']
            var_y = data['kalman.varPY']
            var_z = data['kalman.varPZ']

            print(f'Waiting for estimator to converge... '
                  f'varX={var_x:.5f} varY={var_y:.5f} varZ={var_z:.5f}')

            if var_x < threshold and var_y < threshold and var_z < threshold:
                print('Position estimate converged.')
                return True

            if time.time() - start > timeout:
                print('WARNING: estimator did not converge within timeout, '
                      'continuing anyway.')
                return False


def reset_estimator(scf):
    cf = scf.cf
    cf.param.set_value('kalman.resetEstimation', '1')
    time.sleep(0.1)
    cf.param.set_value('kalman.resetEstimation', '0')
    wait_for_position_estimate(scf)


def send_setpoint(cf, x, y, z, yaw_deg):
    cf.commander.send_position_setpoint(x, y, z, yaw_deg)


def ramp_to_height(cf, x, y, target_z, duration, hz=SETPOINT_HZ):
    """Smoothly ramp the z setpoint from 0 (or current) to target_z."""
    steps = int(duration * hz)
    for i in range(steps):
        z = target_z * (i + 1) / steps
        send_setpoint(cf, x, y, z, 0)
        time.sleep(1.0 / hz)


def ramp_down(cf, x, y, start_z, duration, hz=SETPOINT_HZ):
    steps = int(duration * hz)
    for i in range(steps):
        z = start_z * (1 - (i + 1) / steps)
        send_setpoint(cf, x, y, max(z, 0.0), 0)
        time.sleep(1.0 / hz)


def fly_to_point(cf, x0, y0, z0, x1, y1, z1, duration, hz=SETPOINT_HZ):
    """Linearly interpolate from one point to another."""
    steps = int(duration * hz)
    for i in range(steps):
        t = (i + 1) / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        z = z0 + (z1 - z0) * t
        yaw = compute_yaw(x, y) if FACE_CENTER else 0
        send_setpoint(cf, x, y, z, yaw)
        time.sleep(1.0 / hz)


def compute_yaw(x, y):
    """Yaw angle (degrees) so the drone faces the orbited object."""
    dx = OBJECT_X - x
    dy = OBJECT_Y - y
    return math.degrees(math.atan2(dy, dx))


def orbit(cf):
    total_time = ORBIT_PERIOD * NUM_LAPS
    steps = int(total_time * SETPOINT_HZ)

    for i in range(steps):
        t = i / SETPOINT_HZ
        theta = 2 * math.pi * (t / ORBIT_PERIOD)

        x = OBJECT_X + ORBIT_RADIUS * math.cos(theta)
        y = OBJECT_Y + ORBIT_RADIUS * math.sin(theta)
        z = ORBIT_HEIGHT
        yaw = compute_yaw(x, y) if FACE_CENTER else 0

        send_setpoint(cf, x, y, z, yaw)
        time.sleep(1.0 / SETPOINT_HZ)


def main():
    cflib.crtp.init_drivers()

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf

        print('Resetting estimator...')
        reset_estimator(scf)

        # Arm (required on newer firmware; harmless no-op call structure
        # if arming request isn't supported, remove this line)
        try:
            cf.platform.send_arming_request(True)
            time.sleep(1.0)
        except Exception as e:
            print(f'Arming request skipped/failed: {e}')

        start_x = OBJECT_X + ORBIT_RADIUS
        start_y = OBJECT_Y

        print('Taking off...')
        ramp_to_height(cf, 0.0, 0.0, ORBIT_HEIGHT, duration=2.0)

        print('Flying to orbit start point...')
        fly_to_point(cf, 0.0, 0.0, ORBIT_HEIGHT,
                     start_x, start_y, ORBIT_HEIGHT, duration=3.0)

        print(f'Orbiting object at ({OBJECT_X}, {OBJECT_Y}) '
              f'with radius {ORBIT_RADIUS} m for {NUM_LAPS} laps...')
        orbit(cf)

        print('Returning to landing point...')
        fly_to_point(cf, start_x, start_y, ORBIT_HEIGHT,
                     start_x, start_y, ORBIT_HEIGHT, duration=1.0)

        print('Landing...')
        ramp_down(cf, start_x, start_y, ORBIT_HEIGHT, duration=2.0)

        cf.commander.send_stop_setpoint()
        print('Done.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nEmergency stop triggered by user.')
        sys.exit(1)