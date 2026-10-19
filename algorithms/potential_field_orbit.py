"""
potential_field_orbit.py

Makes a Crazyflie 2.x autonomously find and orbit a nearby object using
a reactive potential-field control law driven by the Multi-ranger deck's
four horizontal time-of-flight sensors. No object coordinates are
hardcoded -- the drone reacts purely to live sensor readings.

ALGORITHM
---------
Each control cycle:
  1. Read all 4 horizontal range sensors.
  2. Pick whichever sensor sees the nearest object (that's the sensor
     "facing" the object right now).
  3. Compute a radial velocity: push away if closer than the desired
     standoff distance, pull in if farther.
  4. Compute a tangential velocity: perpendicular to the object
     direction. Its SPEED SCALES WITH THE MEASURED RADIUS
     (tangential_speed = ANGULAR_SPEED * radius) so the drone's
     ANGULAR rate around the object stays roughly constant --
     this prevents overturning when the drone is closer than the
     desired standoff, and under-turning when it's farther away.
  5. Sum radial + tangential, cap the magnitude, send as a body-frame
     velocity setpoint.
  6. If no sensor sees anything, spin slowly in place to search.

This is a reactive approximation of a potential-field / vector-field
circumnavigation controller -- not a formally proven convergence
guarantee, but effective for a single stationary object in open space.
"""

import time
import math
import sys

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.utils import uri_helper

# ---------------------------------------------------------------------
# CONFIG - edit these for your setup
# ---------------------------------------------------------------------
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')

FLIGHT_HEIGHT = 0.4        # meters, altitude above ground
DESIRED_STANDOFF = 0.5     # meters, target orbit distance from object
MAX_SENSOR_RANGE = 2.0     # meters, ignore readings beyond this (no detection)
MIN_SENSOR_RANGE = 0.05    # meters, ignore obviously invalid near-zero readings

K_RADIAL = 0.8             # proportional gain, distance error -> radial speed

# --- Tangential term is now ANGLE-based instead of a fixed linear speed ---
ANGULAR_SPEED = 0.3        # rad/s, constant angular rate around the object
MIN_RADIUS_FOR_CALC = 0.1  # meters, floor so tangential speed doesn't collapse
                           # or spike if a reading is near zero / noisy
USE_RADIAL_ERROR_DAMPING = True  # optional: shrink tangential term when
                                 # badly off the desired standoff distance

MAX_SPEED = 0.3            # m/s, safety cap on total commanded speed
SEARCH_YAW_RATE = 30       # deg/s, spin rate when no object is detected
ORBIT_DURATION = 40.0      # seconds to orbit before landing
CONTROL_HZ = 10
# ---------------------------------------------------------------------

# Body-frame unit direction vectors for each sensor (x=forward, y=left)
SENSOR_DIRECTIONS = {
    'front': (1.0, 0.0),
    'back': (-1.0, 0.0),
    'left': (0.0, 1.0),
    'right': (0.0, -1.0),
}

_latest_ranges = {'front': None, 'back': None, 'left': None, 'right': None}


def _range_callback(timestamp, data, logconf):
    # Multi-ranger log values are in meters already in recent firmware;
    # if your firmware reports mm, divide by 1000 here instead.
    for key in ('front', 'back', 'left', 'right'):
        val = data.get(f'range.{key}')
        if val is not None:
            _latest_ranges[key] = val


def start_range_logging(scf):
    log_config = LogConfig(name='Ranges', period_in_ms=int(1000 / CONTROL_HZ))
    for key in ('front', 'back', 'left', 'right'):
        log_config.add_variable(f'range.{key}', 'uint16_t')
    scf.cf.log.add_config(log_config)
    log_config.data_received_cb.add_callback(_range_callback)
    log_config.start()
    return log_config


def rotate90_ccw(x, y):
    return (-y, x)


def compute_velocity_command():
    """Reactive potential-field control: returns (vx, vy) in body frame."""
    valid = {
        k: v for k, v in _latest_ranges.items()
        if v is not None and MIN_SENSOR_RANGE < v < MAX_SENSOR_RANGE
    }

    if not valid:
        return None  # nothing detected

    # Use whichever sensor currently sees the nearest object.
    nearest_key = min(valid, key=valid.get)
    nearest_range = valid[nearest_key]
    dx, dy = SENSOR_DIRECTIONS[nearest_key]

    # Radial term: negative if too close (push away), positive if too far (pull in)
    error = nearest_range - DESIRED_STANDOFF
    radial_x = K_RADIAL * error * dx
    radial_y = K_RADIAL * error * dy

    # Tangential term: speed now scales with the measured radius, so the
    # ANGULAR rate (rad/s) stays constant instead of the linear speed.
    # This is what stops the drone from overturning when it's closer than
    # DESIRED_STANDOFF, and under-turning when it's farther away.
    safe_radius = max(nearest_range, MIN_RADIUS_FOR_CALC)
    tangential_speed = ANGULAR_SPEED * safe_radius

    if USE_RADIAL_ERROR_DAMPING:
        damping = max(0.3, 1 - abs(error) / DESIRED_STANDOFF)
        tangential_speed *= damping

    tx, ty = rotate90_ccw(dx, dy)
    tangential_x = tangential_speed * tx
    tangential_y = tangential_speed * ty

    vx = radial_x + tangential_x
    vy = radial_y + tangential_y

    # Cap total speed for safety
    speed = math.hypot(vx, vy)
    if speed > MAX_SPEED:
        scale = MAX_SPEED / speed
        vx *= scale
        vy *= scale

    return vx, vy


def send_hover(cf, vx, vy, yawrate, z):
    cf.commander.send_hover_setpoint(vx, vy, yawrate, z)


def takeoff(cf, target_z, duration=2.0, hz=CONTROL_HZ):
    steps = int(duration * hz)
    for i in range(steps):
        z = target_z * (i + 1) / steps
        send_hover(cf, 0.0, 0.0, 0.0, z)
        time.sleep(1.0 / hz)


def land(cf, start_z, duration=2.0, hz=CONTROL_HZ):
    steps = int(duration * hz)
    for i in range(steps):
        z = start_z * (1 - (i + 1) / steps)
        send_hover(cf, 0.0, 0.0, 0.0, max(z, 0.0))
        time.sleep(1.0 / hz)


def run_orbit(cf, duration, hz=CONTROL_HZ):
    steps = int(duration * hz)
    for i in range(steps):
        cmd = compute_velocity_command()

        if cmd is None:
            # No object detected -- spin in place to search for one.
            send_hover(cf, 0.0, 0.0, SEARCH_YAW_RATE, FLIGHT_HEIGHT)
        else:
            vx, vy = cmd
            send_hover(cf, vx, vy, 0.0, FLIGHT_HEIGHT)

        time.sleep(1.0 / hz)


def main():
    cflib.crtp.init_drivers()

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf

        print('Starting range sensor logging...')
        log_config = start_range_logging(scf)
        time.sleep(0.5)  # let a few readings come in

        try:
            cf.platform.send_arming_request(True)
            time.sleep(1.0)
        except Exception as e:
            print(f'Arming request skipped/failed: {e}')

        print('Taking off...')
        takeoff(cf, FLIGHT_HEIGHT)

        print('Searching for object and orbiting...')
        run_orbit(cf, ORBIT_DURATION)

        print('Landing...')
        land(cf, FLIGHT_HEIGHT)

        cf.commander.send_stop_setpoint()
        log_config.stop()
        print('Done.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nEmergency stop triggered by user.')
        sys.exit(1)
