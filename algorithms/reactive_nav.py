# this should be good for navigation
from __future__ import annotations

import argparse
import math
import sys

from collections import deque
from dataclasses import dataclass, field

import numpy as np

# Body-frame unit vectors for the four horizontal beams.
# Crazyflie body axes: +x forward, +y left.
BEAM_DIRS_BODY = {
    "front": np.array([1.0, 0.0]),
    "back": np.array([-1.0, 0.0]),
    "left": np.array([0.0, 1.0]),
    "right": np.array([0.0, -1.0]),
}

BEAM_FOV_DEG = 27.0
BEAM_MAX_RANGE = 4.0


def rot(theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s], [s, c]])

# 1. ALGORITHM

@dataclass
class Gains:
    k_attract: float = 1.0
    k_repel: float = 0.42          # repulsion strength
    d_influence: float = 1.10      # [m] beyond this, obstacles are ignored
    d_panic: float = 0.28          # [m] below this, repulsion only, no goal pull
    v_max: float = 0.35            # [m/s] speed cap -- keep low, sensing is sparse
    goal_tol: float = 0.18         # [m] arrival radius
    axis_bias: float = 0.35        # 0 = free motion, 1 = snap to beam axes
    yaw_rate: float = 0.55         # [rad/s] sweep rate; 0 disables sweeping
    stall_window: float = 2.5      # [s] look-back for progress
    stall_progress: float = 0.08   # [m] less than this over the window = stuck
    wall_target: float = 0.55      # [m] standoff held while wall-following
    k_wall: float = 0.9            # correction gain toward wall_target
    min_escape_time: float = 2.0   # [s] minimum dwell in escape, stops thrash
    escape_reset: float = 6.0      # [s] clear of escape before re-picking a side


class ReactiveController:

    SEEK = "seek"
    ESCAPE = "escape"
    ARRIVED = "arrived"

    def __init__(self, goal, gains: Gains | None = None):
        self.goal = np.asarray(goal, dtype=float)
        self.g = gains or Gains()
        self.state = self.SEEK
        self._hist: deque = deque()
        self._escape_sign = 1.0
        self._escape_entry_dist = math.inf
        self._escape_t0 = 0.0
        self._last_escape_end = -1e9
        self._normal_filt: np.ndarray | None = None
        self._t = 0.0

# potential field

    def _repulsion(self, ranges: dict, yaw: float) -> np.ndarray:
        """Sum of per-beam repulsive vectors, in the world frame."""
        total = np.zeros(2)
        R = rot(yaw)
        for name, d in ranges.items():
            if name not in BEAM_DIRS_BODY or d is None:
                continue
            if d <= 0.0 or d >= self.g.d_influence:
                continue
            d = max(d, 0.06)  # avoid a singularity at zero range
            world_dir = R @ BEAM_DIRS_BODY[name]
            magnitude = self.g.k_repel * (1.0 / d - 1.0 / self.g.d_influence)
            total += -world_dir * magnitude
        return total

    def _closest_beam_normal(self, ranges: dict, yaw: float):
        """World-frame outward normal of the nearest obstacle, and its range."""
        best, best_d = None, math.inf
        R = rot(yaw)
        for name, d in ranges.items():
            if name not in BEAM_DIRS_BODY or d is None or d <= 0:
                continue
            if d < best_d:
                best_d = d
                best = R @ BEAM_DIRS_BODY[name]
        return best, best_d

    def _apply_axis_bias(self, v: np.ndarray, yaw: float) -> np.ndarray:
        """Nudge the command toward the nearest beam axis.

        Travelling along a beam direction means travelling where the drone can
        actually see. Full snapping would be jerky, so this blends.
        """
        if self.g.axis_bias <= 0.0:
            return v
        speed = float(np.linalg.norm(v))
        if speed < 1e-6:
            return v
        R = rot(yaw)
        axes = [R @ d for d in BEAM_DIRS_BODY.values()]
        best = max(axes, key=lambda a: float(a @ v))
        blended = (1.0 - self.g.axis_bias) * (v / speed) + self.g.axis_bias * best
        n = float(np.linalg.norm(blended))
        return v if n < 1e-9 else blended / n * speed

    # stall detection

    def _note_progress(self, dist: float) -> bool:
        self._hist.append((self._t, dist))
        while self._hist and self._t - self._hist[0][0] > self.g.stall_window:
            self._hist.popleft()
        # Gate on the span the history actually covers, NOT on absolute elapsed
        # time. Using self._t here is a trap: every _hist.clear() (on a state
        # change) leaves a near-empty history that still passes an absolute
        # check, so two ticks later we compare samples 0.05 s apart, see no
        # progress, and declare a stall. That flips the escape direction every
        # other tick and the drone vibrates in place instead of travelling.
        if len(self._hist) < 2:
            return False
        if self._hist[-1][0] - self._hist[0][0] < self.g.stall_window:
            return False
        improvement = self._hist[0][1] - dist
        return improvement < self.g.stall_progress

    def _goal_visible(self, ranges: dict, yaw: float, to_goal: np.ndarray, dist: float) -> bool:
        """True if no beam pointing goal-ward reports something in the way."""
        R = rot(yaw)
        unit = to_goal / max(dist, 1e-9)
        for name, d in ranges.items():
            if name not in BEAM_DIRS_BODY or d is None or d <= 0:
                continue
            world_dir = R @ BEAM_DIRS_BODY[name]
            if float(world_dir @ unit) > 0.7 and d < min(dist, self.g.d_influence):
                return False
        return True

    # main entry point

    def step(self, ranges: dict, pos, yaw: float, dt: float):
        """Returns (v_world (2,), yaw_rate, state)."""
        self._t += dt
        pos = np.asarray(pos, dtype=float)
        to_goal = self.goal - pos
        dist = float(np.linalg.norm(to_goal))

        if dist < self.g.goal_tol:
            self.state = self.ARRIVED
            return np.zeros(2), 0.0, self.state

        rep = self._repulsion(ranges, yaw)
        normal, nearest = self._closest_beam_normal(ranges, yaw)

        # The nearest-beam normal is a 90-degree-quantised estimate of the true
        # surface normal, and it jumps whenever a different beam becomes the
        # nearest one. Unfiltered, that flips the wall-following tangent and
        # the drone vibrates in place instead of sliding along. A sign check
        # resets the filter when we genuinely meet a different surface.
        if normal is not None:
            if self._normal_filt is None or float(self._normal_filt @ normal) < 0.0:
                self._normal_filt = normal.copy()
            else:
                self._normal_filt = 0.7 * self._normal_filt + 0.3 * normal
                nn = float(np.linalg.norm(self._normal_filt))
                if nn > 1e-9:
                    self._normal_filt = self._normal_filt / nn

        # Stall detection runs unconditionally. An earlier version skipped it
        # while close to an obstacle, which deadlocked: the drone could be
        # pinned against a wall and never register as stuck.
        stalled = self._note_progress(dist)

        if self.state == self.SEEK:
            if stalled and normal is not None:
                # Commit to one side and stay committed. Bug algorithms
                # circumnavigate in a single consistent direction; re-deciding
                # mid-escape makes the drone dither and undo its own progress.
                # The side is only re-chosen if we have been clear of
                # obstacles long enough that this is a fresh encounter.
                if self._t - self._last_escape_end > self.g.escape_reset:
                    tangent = np.array([-normal[1], normal[0]])
                    self._escape_sign = 1.0 if float(tangent @ to_goal) > 0 else -1.0
                self._escape_entry_dist = dist
                self._escape_t0 = self._t
                self.state = self.ESCAPE
                self._hist.clear()

        elif self.state == self.ESCAPE:
            # Leave as soon as the goal is actually reachable. The textbook
            # Bug2 rule also demands being closer than the hit point, but that
            # is unsatisfiable if the drone rounded the obstacle the long way:
            # it ends up further out, having earned a clear shot at the goal,
            # and refuses to take it. A minimum dwell time prevents the
            # seek/escape thrash that the distance test was there to stop.
            dwell = self._t - self._escape_t0
            if dwell > self.g.min_escape_time and self._goal_visible(ranges, yaw, to_goal, dist):
                self.state = self.SEEK
                self._last_escape_end = self._t
                self._hist.clear()

        if self.state == self.SEEK:
            attract = self.g.k_attract * to_goal / dist
            v = attract + rep
        else:
            if normal is None or self._normal_filt is None:
                self.state = self.SEEK
                return np.zeros(2), self.g.yaw_rate, self.state
            normal = self._normal_filt
            tangent = self._escape_sign * np.array([-normal[1], normal[0]])
            # normal points TOWARD the obstacle. Positive error means we are
            # further out than the target standoff, so we steer toward the
            # wall: +normal. Getting this sign backwards makes the standoff
            # unholdable and drives the drone into the panic band.
            error = nearest - self.g.wall_target
            v = tangent + normal * self.g.k_wall * error

        # Panic is an additive bias, not a mode. Overriding the command
        # outright would cancel the tangential term and stop the drone from
        # sliding out along a boundary.
        if nearest < self.g.d_panic:
            v = v + rep * 3.0

        n = float(np.linalg.norm(v))
        if n > 1e-9:
            taper = min(1.0, dist / (3.0 * self.g.goal_tol))
            v = v / n * self.g.v_max * taper
        v = self._apply_axis_bias(v, yaw)

        # The sweep covers blind wedges in transit, but while wall-following it
        # keeps handing the wall to a different beam and destabilises the
        # normal. Hold heading instead -- the wall is already in view.
        yaw_cmd = 0.0 if self.state == self.ESCAPE else self.g.yaw_rate
        return v, yaw_cmd, self.state


# 2. SIMULATOR

@dataclass
class Rect:
    lo: np.ndarray
    hi: np.ndarray

    def __post_init__(self):
        self.lo = np.asarray(self.lo, dtype=float)
        self.hi = np.asarray(self.hi, dtype=float)


@dataclass
class SimWorld:
    bounds_lo: np.ndarray
    bounds_hi: np.ndarray
    rects: list = field(default_factory=list)

    def __post_init__(self):
        self.bounds_lo = np.asarray(self.bounds_lo, dtype=float)
        self.bounds_hi = np.asarray(self.bounds_hi, dtype=float)
        # Represent the room walls as four thick slabs so rays hit them.
        t = 0.30
        lo, hi = self.bounds_lo, self.bounds_hi
        self.walls = [
            Rect([lo[0] - t, lo[1] - t], [hi[0] + t, lo[1]]),
            Rect([lo[0] - t, hi[1]], [hi[0] + t, hi[1] + t]),
            Rect([lo[0] - t, lo[1] - t], [lo[0], hi[1] + t]),
            Rect([hi[0], lo[1] - t], [hi[0] + t, hi[1] + t]),
        ]

    def all_rects(self):
        return self.rects + self.walls

    def occupied(self, p) -> bool:
        p = np.asarray(p, dtype=float)
        for r in self.all_rects():
            if np.all(p >= r.lo) and np.all(p <= r.hi):
                return True
        return False


def _ray_rect(origin, direction, rect: Rect) -> float:
    """Slab method. Returns distance along direction, or inf."""
    tmin, tmax = 0.0, math.inf
    for k in range(2):
        if abs(direction[k]) < 1e-12:
            if origin[k] < rect.lo[k] or origin[k] > rect.hi[k]:
                return math.inf
            continue
        t1 = (rect.lo[k] - origin[k]) / direction[k]
        t2 = (rect.hi[k] - origin[k]) / direction[k]
        if t1 > t2:
            t1, t2 = t2, t1
        tmin = max(tmin, t1)
        tmax = min(tmax, t2)
        if tmin > tmax:
            return math.inf
    return tmin if tmin >= 0.0 else math.inf


def simulate_ranger(world: SimWorld, pos, yaw: float, rays_per_beam: int = 7) -> dict:
    """Fake a Multi-ranger, including its finite field of view.

    Each beam fans several rays across its real 27-degree cone and reports the
    minimum. This is what makes the blind diagonal wedges show up in
    simulation -- a single centre ray per beam would hide the failure mode the
    escape behaviour exists to handle.
    """
    out = {}
    half = math.radians(BEAM_FOV_DEG * 0.5)
    offsets = np.linspace(-half, half, rays_per_beam)
    rects = world.all_rects()
    for name, body_dir in BEAM_DIRS_BODY.items():
        base = math.atan2(body_dir[1], body_dir[0]) + yaw
        best = BEAM_MAX_RANGE
        for off in offsets:
            ang = base + off
            d = np.array([math.cos(ang), math.sin(ang)])
            for r in rects:
                t = _ray_rect(pos, d, r)
                if t < best:
                    best = t
        out[name] = float(best)
    return out


def simulate(world: SimWorld, start, goal, gains: Gains | None = None,
             dt: float = 0.05, t_limit: float = 120.0, tau: float = 0.25):
    """Run the controller against the simulated world.

    Velocity is tracked through a first-order lag, so gains that look fine
    against an ideal integrator but oscillate on real hardware also oscillate
    here.
    """
    ctrl = ReactiveController(goal, gains)
    pos = np.asarray(start, dtype=float).copy()
    vel = np.zeros(2)
    yaw = 0.0
    log = {"t": [], "pos": [], "state": [], "dist": [], "nearest": []}
    t = 0.0
    collided = False

    while t < t_limit:
        ranges = simulate_ranger(world, pos, yaw)
        v_cmd, yaw_rate, state = ctrl.step(ranges, pos, yaw, dt)

        log["t"].append(t)
        log["pos"].append(pos.copy())
        log["state"].append(state)
        log["dist"].append(float(np.linalg.norm(ctrl.goal - pos)))
        log["nearest"].append(min(ranges.values()))

        if state == ReactiveController.ARRIVED:
            break

        vel += (v_cmd - vel) * (dt / tau)
        pos = pos + vel * dt
        yaw = (yaw + yaw_rate * dt) % (2 * math.pi)
        t += dt

        if world.occupied(pos):
            collided = True
            break

    log["pos"] = np.array(log["pos"])
    log["t"] = np.array(log["t"])
    log["dist"] = np.array(log["dist"])
    log["nearest"] = np.array(log["nearest"])
    log["collided"] = collided
    log["arrived"] = ctrl.state == ReactiveController.ARRIVED
    log["duration"] = t
    log["escape_fraction"] = (
            sum(1 for s in log["state"] if s == ReactiveController.ESCAPE)
            / max(len(log["state"]), 1)
    )
    return log


# 3. SCENARIOS

def scenario_open():
    w = SimWorld([0, 0], [5, 4])
    return "open", w, np.array([0.6, 2.0]), np.array([4.4, 2.0])


def scenario_slalom():
    w = SimWorld([0, 0], [5, 4], rects=[
        Rect([1.4, 0.0], [1.7, 2.5]),
        Rect([3.0, 1.5], [3.3, 4.0]),
    ])
    return "slalom", w, np.array([0.5, 3.4]), np.array([4.5, 3.4])


def scenario_trap():
    """Concave pocket opening toward the start -- the classic local minimum."""
    w = SimWorld([0, 0], [5, 4], rects=[
        Rect([2.6, 1.0], [2.9, 3.0]),
        Rect([2.6, 1.0], [3.9, 1.3]),
        Rect([2.6, 2.7], [3.9, 3.0]),
    ])
    return "trap", w, np.array([0.7, 2.0]), np.array([4.5, 2.0])


def scenario_wall():
    """Flat wall square across the goal direction."""
    w = SimWorld([0, 0], [5, 4], rects=[
        Rect([2.4, 0.8], [2.7, 3.2]),
    ])
    return "wall", w, np.array([0.6, 2.0]), np.array([4.4, 2.0])


SCENARIOS = {
    "open": scenario_open,
    "wall": scenario_wall,
    "slalom": scenario_slalom,
    "trap": scenario_trap,
}


# 4. PLOTTING

def plot_runs(runs, save=None):
    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    n = len(runs)
    fig, axes = plt.subplots(2, n, figsize=(5.0 * n, 7.4), squeeze=False)

    for col, (name, world, start, goal, log) in enumerate(runs):
        ax = axes[0][col]
        for r in world.rects:
            ax.add_patch(Rectangle(r.lo, *(r.hi - r.lo),
                                   facecolor="#b0342c", alpha=0.3, edgecolor="#7a241e"))
        pos = log["pos"]
        states = log["state"]
        seek = np.array([s == ReactiveController.SEEK for s in states])
        esc = np.array([s == ReactiveController.ESCAPE for s in states])
        ax.plot(pos[seek, 0], pos[seek, 1], ".", ms=2.4, color="#0b8043", label="seek")
        if esc.any():
            ax.plot(pos[esc, 0], pos[esc, 1], ".", ms=2.4, color="#e37400", label="escape")
        ax.scatter(*start, c="#0b8043", s=70, marker="^", zorder=5)
        ax.scatter(*goal, c="#c5221f", s=110, marker="*", zorder=5)
        ax.add_patch(plt.Circle(goal, 0.18, fill=False, ls="--", color="#c5221f", lw=0.8))
        ax.set_xlim(world.bounds_lo[0], world.bounds_hi[0])
        ax.set_ylim(world.bounds_lo[1], world.bounds_hi[1])
        ax.set_aspect("equal")
        verdict = "reached" if log["arrived"] else ("COLLIDED" if log["collided"] else "timeout")
        ax.set_title(f"{name}: {verdict} in {log['duration']:.1f} s", fontsize=10)
        ax.set_xlabel("x [m]")
        if col == 0:
            ax.set_ylabel("y [m]")
            ax.legend(fontsize=8, loc="lower left")
        ax.grid(alpha=0.2)

        ax2 = axes[1][col]
        ax2.plot(log["t"], log["dist"], color="#1f77b4", label="distance to goal")
        ax2.plot(log["t"], log["nearest"], color="#e37400", lw=0.9, label="nearest obstacle")
        if esc.any():
            ax2.fill_between(log["t"], 0, log["dist"].max(), where=esc,
                             color="#e37400", alpha=0.12, step="mid")
        ax2.axhline(0.28, color="#c5221f", ls=":", lw=0.9)
        ax2.set_xlabel("t [s]");
        ax2.set_ylabel("[m]")
        ax2.grid(alpha=0.25)
        if col == 0:
            ax2.legend(fontsize=8)

    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=140)
        print(f"Figure written to {save}")
    else:
        plt.show()


# 5. REAL FLIGHT

def fly(goal_xy, uri: str, height: float = 0.45, gains: Gains | None = None,
        rate_hz: float = 10.0, t_limit: float = 90.0):
    """Run the same controller on a real Crazyflie.

    The goal is a DISPLACEMENT from the takeoff point, not an absolute room
    coordinate, so this needs only a Flow deck plus Multi-ranger -- no
    Lighthouse or Loco.

    NOT TESTED AGAINST HARDWARE: cflib was unavailable in the authoring
    environment. Fly it with props off first and watch the printed state.
    """
    try:
        import cflib.crtp
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
        from cflib.crazyflie.log import LogConfig
        from cflib.utils.multiranger import Multiranger
        from cflib.positioning.motion_commander import MotionCommander
    except ImportError:
        print("cflib is not installed.  pip install cflib", file=sys.stderr)
        return 1

    import time

    ctrl = ReactiveController(np.asarray(goal_xy, dtype=float), gains)
    dt = 1.0 / rate_hz

    cflib.crtp.init_drivers()
    with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        for param, label in [("deck.bcFlow2", "Flow deck v2"),
                             ("deck.bcMultiranger", "Multi-ranger")]:
            try:
                if not int(scf.cf.param.get_value(param, timeout=2.0)):
                    print(f"{label} not detected. Aborting.", file=sys.stderr)
                    return 1
                print(f"  {label}: detected")
            except Exception:
                print(f"  ! could not verify {label}")

        # Track the Flow deck's dead-reckoned position so the controller knows
        # how far it has come. This drifts; keep flights short.
        est = {"x": 0.0, "y": 0.0, "yaw": 0.0}
        lg = LogConfig(name="kalman", period_in_ms=50)
        lg.add_variable("kalman.stateX", "float")
        lg.add_variable("kalman.stateY", "float")
        lg.add_variable("stabilizer.yaw", "float")

        def _on_data(_ts, data, _cfg):
            est["x"] = data["kalman.stateX"]
            est["y"] = data["kalman.stateY"]
            est["yaw"] = math.radians(data["stabilizer.yaw"])

        scf.cf.log.add_config(lg)
        lg.data_received_cb.add_callback(_on_data)
        lg.start()

        try:
            scf.cf.platform.send_arming_request(True)
            time.sleep(1.0)
        except AttributeError:
            pass

        try:
            with Multiranger(scf) as mr, MotionCommander(scf, default_height=height) as mc:
                time.sleep(2.0)
                origin = np.array([est["x"], est["y"]])
                t = 0.0
                last_state = None

                while t < t_limit:
                    ranges = {
                        "front": mr.front, "back": mr.back,
                        "left": mr.left, "right": mr.right,
                    }
                    if mr.up is not None and mr.up < 0.30:
                        print("Obstacle overhead -- landing.")
                        break

                    pos = np.array([est["x"], est["y"]]) - origin
                    yaw = est["yaw"]
                    v_world, yaw_rate, state = ctrl.step(ranges, pos, yaw, dt)

                    if state != last_state:
                        print(f"  t={t:5.1f}s  {state}   pos=({pos[0]:.2f},{pos[1]:.2f})")
                        last_state = state
                    if state == ReactiveController.ARRIVED:
                        print("Goal reached.")
                        break

                    # World -> body frame for MotionCommander.
                    v_body = rot(-yaw) @ v_world
                    mc.start_linear_motion(float(v_body[0]), float(v_body[1]), 0.0,
                                           rate_yaw=math.degrees(yaw_rate))
                    time.sleep(dt)
                    t += dt

                mc.stop()
        except Exception as exc:
            print(f"\nERROR in flight loop: {exc}", file=sys.stderr)
            print("If airborne, kill power at the battery.", file=sys.stderr)
            return 1
        finally:
            lg.stop()
    print("Done.")
    return 0


# 6. ENTRY POINT

def stress(gains: Gains, trials: int = 150, seed: int = 7, t_limit: float = 120.0):
    """Randomized layouts. Four hand-built scenarios prove almost nothing;
    this is what tells you whether a gain change actually helped."""
    rng = np.random.default_rng(seed)
    res = {"reached": 0, "collided": 0, "timeout": 0}
    clearances, durations = [], []
    done = 0
    while done < trials:
        w = SimWorld([0, 0], [5, 4])
        for _ in range(int(rng.integers(1, 5))):
            cx, cy = rng.uniform(1.0, 4.0), rng.uniform(0.5, 3.5)
            wx, wy = rng.uniform(0.2, 0.6), rng.uniform(0.3, 1.8)
            w.rects.append(Rect([cx - wx / 2, cy - wy / 2], [cx + wx / 2, cy + wy / 2]))
        s = np.array([0.5, rng.uniform(0.6, 3.4)])
        g = np.array([4.5, rng.uniform(0.6, 3.4)])
        if w.occupied(s) or w.occupied(g):
            continue
        done += 1
        log = simulate(w, s, g, gains, t_limit=t_limit)
        key = "reached" if log["arrived"] else ("collided" if log["collided"] else "timeout")
        res[key] += 1
        clearances.append(log["nearest"].min())
        if log["arrived"]:
            durations.append(log["duration"])

    print(f"{trials} randomized layouts (seed {seed}):")
    for k, v in res.items():
        print(f"  {k:9s} {v:4d}  ({100 * v / trials:.0f}%)")
    print(f"  clearance   5th pct {np.percentile(clearances, 5):.2f} m, "
          f"worst {min(clearances):.2f} m")
    if durations:
        print(f"  time        median {np.median(durations):.0f} s")
    print("\n  Clearance is measured from the drone CENTRE. The Crazyflie is")
    print("  about 0.09 m in radius, so subtract that for propeller margin.")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default="all",
                    choices=list(SCENARIOS) + ["all"])
    ap.add_argument("--save", metavar="PNG")
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--fly", action="store_true")
    ap.add_argument("--goal", nargs=2, type=float, metavar=("DX", "DY"),
                    default=[2.0, 0.0], help="goal as displacement from takeoff [m]")
    ap.add_argument("--uri", default="radio://0/80/2M/E7E7E7E7E7")
    ap.add_argument("--height", type=float, default=0.45)
    ap.add_argument("--stress", action="store_true",
                    help="run randomized layouts instead of the fixed scenarios")
    ap.add_argument("--trials", type=int, default=150)
    ap.add_argument("--no-yaw-sweep", action="store_true",
                    help="disable the blind-wedge sweep (not recommended)")
    args = ap.parse_args(argv)

    gains = Gains()
    if args.no_yaw_sweep:
        gains.yaw_rate = 0.0

    if args.fly:
        return fly(args.goal, args.uri, args.height, gains)

    if args.stress:
        stress(gains, trials=args.trials)
        return 0

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    runs = []
    for nm in names:
        label, world, start, goal = SCENARIOS[nm]()
        log = simulate(world, start, goal, gains)
        verdict = "reached" if log["arrived"] else ("COLLIDED" if log["collided"] else "timeout")
        print(f"{label:8s} {verdict:9s} {log['duration']:5.1f} s  "
              f"escape {log['escape_fraction'] * 100:4.1f}%  "
              f"min clearance {log['nearest'].min():.2f} m")
        runs.append((label, world, start, goal, log))

    if not args.no_plot:
        plot_runs(runs, save=args.save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())