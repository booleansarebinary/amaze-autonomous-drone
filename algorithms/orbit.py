"""
Makes a Crazyflie 2.x fly a circular orbit around a fixed point in space
(e.g. an object sitting on the floor).

This script streams position setpoints directly (low-level position
control), rather than using the high-level commander, so you get full
control over the shape/speed of the circle.

Requires a working position estimate (for example a Flow deck, Lighthouse,
Loco, or externally supplied position). Object coordinates and flight altitude
must use the estimator's coordinate frame; this script does not detect objects.
"""

import time
import math
import sys
from collections import deque
from contextlib import contextmanager
from queue import Empty, Queue

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.utils import uri_helper

# ---------------------------------------------------------------------
# CONFIG - edit these for your setup
# ---------------------------------------------------------------------
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')

# Coordinates of the stationary object, in your positioning system's frame (meters)
OBJECT_X = 0.0
OBJECT_Y = 0.0

ORBIT_RADIUS = 0.4      # meters
ORBIT_HEIGHT = 0.5      # meters (flight altitude)
ORBIT_PERIOD = 8.0      # seconds for one full revolution
NUM_LAPS = 1
SETPOINT_HZ = 10        # rate at which setpoints are streamed
FACE_CENTER = True      # if True, the drone yaws to always face the object
# ---------------------------------------------------------------------


@contextmanager
def position_samples(scf, variables, timeout):
    """Read telemetry with a deadline, including when no packets arrive."""
    samples = Queue()
    log_config = LogConfig(name='Orbit Position', period_in_ms=200)
    for variable in variables:
        log_config.add_variable(variable, 'float')
    log_config.data_received_cb.add_callback(
        lambda timestamp, data, config: samples.put(data))
    log_config.error_cb.add_callback(
        lambda config, message: samples.put(RuntimeError(message)))
    scf.cf.log.add_config(log_config)

    def read_samples():
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Timed out waiting for position telemetry.')
            try:
                sample = samples.get(timeout=remaining)
            except Empty as exc:
                raise TimeoutError('Timed out waiting for position telemetry.') from exc
            if isinstance(sample, Exception):
                raise sample
            yield sample

    try:
        log_config.start()
        yield read_samples()
    finally:
        log_config.delete()


def wait_for_position_estimate(scf, timeout=10.0):
    """Block until the Kalman filter's position estimate has converged."""
    variables = ('kalman.varPX', 'kalman.varPY', 'kalman.varPZ')
    histories = [deque(maxlen=10) for _ in variables]
    threshold = 0.001
    with position_samples(scf, variables, timeout) as samples:
        for data in samples:
            for variable, history in zip(variables, histories):
                value = data[variable]
                if not math.isfinite(value) or value < 0:
                    raise RuntimeError(f'Invalid estimator variance: {variable}={value}')
                history.append(value)
            if all(len(h) == h.maxlen and max(h) - min(h) < threshold
                   for h in histories):
                print('Position estimate converged.')
                return True


def reset_estimator(scf):
    cf = scf.cf
    cf.param.set_value('stabilizer.estimator', '2')
    cf.param.set_value('kalman.resetEstimation', '1')
    time.sleep(0.1)
    cf.param.set_value('kalman.resetEstimation', '0')
    wait_for_position_estimate(scf)


def read_position(scf, timeout=5.0):
    variables = ('stateEstimate.x', 'stateEstimate.y', 'stateEstimate.z')
    with position_samples(scf, variables, timeout) as samples:
        data = next(samples)
        position = tuple(data[v] for v in variables)
        if not all(math.isfinite(v) for v in position):
            raise RuntimeError('Invalid position estimate.')
        return position


def send_setpoint(cf, x, y, z, yaw_deg):
    cf.commander.send_position_setpoint(x, y, z, yaw_deg)


def ramp_to_height(cf, x, y, target_z, duration, hz=SETPOINT_HZ, start_z=0.0):
    """Smoothly ramp from the measured ground altitude to target_z."""
    steps = int(duration * hz)
    for i in range(steps):
        z = start_z + (target_z - start_z) * (i + 1) / steps
        send_setpoint(cf, x, y, z, 0)
        time.sleep(1.0 / hz)


def ramp_down(cf, x, y, start_z, duration, hz=SETPOINT_HZ, target_z=0.0):
    steps = int(duration * hz)
    for i in range(steps):
        z = start_z + (target_z - start_z) * (i + 1) / steps
        send_setpoint(cf, x, y, z, 0)
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

    for i in range(1, steps + 1):
        t = total_time * i / steps
        theta = 2 * math.pi * (t / ORBIT_PERIOD)

        x = OBJECT_X + ORBIT_RADIUS * math.cos(theta)
        y = OBJECT_Y + ORBIT_RADIUS * math.sin(theta)
        z = ORBIT_HEIGHT
        yaw = compute_yaw(x, y) if FACE_CENTER else 0

        send_setpoint(cf, x, y, z, yaw)
        time.sleep(1.0 / SETPOINT_HZ)


def main():
    for name, value in (('ORBIT_RADIUS', ORBIT_RADIUS),
                        ('ORBIT_PERIOD', ORBIT_PERIOD), ('NUM_LAPS', NUM_LAPS),
                        ('SETPOINT_HZ', SETPOINT_HZ)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be finite and positive.')
    if not all(math.isfinite(v) for v in (OBJECT_X, OBJECT_Y, ORBIT_HEIGHT)):
        raise ValueError('Object coordinates and orbit height must be finite.')
    if int(ORBIT_PERIOD * NUM_LAPS * SETPOINT_HZ) < 1 or SETPOINT_HZ < 1:
        raise ValueError('Flight settings must produce at least one setpoint per second.')
    cflib.crtp.init_drivers()

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf

        print('Resetting estimator...')
        reset_estimator(scf)

        home_x, home_y, home_z = read_position(scf)
        if ORBIT_HEIGHT <= home_z:
            raise ValueError('ORBIT_HEIGHT must be above the measured takeoff altitude.')
        start_x = OBJECT_X + ORBIT_RADIUS
        start_y = OBJECT_Y

        # New cflib exposes arming through supervisor; retain older API support.
        arming = getattr(cf, 'supervisor', cf.platform)
        try:
            arming.send_arming_request(True)
            time.sleep(1.0)

            print('Taking off...')
            ramp_to_height(cf, home_x, home_y, ORBIT_HEIGHT, duration=2.0,
                           start_z=home_z)

            print('Flying to orbit start point...')
            fly_to_point(cf, home_x, home_y, ORBIT_HEIGHT,
                         start_x, start_y, ORBIT_HEIGHT, duration=3.0)

            print(f'Orbiting object at ({OBJECT_X}, {OBJECT_Y}) '
                  f'with radius {ORBIT_RADIUS} m for {NUM_LAPS} laps...')
            orbit(cf)

            print('Returning to landing point...')
            theta = 2 * math.pi * NUM_LAPS
            end_x = OBJECT_X + ORBIT_RADIUS * math.cos(theta)
            end_y = OBJECT_Y + ORBIT_RADIUS * math.sin(theta)
            fly_to_point(cf, end_x, end_y, ORBIT_HEIGHT,
                         home_x, home_y, ORBIT_HEIGHT, duration=3.0)

            print('Landing...')
            ramp_down(cf, home_x, home_y, ORBIT_HEIGHT, duration=2.0,
                      target_z=home_z)
        finally:
            # Stop while the radio link is still open, even on Ctrl-C/errors.
            try:
                cf.commander.send_stop_setpoint()
                time.sleep(0.1)
            finally:
                arming.send_arming_request(False)
        print('Done.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nEmergency stop triggered by user.')
        sys.exit(1)
