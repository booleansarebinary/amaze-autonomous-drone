"""Autonomous boundary following in simulation or on a Crazyflie.

The controller receives synthetic range sweeps and an ideal local pose. Only
the simulator knows obstacle geometry. A sweep is an idealized active scan,
not the four simultaneous horizontal readings of a physical Multi-ranger.

Hardware mode (--fly) uses a separate left-side boundary follower. Requires
Flow deck v2, Multi-ranger, Crazyradio and cflib. Place the object to the LEFT
of the drone, within 1.8 m, extending through the chosen flight height.
It follows the first surface, not a recognized object. Lap closure is heuristic.
Example: python3 algorithms/cache/orbit_prototype.py --fly --height 0.45
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from threading import Lock
from tempfile import TemporaryDirectory
from dataclasses import dataclass
from pathlib import Path


def wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


@dataclass(frozen=True)
class Config:
    clearance: float = 0.55       # From simulated drone center to surface, m.
    detect_range: float = 1.8
    speed: float = 0.20
    max_speed: float = 0.25
    correction_gain: float = 0.8
    stop_distance: float = 0.20
    time_limit: float = 120.0


class OrbitController:
    """Sensor-driven concept controller; does not accept an object location."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.state = "SEARCH"
        self.reason = "Scanning for the first nearby surface"
        self.elapsed = 0.0
        self.confirmations = 0
        self.lost_time = 0.0
        self.entry = None
        self.previous_pos = None
        self.previous_bearing = None
        self.travel = 0.0
        self.turn = 0.0
        self.left_entry = False
        self.last_target_bearing = None
        self.last_target_distance = None

    def abort(self, reason):
        self.state, self.reason = "ABORT", reason
        return 0.0, 0.0

    def step(self, scan, pos, yaw, dt):
        """Return world-frame (vx, vy), in m/s.

        scan: list of (body bearing in radians, distance in meters). None is
        a valid no-return sample here. Empty or malformed scans are failures.
        pos: local odometry (x, y). yaw: radians, counterclockwise positive.
        """
        if self.state in ("COMPLETE", "ABORT"):
            return 0.0, 0.0
        if not math.isfinite(dt) or dt <= 0:
            return self.abort("Invalid time step")
        if not all(math.isfinite(value) for value in (*pos, yaw)):
            return self.abort("Invalid pose")
        self.elapsed += dt
        if self.elapsed >= self.config.time_limit:
            return self.abort("Mission time limit")
        if not scan:
            return self.abort("Missing scan")
        if any(not math.isfinite(a) or (d is not None and
               (not math.isfinite(d) or d <= 0)) for a, d in scan):
            return self.abort("Invalid scan")

        hits = [(a, d) for a, d in scan if d is not None]
        if hits and min(d for _, d in hits) < self.config.stop_distance:
            return self.abort("Surface inside stop distance")
        candidates = [(a, d) for a, d in hits
                      if d <= self.config.detect_range]
        if not candidates:
            self.confirmations = 0
            if self.state != "SEARCH":
                self.state = "REACQUIRE"
                self.reason = "Holding position while scanning for the surface"
                self.lost_time += dt
                if self.lost_time > 3.0:
                    return self.abort("Target lost for more than 3 seconds")
                return 0.0, 0.0
            self.reason = "Moving slowly through the clear demo search area"
            return 0.10 * math.cos(yaw), 0.10 * math.sin(yaw)

        bearing, distance = min(candidates, key=lambda item: item[1])
        world_bearing = wrap(bearing + yaw)
        # Deliberately modest target continuity check, not object recognition.
        if self.state not in ("SEARCH", "APPROACH"):
            if (self.last_target_bearing is not None and
                (abs(wrap(world_bearing - self.last_target_bearing)) >
                 math.radians(65) or
                 abs(distance - self.last_target_distance) > 0.45)):
                self.state = "REACQUIRE"
                self.reason = "Surface changed abruptly; holding position"
                self.lost_time += dt
                if self.lost_time > 3.0:
                    return self.abort("Could not reacquire the same surface")
                return 0.0, 0.0
        self.last_target_bearing = world_bearing
        self.last_target_distance = distance
        self.lost_time = 0.0

        if self.state == "SEARCH":
            self.confirmations += 1
            self.reason = "Confirming a nearby surface across five scans"
            if self.confirmations < 5:
                return 0.0, 0.0
            self.state = "APPROACH"

        nx, ny = math.cos(world_bearing), math.sin(world_bearing)
        error = distance - self.config.clearance
        if self.state == "APPROACH":
            self.reason = "Approaching the detected surface"
            if abs(error) > 0.06:
                speed = max(-0.15, min(0.15, self.config.correction_gain * error))
                return speed * nx, speed * ny
            self.entry = tuple(pos)
            self.previous_pos = tuple(pos)
            self.previous_bearing = world_bearing
            self.state = "FOLLOW"

        if self.state == "REACQUIRE":
            self.state = "FOLLOW"
        self.reason = "Following the boundary at the desired clearance"
        if self.previous_pos is not None:
            self.travel += math.dist(pos, self.previous_pos)
        if self.previous_bearing is not None:
            self.turn += wrap(world_bearing - self.previous_bearing)
        self.previous_pos = tuple(pos)
        self.previous_bearing = world_bearing
        entry_distance = math.dist(pos, self.entry)
        self.left_entry |= entry_distance > 0.45
        # Net change of the observed surface bearing plus odometry closure.
        # This is a heuristic, not a proof of encircling a particular object.
        if (self.left_entry and self.travel > 2.0 and
            self.turn > math.radians(330) and entry_distance < 0.16):
            self.state = "COMPLETE"
            self.reason = "Approximate lap closure detected"
            return 0.0, 0.0

        # n points toward the surface; rotating it clockwise produces CCW
        # travel around the isolated obstacle, keeping the surface on the left.
        tx, ty = ny, -nx
        vx = self.config.speed * tx + self.config.correction_gain * error * nx
        vy = self.config.speed * ty + self.config.correction_gain * error * ny
        magnitude = math.hypot(vx, vy)
        scale = min(1.0, self.config.max_speed / max(magnitude, 1e-12))
        return vx * scale, vy * scale


class FlightController:
    """Sparse-beam left-hand follower; commands are body vx, vy, CCW deg/s.

    Turning toward a receding left surface maintains contact on convex objects.
    A range derivative damps the steering. Blind wedges and odometry drift
    remain; this is an experimental controller, not guaranteed object tracking.
    """

    def __init__(self, config):
        self.config = config
        self.state, self.reason = "APPROACH", "Acquiring the left surface"
        self.elapsed = self.lost = self.turn = self.travel = 0.0
        self.previous_distance = None
        self.previous_pose = self.entry = None
        self.confirmations = 0
        self.left_entry = False
        self.derivative = 0.0

    def abort(self, reason):
        self.state, self.reason = "ABORT", reason
        return 0.0, 0.0, 0.0

    def step(self, ranges, pos, yaw, dt):
        if self.state in ("ABORT", "COMPLETE"):
            return 0.0, 0.0, 0.0
        if not math.isfinite(dt) or not 0 < dt <= 0.5:
            return self.abort("Control loop stalled")
        if not all(math.isfinite(v) for v in (*pos, yaw)):
            return self.abort("Invalid pose")
        if any(name not in ranges for name in ("front", "back", "left", "right", "up")):
            return self.abort("Missing range data")
        invalid = {name: d for name, d in ranges.items()
                   if d is not None and (not math.isfinite(d) or d <= 0)}
        if invalid:
            return self.abort(f"Invalid range data (meters): {invalid}")
        self.elapsed += dt
        if self.elapsed >= self.config.time_limit:
            return self.abort("Mission time limit")
        too_close = [f"{name}={d:.3f} m" for name, d in ranges.items()
                     if name != "up" and d is not None and d < self.config.stop_distance]
        if too_close:
            return self.abort(f"Surface inside stop distance ({self.config.stop_distance:.2f} m): "
                              + ", ".join(too_close))
        if ranges["up"] is not None and ranges["up"] < 0.30:
            return self.abort(f"Obstacle overhead: up={ranges['up']:.3f} m (minimum 0.30 m)")

        distance = ranges["left"]
        if distance is None or distance > self.config.detect_range:
            self.lost += dt
            self.confirmations = 0
            self.previous_distance = None
            self.derivative = 0.0
            if self.lost > 3.0:
                return self.abort("Left surface lost for 3 seconds")
            self.reason = "Holding for left surface; place object to the left"
            return 0.0, 0.0, 0.0
        if (self.previous_distance is not None and
                abs(distance - self.previous_distance) > 0.45):
            return self.abort("Left surface changed abruptly")
        self.lost = 0.0
        self.confirmations += 1
        derivative = (0.0 if self.previous_distance is None else
                      (distance - self.previous_distance) / dt)
        self.derivative = 0.8 * self.derivative + 0.2 * derivative
        self.previous_distance = distance
        if self.confirmations < 5:
            return 0.0, 0.0, 0.0
        error = distance - self.config.clearance
        if self.state == "APPROACH":
            if abs(error) > 0.06:
                self.reason = "Adjusting left clearance"
                return 0.0, max(-0.10, min(0.10, 0.5 * error)), 0.0
            self.state = "FOLLOW"
            self.entry = tuple(pos)
            self.previous_pose = (*pos, yaw)
        previous = self.previous_pose
        self.travel += math.dist(pos, previous[:2])
        self.turn += wrap(yaw - previous[2])
        self.previous_pose = (*pos, yaw)
        closure = math.dist(pos, self.entry)
        self.left_entry |= closure > 0.45
        if self.left_entry and self.travel > 2.0 and self.turn > math.radians(330) and closure < 0.25:
            self.state, self.reason = "COMPLETE", "Approximate lap closure; landing"
            return 0.0, 0.0, 0.0

        self.reason = "Following surface on left"
        yaw_rate = max(-30.0, min(30.0, 90.0 * error + 65.0 * self.derivative))
        speed = self.config.speed
        front = ranges["front"]
        if front is not None and front < self.config.clearance:
            # Turn away from a concave corner instead of driving into it.
            speed, yaw_rate = 0.0, -20.0
        elif abs(error) > 0.20:
            speed *= 0.4
        return speed, 0.0, yaw_rate


class Telemetry:
    """Atomically copy asynchronous log packets and track their arrival times."""

    def __init__(self):
        self.lock = Lock()
        self.packets = {}
        self.error = None

    def receive(self, _timestamp, data, config):
        with self.lock:
            self.packets[config.name] = (time.monotonic(), dict(data))

    def fail(self, _config, message):
        with self.lock:
            self.error = str(message)

    def raw_ranges(self, now):
        """Diagnostic read: preserve zeros and sentinels exactly as received."""
        with self.lock:
            if self.error:
                raise RuntimeError(self.error)
            packet = self.packets.get("orbit_range")
            if packet is None or now - packet[0] > 0.5:
                raise RuntimeError("Missing or stale range telemetry")
            return {name: packet[1][f"range.{name}"]
                    for name in ("front", "back", "left", "right", "up")}

    def snapshot(self, now):
        with self.lock:
            if self.error:
                raise RuntimeError(self.error)
            if any(name not in self.packets or now - self.packets[name][0] > 0.5
                   for name in ("orbit_pose", "orbit_range")):
                raise RuntimeError("Missing or stale telemetry")
            data = {key: value for _, packet in self.packets.values()
                    for key, value in packet.items()}
        pos = (data["stateEstimate.x"], data["stateEstimate.y"])
        yaw = math.radians(data["stabilizer.yaw"])
        raw_ranges = {name: data[f"range.{name}"]
                      for name in ("front", "back", "left", "right", "up")}
        invalid = {name: value for name, value in raw_ranges.items()
                   if not math.isfinite(value) or value <= 0}
        if invalid:
            # Initial log packets can arrive before usable range measurements.
            # Do not interpret zero as free space, especially during flight.
            raise RuntimeError(f"Invalid Multi-ranger readings (raw mm): {invalid}")
        # Treat readings beyond the deck's nominal 4 m range as no return.
        ranges = {name: (None if data[f"range.{name}"] >= 4000 else
                         data[f"range.{name}"] / 1000.0)
                  for name in ("front", "back", "left", "right", "up")}
        if not all(math.isfinite(v) for v in (*pos, yaw, data["pm.vbat"])):
            raise RuntimeError("Non-finite telemetry")
        return pos, yaw, ranges, data["pm.vbat"]


def check_sensors(args):
    """Read native range logs for ten seconds; never arm or send setpoints."""
    try:
        import cflib.crtp
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.log import LogConfig
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
    except ImportError as exc:
        print(f"Sensor check requires cflib: {exc}", file=sys.stderr)
        return 1
    telemetry = Telemetry()
    print(f"SENSOR CHECK: {args.uri} — no arming or takeoff")
    print("Raw millimeters for 10 seconds. Move a flat object 20–50 cm behind the rear sensor.")
    cflib.crtp.init_drivers()
    try:
        # Retrieve a fresh log TOC for diagnostics, independent of cached IDs.
        with TemporaryDirectory(prefix="orbit-sensors-") as cache_dir, \
                SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache=cache_dir)) as scf:
            detected = scf.cf.param.get_value("deck.bcMultiranger", timeout=5.0)
            print(f"deck.bcMultiranger={detected}")
            if not int(detected):
                raise RuntimeError("Multi-ranger deck not detected")
            scf.cf.connection_lost.add_callback(lambda _uri, msg: telemetry.fail(None, msg))
            log = LogConfig(name="orbit_range", period_in_ms=100)
            for name in ("front", "back", "left", "right", "up"):
                log.add_variable(f"range.{name}")  # Use firmware's declared type.
            scf.cf.log.add_config(log)
            log.data_received_cb.add_callback(telemetry.receive)
            log.error_cb.add_callback(telemetry.fail)
            problems = ["No readings received"]
            try:
                log.start()
                for _ in range(20):
                    time.sleep(0.5)
                    try:
                        readings = telemetry.raw_ranges(time.monotonic())
                        print("  ".join(f"{name}={value}" for name, value in readings.items()))
                        problems = []
                        for name, value in readings.items():
                            minimum = 300 if name == "up" else 250
                            if not math.isfinite(value) or value <= 0:
                                problems.append(f"{name}={value} mm is invalid")
                            elif value < minimum:
                                problems.append(f"{name}={value} mm is below {minimum} mm clearance")
                    except RuntimeError as exc:
                        print(exc)
                        problems = [str(exc)]
            finally:
                log.stop()
            if problems:
                print("Final readings block flight: " + "; ".join(problems))
                return 1
            print("Final readings meet clearance thresholds. This does not validate sensor accuracy; "
                  "verify each sensor responds to a nearby object.")
            return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Sensor check failed: {exc}", file=sys.stderr)
        return 1


def fly(args):
    """Connect only when explicitly requested; always attempt landing on exit."""
    try:
        import cflib.crtp
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.log import LogConfig
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
        from cflib.positioning.motion_commander import MotionCommander
    except ImportError as exc:
        print(f"Flight requires cflib in this Python environment: {exc}", file=sys.stderr)
        return 1

    controller = FlightController(Config(clearance=args.clearance, speed=args.speed,
                                         time_limit=args.timeout, stop_distance=0.25))
    telemetry = Telemetry()
    logs = []
    print(f"FLIGHT: {args.uri}, height {args.height:.2f} m, speed {args.speed:.2f} m/s")
    print("Object must be on the LEFT. Ctrl+C requests landing.")
    cflib.crtp.init_drivers()
    try:
        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            for param in ("deck.bcFlow2", "deck.bcMultiranger"):
                if not int(scf.cf.param.get_value(param, timeout=5.0)):
                    raise RuntimeError(f"Required deck not detected: {param}")
            scf.cf.connection_lost.add_callback(lambda _uri, msg: telemetry.fail(None, msg))
            try:
                for name, variables in (
                    ("orbit_pose", [("stateEstimate.x", "float"), ("stateEstimate.y", "float"),
                                    ("stabilizer.yaw", "float"), ("pm.vbat", "float")]),
                    ("orbit_range", [(f"range.{side}", "uint16_t")
                                     for side in ("front", "back", "left", "right", "up")]),
                ):
                    log = LogConfig(name=name, period_in_ms=50)
                    for variable, kind in variables:
                        log.add_variable(variable, kind)
                    scf.cf.log.add_config(log)
                    log.data_received_cb.add_callback(telemetry.receive)
                    log.error_cb.add_callback(telemetry.fail)
                    logs.append(log)
                    log.start()
                deadline = time.monotonic() + 5.0
                last_wait_message = None
                next_wait_report = 0.0
                while True:
                    try:
                        pos, yaw, ranges, battery = telemetry.snapshot(time.monotonic())
                        break
                    except RuntimeError as exc:
                        if time.monotonic() >= deadline:
                            raise RuntimeError(f"Sensors not ready after 5 seconds: {exc}") from exc
                        if args.diag and (str(exc) != last_wait_message or
                                          time.monotonic() >= next_wait_report):
                            print(f"Waiting for sensors: {exc}")
                            last_wait_message = str(exc)
                            next_wait_report = time.monotonic() + 1.0
                        time.sleep(0.05)
                if battery < 3.5:
                    raise RuntimeError(f"Battery too low for takeoff: {battery:.2f} V")
                # Validate fresh ranges before arming, without requiring the
                # object to intersect the beams until the drone is airborne.
                controller.step(ranges, pos, yaw, 0.05)
                if controller.state == "ABORT":
                    raise RuntimeError(controller.reason)
                arm = getattr(scf.cf.platform, "send_arming_request", None)
                if arm is not None:
                    arm(True)
                    time.sleep(1.0)
                motion = MotionCommander(scf, default_height=args.height)
                try:
                    motion.take_off()
                    origin, _, _, _ = telemetry.snapshot(time.monotonic())
                    # Ground-level surfaces need not be the airborne target.
                    controller = FlightController(controller.config)
                    previous = time.monotonic() - 0.05
                    last_state = None
                    while True:
                        now = time.monotonic()
                        pos, yaw, ranges, battery = telemetry.snapshot(now)
                        if battery < 3.2:
                            raise RuntimeError(f"Low battery: {battery:.2f} V")
                        if math.dist(pos, origin) > args.max_radius:
                            raise RuntimeError("Maximum distance from takeoff exceeded")
                        vx, vy, rate = controller.step(ranges, pos, yaw, now - previous)
                        previous = now
                        if controller.state != last_state or args.diag:
                            print(f"{controller.elapsed:6.1f}s {controller.state:9s} "
                                  f"left={ranges['left']} v=({vx:.2f},{vy:.2f}) "
                                  f"yaw_rate={rate:.1f}: {controller.reason}")
                        last_state = controller.state
                        if controller.state in ("COMPLETE", "ABORT"):
                            break
                        motion.start_linear_motion(vx, vy, 0.0, rate_yaw=rate)
                        time.sleep(max(0.0, 0.05 - (time.monotonic() - now)))
                finally:
                    # Explicit finally also covers interruption during takeoff.
                    try:
                        motion.stop()
                    finally:
                        motion.land()
            finally:
                for log in logs:
                    log.stop()
    except KeyboardInterrupt:
        print("Interrupted; landing requested.")
        return 130
    except Exception as exc:
        print(f"Flight stopped: {exc}", file=sys.stderr)
        return 1
    return 0 if controller.state == "COMPLETE" else 1


class DemoWorld:
    """Ground truth is restricted to sensing, collision checks and rendering."""

    def __init__(self, scenario):
        self.scenario = scenario
        self.center = (1.7, 0.4)
        self.radius = 0.45
        self.box = (1.25, -0.05, 2.15, 0.85)

    def surface_distance(self, pos):
        if self.scenario == "empty":
            return math.inf
        if self.scenario == "circle":
            return math.dist(pos, self.center) - self.radius
        x0, y0, x1, y1 = self.box
        if x0 <= pos[0] <= x1 and y0 <= pos[1] <= y1:
            return -min(pos[0]-x0, x1-pos[0], pos[1]-y0, y1-pos[1])
        return math.hypot(max(x0-pos[0], 0, pos[0]-x1),
                          max(y0-pos[1], 0, pos[1]-y1))

    def ray(self, pos, angle):
        if self.scenario == "empty":
            return None
        dx, dy = math.cos(angle), math.sin(angle)
        if self.scenario == "circle":
            ox, oy = pos[0]-self.center[0], pos[1]-self.center[1]
            b = ox*dx + oy*dy
            disc = b*b - (ox*ox + oy*oy - self.radius*self.radius)
            if disc < 0:
                return None
            distance = -b - math.sqrt(disc)
        else:
            near, far = 0.0, math.inf
            for origin, direction, lo, hi in (
                (pos[0], dx, self.box[0], self.box[2]),
                (pos[1], dy, self.box[1], self.box[3]),
            ):
                if abs(direction) < 1e-12:
                    if not lo <= origin <= hi:
                        return None
                    continue
                a, b = sorted(((lo-origin)/direction, (hi-origin)/direction))
                near, far = max(near, a), min(far, b)
                if near > far:
                    return None
            distance = near
        return distance if 0 < distance <= 4.0 else None

    def scan(self, pos, yaw):
        # Ideal instantaneous 360-degree sweep, 5-degree spacing. A real deck
        # would need rotation, timestamps and pose compensation to build this.
        bearings = [math.radians(i) for i in range(-180, 180, 5)]
        return [(a, self.ray(pos, yaw+a)) for a in bearings]


def simulate(scenario="circle"):
    world = DemoWorld(scenario)
    controller = OrbitController()
    pos, yaw, dt = (0.0, 0.0), 0.0, 0.1
    log = []
    for _ in range(1202):
        scan = world.scan(pos, yaw)
        vx, vy = controller.step(scan, pos, yaw, dt)
        log.append({"t": round(controller.elapsed, 3), "x": pos[0],
                    "y": pos[1], "state": controller.state,
                    "clearance": world.surface_distance(pos),
                    "vx": vx, "vy": vy, "reason": controller.reason})
        if controller.state in ("COMPLETE", "ABORT"):
            break
        pos = (pos[0]+vx*dt, pos[1]+vy*dt)
        # A 9 cm footprint is a demo assumption, not a model specification.
        if world.surface_distance(pos) < 0.09:
            controller.abort("Simulated footprint collision")
            log.append({"t": round(controller.elapsed+dt, 3), "x": pos[0],
                        "y": pos[1], "state": "ABORT",
                        "clearance": world.surface_distance(pos),
                        "vx": 0.0, "vy": 0.0, "reason": controller.reason})
            break
    return world, controller, log


def plot_demo(world, log, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle

    colors = {"SEARCH": "#67768a", "APPROACH": "#d58a23", "FOLLOW": "#167b72",
              "REACQUIRE": "#ad65a2", "COMPLETE": "#2261b0", "ABORT": "#b64141"}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), gridspec_kw={"width_ratios": [1.25, 1]})
    fig.patch.set_facecolor("#f7f8fb")
    ax, dist_ax = axes
    if world.scenario == "circle":
        ax.add_patch(Circle(world.center, world.radius, color="#24364b"))
    elif world.scenario == "box":
        x0, y0, x1, y1 = world.box
        ax.add_patch(Rectangle((x0, y0), x1-x0, y1-y0, color="#24364b"))
    for state, color in colors.items():
        rows = [r for r in log if r["state"] == state]
        if rows:
            ax.scatter([r["x"] for r in rows], [r["y"] for r in rows],
                       s=9, color=color, label=state.title(), zorder=3)
    ax.scatter([0], [0], marker="^", s=110, color="#24364b", zorder=5)
    ax.annotate("Takeoff reference", (0, 0), xytext=(8, -25), textcoords="offset points", fontsize=9)
    ax.set_aspect("equal")
    ax.set(xlabel="Local x (m)", ylabel="Local y (m)", title="Discovery and boundary following")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.18)
    dist_ax.plot([r["t"] for r in log], [r["clearance"] for r in log], color="#167b72", lw=2)
    dist_ax.axhline(0.55, color="#d58a23", linestyle="--", label="Desired clearance: 0.55 m")
    dist_ax.set(xlabel="Simulated time (s)", ylabel="Distance to surface (m)", title="Surface clearance")
    dist_ax.legend(fontsize=8)
    dist_ax.grid(alpha=0.18)
    fig.suptitle("AMAZE  /  Autonomous Object Orbit", fontsize=19, fontweight="bold", x=0.06, ha="left")
    fig.text(0.06, 0.91, "Simulation concept • ideal range sweeps • no target coordinates supplied to controller", color="#526277", fontsize=10)
    fig.text(0.06, 0.02, f"{world.scenario.title()} scenario  |  {log[-1]['state']}  |  {log[-1]['t']:.1f} simulated seconds  |  Hardware integration pending", fontsize=9, color="#526277")
    fig.tight_layout(rect=(0.02, 0.06, 0.99, 0.87))
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("circle", "box", "empty"), default="circle")
    parser.add_argument("--csv", type=Path, help="Optional trace output")
    parser.add_argument("--plot", type=Path, help="Optional chart; requires matplotlib")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fly", action="store_true", help="Connect, take off and follow a real surface")
    mode.add_argument("--check-sensors", action="store_true", help="Read raw ranges for 10 seconds without taking off")
    parser.add_argument("--uri", default="radio://0/80/2M/E7E7E7E7E7")
    parser.add_argument("--height", type=float, default=0.45, help="Flight height in meters")
    parser.add_argument("--speed", type=float, default=0.10, help="Flight forward speed in m/s")
    parser.add_argument("--clearance", type=float, default=0.55, help="Desired left range in meters")
    parser.add_argument("--timeout", type=float, default=120.0, help="Maximum mission seconds")
    parser.add_argument("--max-radius", type=float, default=3.0, help="Maximum distance from takeoff in meters")
    parser.add_argument("--diag", action="store_true", help="Print every flight control tick")
    args = parser.parse_args(argv)
    if args.check_sensors:
        if args.csv or args.plot:
            parser.error("--csv and --plot are simulation-only")
        return check_sensors(args)
    if args.fly:
        if args.csv or args.plot:
            parser.error("--csv and --plot are simulation-only")
        for name, low, high in (("height", 0.2, 1.0), ("speed", 0.02, 0.20),
                                ("clearance", 0.4, 1.0), ("timeout", 5.0, 180.0),
                                ("max_radius", 0.5, 5.0)):
            if not low <= getattr(args, name) <= high:
                parser.error(f"--{name.replace('_', '-')} must be between {low} and {high}")
        return fly(args)
    world, controller, log = simulate(args.scenario)
    previous = None
    for row in log:
        if row["state"] != previous:
            print(f"{row['t']:6.1f}s  {row['state']:10s}  {row['reason']}")
            previous = row["state"]
    minimum = min(r["clearance"] for r in log)
    print(f"Final state: {controller.state}; minimum center-to-surface clearance: {minimum:.3f} m")
    print("Simulation only: ideal scanning and odometry; no drone connection.")
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=log[0].keys())
            writer.writeheader()
            writer.writerows(log)
    if args.plot:
        plot_demo(world, log, args.plot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
