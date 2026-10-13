"""Autonomous boundary-following concept demo. Simulation only; no radio code.

The controller receives synthetic range sweeps and an ideal local pose. Only
the simulator knows obstacle geometry. A sweep is an idealized active scan,
not the four simultaneous horizontal readings of a physical Multi-ranger.
"""

from __future__ import annotations

import argparse
import csv
import math
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("circle", "box", "empty"), default="circle")
    parser.add_argument("--csv", type=Path, help="Optional trace output")
    parser.add_argument("--plot", type=Path, help="Optional chart; requires matplotlib")
    args = parser.parse_args()
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
