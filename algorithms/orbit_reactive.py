"""
orbit_reactive.py

Makes a Crazyflie 2.x autonomously find and orbit a nearby object using
a reactive potential-field control law driven by the Multi-ranger deck's
four horizontal time-of-flight sensors. No object coordinates are
hardcoded -- the drone reacts purely to live sensor readings.

ALGORITHM
---------
Each control cycle:
  1. Convert horizontal range telemetry from millimeters to meters.
  2. Acquire the nearest surface within DETECTION_DISTANCE and keep that
     sensor selected until the target is lost.
  3. Compute a radial velocity: push away if closer than the desired
     standoff distance, pull in if farther.
  4. Compute a tangential velocity: perpendicular to the object
     direction, at a constant orbit speed -- this is what makes the
     drone circle rather than just hover at a fixed distance.
  5. Cap velocity and yaw with the sideways motion to keep the selected
     sensor facing the surface.
  6. Stop translation on target loss; search briefly, then land on timeout.

This is a reactive approximation of a potential-field / vector-field
circumnavigation controller -- not a formally proven convergence
guarantee. Requires a working velocity estimate (e.g. Flow deck), and an
isolated stationary object intersecting the sensors at FLIGHT_HEIGHT.
Ranges measure surface clearance, not object center/radius or identity.
"""

import time
import math
import sys
from threading import Lock

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.utils import uri_helper

# ---------------------------------------------------------------------
# CONFIG - edit these for your setup
# ---------------------------------------------------------------------
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')

FLIGHT_HEIGHT = 0.35        # meters, altitude above ground
DESIRED_STANDOFF = 0.25     # meters, target orbit distance from object
DETECTION_DISTANCE = 1.0   # meters, acquire a new target inside this distance
MAX_SENSOR_RANGE = 2.0     # meters, ignore readings beyond this (no detection)
MIN_SENSOR_RANGE = 0.05    # meters, ignore obviously invalid near-zero readings

K_RADIAL = 0.8             # proportional gain, distance error -> radial speed
ORBIT_SPEED = 0.15         # m/s, constant tangential (circling) speed
MAX_SPEED = 0.3            # m/s, safety cap on total commanded speed
SEARCH_YAW_RATE = 30       # deg/s, spin rate when no object is detected
MAX_ORBIT_YAW_RATE = 45.0  # deg/s, cap yaw and matching tangential motion
SEARCH_TIMEOUT = 12.0     # seconds without a target before landing
TARGET_LOST_TIMEOUT = 0.5 # seconds to hover before releasing a lost target
RANGE_TIMEOUT = 0.5       # seconds before telemetry is considered stale
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
_ranges_received_at = None
_range_lock = Lock()


def _range_callback(timestamp, data, logconf):
    global _ranges_received_at
    # Raw range.* uint16_t logs are millimeters (unlike Multiranger properties).
    ranges = {}
    for key in SENSOR_DIRECTIONS:
        val = data.get(f'range.{key}')
        ranges[key] = val / 1000.0 if val is not None and 0 < val < 8000 else None
    with _range_lock:
        _latest_ranges.update(ranges)
        _ranges_received_at = time.monotonic()


def read_ranges():
    with _range_lock:
        if (_ranges_received_at is None or
                time.monotonic() - _ranges_received_at > RANGE_TIMEOUT):
            raise RuntimeError('Range telemetry missing or stale.')
        return _latest_ranges.copy()


def start_range_logging(scf):
    global _ranges_received_at
    with _range_lock:
        _ranges_received_at = None
        _latest_ranges.update(dict.fromkeys(SENSOR_DIRECTIONS))
    log_config = LogConfig(name='Ranges', period_in_ms=int(1000 / CONTROL_HZ))
    for key in ('front', 'back', 'left', 'right'):
        log_config.add_variable(f'range.{key}', 'uint16_t')
    scf.cf.log.add_config(log_config)
    log_config.data_received_cb.add_callback(_range_callback)
    log_config.start()
    return log_config


def rotate90_ccw(x, y):
    return (-y, x)


def compute_velocity_command(ranges=None, target_sensor=None):
    """Reactive potential-field control: returns (vx, vy) in body frame."""
    if ranges is None:
        ranges = read_ranges()
    limit = MAX_SENSOR_RANGE if target_sensor is not None else DETECTION_DISTANCE
    valid = {k: v for k, v in ranges.items()
             if v is not None and MIN_SENSOR_RANGE < v <= limit
             and (target_sensor is None or k == target_sensor)}

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

    # Tangential term: constant-speed circling, perpendicular to object direction
    tx, ty = rotate90_ccw(dx, dy)
    tangential_speed = min(ORBIT_SPEED,
                           math.radians(MAX_ORBIT_YAW_RATE) * nearest_range)
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


class OrbitController:
    """Lock a sensor on acquisition; do not switch to a closer wall each tick."""

    def __init__(self):
        self.target_sensor = None
        self.last_seen = None
        self.search_started = None

    def command(self, ranges, now):
        if self.search_started is None:
            self.search_started = now
        if self.target_sensor is None:
            candidates = {k: v for k, v in ranges.items()
                          if v is not None and MIN_SENSOR_RANGE < v <= DETECTION_DISTANCE}
            if candidates:
                self.target_sensor = min(candidates, key=candidates.get)
                print(f'Target acquired: {self.target_sensor}, '
                      f'{candidates[self.target_sensor]:.2f} m')

        if self.target_sensor is not None:
            cmd = compute_velocity_command(ranges, self.target_sensor)
            if cmd is not None:
                self.last_seen = now
                self.search_started = now
                vx, vy = cmd
                dx, dy = SENSOR_DIRECTIONS[self.target_sensor]
                # Bearing rate about a stationary surface point: -v_t / range.
                # cflib hover yaw is positive counterclockwise.
                tangential_speed = -dy * vx + dx * vy
                yawrate = -math.degrees(tangential_speed / ranges[self.target_sensor])
                return vx, vy, yawrate
            if now - self.last_seen < TARGET_LOST_TIMEOUT:
                return 0.0, 0.0, 0.0
            print('Target lost; searching again.')
            self.target_sensor = None

        if now - self.search_started >= SEARCH_TIMEOUT:
            return None
        return 0.0, 0.0, SEARCH_YAW_RATE


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
    controller = OrbitController()
    steps = int(duration * hz)
    for i in range(steps):
        try:
            ranges = read_ranges()
        except RuntimeError as exc:
            print(f'{exc} Landing.')
            send_hover(cf, 0.0, 0.0, 0.0, FLIGHT_HEIGHT)
            return
        cmd = controller.command(ranges, time.monotonic())
        if cmd is None:
            print('No target within search timeout; landing.')
            send_hover(cf, 0.0, 0.0, 0.0, FLIGHT_HEIGHT)
            return
        send_hover(cf, *cmd, FLIGHT_HEIGHT)

        time.sleep(1.0 / hz)


def main():
    if not (0 < MIN_SENSOR_RANGE < DESIRED_STANDOFF < DETECTION_DISTANCE
            <= MAX_SENSOR_RANGE < 8.0):
        raise ValueError('Require min range < standoff < detection distance <= max range < 8 m.')
    cflib.crtp.init_drivers()

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        cf = scf.cf

        print('Starting range sensor logging...')
        log_config = start_range_logging(scf)
        arming = getattr(cf, 'supervisor', cf.platform)
        try:
            time.sleep(0.5)  # let a few readings come in
            read_ranges()  # require live telemetry before takeoff
            arming.send_arming_request(True)
            time.sleep(1.0)

            print('Taking off...')
            takeoff(cf, FLIGHT_HEIGHT)

            print(f'Searching within {DETECTION_DISTANCE:.2f} m; '
                  f'orbit standoff {DESIRED_STANDOFF:.2f} m...')
            run_orbit(cf, ORBIT_DURATION)

            print('Landing...')
            land(cf, FLIGHT_HEIGHT)
        finally:
            # Stop while connected, including on Ctrl-C and callback failures.
            try:
                cf.commander.send_stop_setpoint()
            finally:
                try:
                    arming.send_arming_request(False)
                finally:
                    log_config.stop()
        print('Done.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nEmergency stop triggered by user.')
        sys.exit(1)
