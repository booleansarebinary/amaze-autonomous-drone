#!/usr/bin/env python3
"""
reactive_nav.py -- go from A to B with no pre-planned path.

ALGORITHM
---------
Artificial potential fields computed directly from the Multi-ranger's beams,
with a Bug-style wall-following escape for local minima.

    SEEK    v = attract(goal) + sum(repel(beam) for each beam in range)
    ESCAPE  entered when progress toward the goal stalls. Rotates the command
            90 degrees and follows the obstacle boundary until the goal is
            locally unblocked after a minimum dwell time.

Repulsion uses the (1/d - 1/d0) form, so it vanishes exactly at the influence
radius d0 and diverges as d -> 0. Linear falloff does not work: it either
ignores obstacles until too late or pushes from across the room.

WHAT THIS DOES NOT GUARANTEE
----------------------------
This is a heuristic, not Bug2: it has no m-line or complete boundary map.
It can cycle, and a clear beam does not establish visibility in a blind wedge. The
simulator exists so you can find those cases on your laptop, not in the air.

SENSING LIMITS THAT SHAPE THE DESIGN
------------------------------------
Five VL53L1x beams (front/back/left/right/up), each about 27 degrees wide, out
to 4 m. That covers roughly 108 degrees of 360 -- the diagonals are blind. Three
mitigations are built in:
    * speed cap, so a late detection still leaves braking distance
    * axis bias, preferring motion along beam directions
    * slow continuous yaw, sweeping the cones across the blind wedges

The simulated ranger casts multiple rays across each cone's real field of view,
so it reproduces the blind wedges. A sim with ideal point sensors would tell you
comforting lies.

USAGE
-----
    python3 reactive_nav.py --scenario trap        # watch it stall and escape
    python3 reactive_nav.py --scenario slalom
    python3 reactive_nav.py --scenario all --save runs.png
    python3 reactive_nav.py --fly --goal 2.0 0.0   # needs Flow + Multi-ranger
"""

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


# ----------------------------------------------------------------------------
# 1. THE ALGORITHM  (no hardware, no simulator -- pure)
# ----------------------------------------------------------------------------


@dataclass
class Gains:
    k_attract: float = 1.0
    k_repel: float = 0.42          # repulsion strength
    d_influence: float = 1.10      # [m] beyond this, obstacles are ignored
    d_panic: float = 0.28          # [m] below this, add stronger repulsion
    v_max: float = 0.35            # [m/s] speed cap -- keep low, sensing is sparse
    goal_tol: float = 0.18         # [m] arrival radius
    axis_bias: float = 0.35        # 0 = free motion, 1 = snap to beam axes
    yaw_rate: float = 0.55         # [rad/s] sweep rate; 0 disables sweeping
    stall_window: float = 2.5      # [s] look-back for progress
    stall_progress: float = 0.08   # [m] less than this over the window = stuck
    wall_target: float = 0.30      # [m] standoff held while wall-following
    k_wall: float = 0.9            # correction gain toward wall_target
    min_escape_time: float = 2.0   # [s] minimum dwell in escape, stops thrash
    escape_reset: float = 6.0      # [s] clear of escape before re-picking a side
    cmd_smooth: float = 1.0        # 1 = no smoothing, lower = smoother command
    range_median: int = 1          # median filter length per beam, 1 = off
    k_damp: float = 0.0            # velocity feedback. 0 = undamped spring
    min_speed_frac: float = 0.30   # floor on the proximity slowdown
    cmd_accel: float = math.inf    # [m/s²] ordinary velocity-command slew limit
    brake_time: float = 0.0        # [s] closing-speed horizon; 0 disables

    @classmethod
    def flight(cls) -> "Gains":
        """Conservative profile for real hardware.

        Sweep is disabled to reduce sensitivity to delayed yaw estimates.
        Earlier reaction and smoothing do not restore blind-wedge coverage;
        this profile still needs validation against actual sensor/vehicle logs.
        """
        return cls(
            v_max=0.28,          # slower: sparse sensing needs braking distance
            d_influence=1.00,
            d_panic=0.30,
            k_repel=0.80,        # head-on balance about 0.44 m
            k_damp=0.15,         # damp the spring so it stops ringing
            min_speed_frac=0.60,
            wall_target=0.30,
            yaw_rate=0.0,        # hold heading; diagonal sensing remains limited
            axis_bias=0.0,       # measured as doing nothing, and it snaps heading
            cmd_smooth=0.50,     # lighter filter: smoothing IS lag
            range_median=3,      # reject single-frame ToF dropouts
            cmd_accel=2.0,       # avoid excessive lag while bounding reversals
            brake_time=0.60,
        )


class ReactiveController:
    """State machine over potential fields. One instance per flight.

    step() is the whole algorithm. It takes range readings in the BODY frame
    plus the current world-frame position estimate, and returns a world-frame
    velocity. Nothing in here knows whether it is driving a simulation or a
    real Crazyflie.
    """

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
        self._escape_entry_pos: np.ndarray | None = None
        self._dwell_mult = 1.0
        self._best_dist = math.inf
        self._best_t = 0.0
        self._normal_filt: np.ndarray | None = None
        self._v_prev: np.ndarray | None = None
        self._range_hist: dict = {}
        self._t = 0.0

    def _filter_ranges(self, ranges: dict) -> dict:
        """Median-filter each beam. The VL53L1x throws occasional single-frame
        spurious short readings, and one bad frame is enough to fire a panic
        response that looks like the drone lurching for no reason."""
        if self.g.range_median <= 1:
            return ranges
        out = {}
        for name in BEAM_DIRS_BODY:
            d = ranges.get(name)
            # None means nothing within range, i.e. clear -- not zero.
            d = BEAM_MAX_RANGE if (d is None or d <= 0.0) else float(d)
            buf = self._range_hist.setdefault(name, deque(maxlen=self.g.range_median))
            buf.append(d)
            out[name] = float(np.median(buf))
        return out

    # -- potential field ------------------------------------------------------

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
        """World-frame direction TOWARD the nearest obstacle, and its range."""
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

    # -- stall detection ------------------------------------------------------

    def _note_progress(self, dist: float) -> bool:
        """Stalled = has not beaten its best distance-to-goal in a while.

        The previous version compared distance now against distance one window
        ago. An oscillating drone defeats that completely: swinging back and
        forth changes the distance by more than the threshold every window, so
        it reads as progress while the drone goes nowhere. Requiring a NEW BEST
        cannot be faked by oscillation -- only by actually getting closer.
        """
        if dist < self._best_dist - self.g.stall_progress:
            self._best_dist = dist
            self._best_t = self._t
        return (self._t - self._best_t) > self.g.stall_window

    def _goal_visible(self, ranges: dict, yaw: float, to_goal: np.ndarray, dist: float) -> bool:
        """Local leave heuristic, not proof of visibility through blind wedges."""
        R = rot(yaw)
        unit = to_goal / max(dist, 1e-9)
        for name, d in ranges.items():
            if name not in BEAM_DIRS_BODY or d is None or d <= 0:
                continue
            world_dir = R @ BEAM_DIRS_BODY[name]
            if float(world_dir @ unit) > 0.7 and d < min(dist, self.g.d_influence):
                return False
        return True

    # -- main entry point -----------------------------------------------------

    def step(self, ranges: dict, pos, yaw: float, dt: float, vel=None):
        """Returns (v_world (2,), yaw_rate, state).

        vel is the current world-frame velocity, used to oppose residual motion.
        """
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be finite and positive")
        self._t += dt
        raw_ranges = ranges
        _, raw_nearest = self._closest_beam_normal(ranges, yaw)
        ranges = self._filter_ranges(ranges)
        # A fresh close return must not wait for the median window to fill.
        ranges = dict(ranges)
        for name, distance in raw_ranges.items():
            if name in BEAM_DIRS_BODY and distance is not None and 0 < distance < self.g.d_panic:
                ranges[name] = distance
        pos = np.asarray(pos, dtype=float)
        to_goal = self.goal - pos
        dist = float(np.linalg.norm(to_goal))

        if dist < self.g.goal_tol:
            self.state = self.ARRIVED
            return np.zeros(2), 0.0, self.state

        rep = self._repulsion(ranges, yaw)
        normal, nearest = self._closest_beam_normal(ranges, yaw)
        normal_raw = None if normal is None else normal.copy()
        obstacle_nearest = nearest
        wall_lost = False

        if self.state == self.ESCAPE and self._normal_filt is not None:
            # Keep following the same boundary when a corner leaves a beam.
            # Switching to the opposite wall reverses the tangent and traps
            # the drone between alternating obstacles.
            R = rot(yaw)
            candidates = [(float(d), R @ BEAM_DIRS_BODY[name])
                          for name, d in ranges.items()
                          if name in BEAM_DIRS_BODY and d is not None and 0 < d < self.g.d_influence
                          and (float((R @ BEAM_DIRS_BODY[name]) @ self._normal_filt) > 0.5
                               or (d < self.g.wall_target + 0.15
                                   and float((R @ BEAM_DIRS_BODY[name]) @ self._normal_filt) > -0.2))]
            if candidates:
                nearest, normal = min(candidates, key=lambda item: item[0])
            else:
                normal = self._normal_filt.copy()
                wall_lost = True

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
                    # Prefer the side with room to move. Goal alignment alone
                    # selects the dead end beside a wall attached to the room.
                    R = rot(yaw)
                    along = max(BEAM_DIRS_BODY, key=lambda name:
                                float((R @ BEAM_DIRS_BODY[name]) @ tangent))
                    against = max(BEAM_DIRS_BODY, key=lambda name:
                                  float((R @ BEAM_DIRS_BODY[name]) @ -tangent))
                    plus = ranges.get(along) or BEAM_MAX_RANGE
                    minus = ranges.get(against) or BEAM_MAX_RANGE
                    if abs(plus - minus) > self.g.wall_target:
                        self._escape_sign = 1.0 if plus > minus else -1.0
                    else:
                        self._escape_sign = 1.0 if float(tangent @ to_goal) > 0 else -1.0
                # Anti-cycling. Leaving escape on line-of-sight alone lets the
                # drone round part of an obstacle, see the goal, hand back to
                # SEEK, and get dragged straight into the same local minimum --
                # an endless loop. Re-entering escape near where we last
                # entered it is the signature, so each repeat doubles the
                # required dwell until the drone commits far enough round to
                # actually clear the obstacle.
                if (self._escape_entry_pos is not None
                        and float(np.linalg.norm(pos - self._escape_entry_pos)) < 0.60):
                    self._dwell_mult = min(self._dwell_mult * 2.0, 16.0)
                else:
                    self._dwell_mult = 1.0
                self._escape_entry_pos = pos.copy()
                self._escape_entry_dist = dist
                self._escape_t0 = self._t
                self.state = self.ESCAPE
                self._best_t = self._t

        elif self.state == self.ESCAPE:
            # Leave as soon as the goal is actually reachable. The textbook
            # Bug2 rule also demands being closer than the hit point, but that
            # is unsatisfiable if the drone rounded the obstacle the long way:
            # it ends up further out, having earned a clear shot at the goal,
            # and refuses to take it. A minimum dwell time prevents the
            # seek/escape thrash that the distance test was there to stop.
            dwell = self._t - self._escape_t0
            required = self.g.min_escape_time * self._dwell_mult
            if dwell > required and self._goal_visible(ranges, yaw, to_goal, dist):
                self.state = self.SEEK
                self._last_escape_end = self._t
                self._best_dist = dist      # fresh start for the new leg
                self._best_t = self._t

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
            # Turn decisively toward the last boundary at a convex corner;
            # continuing straight would attach us to an unrelated room wall.
            correction = 2.0 if wall_lost else self.g.k_wall * error
            v = tangent + normal * correction

        # Panic is an additive bias, not a mode. Overriding the command
        # outright would cancel the tangential term and stop the drone from
        # sliding out along a boundary.
        #
        # Ramp it in CONTINUOUSLY. A hard switch at d_panic is a relay: with
        # roughly half a second of loop and sensor lag, the drone crosses the
        # boundary, gets a full-strength kick, crosses back out, loses it
        # entirely, drifts in again -- a textbook limit cycle that reads as
        # violent overcorrection. Scaling from 0 at the boundary to 3x at
        # contact removes the discontinuity.
        if obstacle_nearest < self.g.d_panic:
            depth = (self.g.d_panic - obstacle_nearest) / max(self.g.d_panic, 1e-6)
            v = v + rep * (3.0 * min(max(depth, 0.0), 1.0))

        n = float(np.linalg.norm(v))
        if n > 1e-9:
            taper = min(1.0, dist / (3.0 * self.g.goal_tol))
            # Slow closing motion without throttling tangential wall-following.
            if obstacle_nearest < self.g.d_influence and normal_raw is not None:
                approach = float((v / n) @ normal_raw)   # +1 = straight at it
                if approach > 0.0:
                    span = max(self.g.d_influence - self.g.d_panic, 1e-6)
                    prox = float(np.clip((obstacle_nearest - self.g.d_panic) / span,
                                         self.g.min_speed_frac, 1.0))
                    taper *= (1.0 - approach) + approach * prox
            # Preserve small residual fields near equilibrium. Normalizing
            # every nonzero field to cruise speed turns sensor noise into
            # full-speed forward/backward reversals.
            v = v / max(n, 1.0) * self.g.v_max * taper

        # Oppose measured residual velocity to reduce overshoot.
        if vel is not None and self.g.k_damp > 0.0:
            v = v - self.g.k_damp * np.asarray(vel, dtype=float)
            n2 = float(np.linalg.norm(v))
            if n2 > self.g.v_max:
                v = v / n2 * self.g.v_max
        v = self._apply_axis_bias(v, yaw)

        # First-order filter on the output. Mode switches and beam handover
        # both step the command discontinuously; unsmoothed, the drone snaps
        # between headings and looks erratic.
        previous = np.zeros(2) if self._v_prev is None else self._v_prev
        emergency = min(raw_nearest, obstacle_nearest) < self.g.d_panic
        if not emergency:
            # cmd_smooth is the blend at the nominal 15 Hz flight rate.
            # Use elapsed time so radio/loop jitter does not change the filter.
            alpha = 1.0 - (1.0 - self.g.cmd_smooth) ** (dt * 15.0)
            v = (1.0 - alpha) * previous + alpha * v
            change = v - previous
            change_norm = float(np.linalg.norm(change))
            limit = self.g.cmd_accel * dt
            if change_norm > limit:
                v = previous + change * (limit / change_norm)
        # Smoothing must not carry a closing command into the panic band.
        # Bound each measured body-axis component independently, preserving
        # tangential motion. This is a local bound, not a blind-wedge guarantee.
        if self.g.brake_time > 0:
            R = rot(yaw)
            for name in BEAM_DIRS_BODY:
                readings = [d for d in (raw_ranges.get(name), ranges.get(name))
                            if d is not None and math.isfinite(d) and d > 0]
                if not readings:
                    continue
                direction = R @ BEAM_DIRS_BODY[name]
                allowed = max(0.0, (min(readings) - self.g.d_panic) / self.g.brake_time)
                closing = float(v @ direction)
                if closing > allowed:
                    v -= (closing - allowed) * direction
        # Urgent corrections and the closing-speed bound take priority over
        # comfort smoothing, so these can exceed the ordinary slew limit.
        self._v_prev = v.copy()

        # The sweep covers blind wedges in transit, but while wall-following it
        # keeps handing the wall to a different beam and destabilises the
        # normal. Hold heading instead -- the wall is already in view.
        yaw_cmd = 0.0 if self.state == self.ESCAPE else self.g.yaw_rate
        return v, yaw_cmd, self.state


# ----------------------------------------------------------------------------
# 2. SIMULATOR
# ----------------------------------------------------------------------------


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

    def clearance(self, p) -> float:
        """True centre-to-surface distance, including the room boundary."""
        p = np.asarray(p, dtype=float)
        boundary = float(min(np.min(p - self.bounds_lo), np.min(self.bounds_hi - p)))
        return min([boundary] + [float(np.linalg.norm(np.maximum(
            np.maximum(r.lo - p, p - r.hi), 0.0))) for r in self.rects])

    def segment_clearance(self, start, end) -> float:
        """Minimum clearance over a whole integration step (no tunnelling)."""
        start, end = np.asarray(start), np.asarray(end)
        delta = end - start
        length = float(np.linalg.norm(delta))
        best = min(self.clearance(start), self.clearance(end))
        if length < 1e-12:
            return best
        for rect in self.rects:
            if _ray_rect(start, delta / length, rect) <= length:
                return 0.0
            corners = np.array([rect.lo, rect.hi,
                                [rect.lo[0], rect.hi[1]], [rect.hi[0], rect.lo[1]]])
            fractions = np.clip((corners - start) @ delta / length**2, 0, 1)
            distances = np.linalg.norm(corners - (start + fractions[:, None] * delta), axis=1)
            best = min(best, float(distances.min()))
        return best


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
    half = math.radians(BEAM_FOV_DEG * 0.5)
    offsets = np.linspace(-half, half, rays_per_beam)
    rects = world.all_rects()
    angles = np.array([math.atan2(d[1], d[0]) for d in BEAM_DIRS_BODY.values()])
    angles = (angles[:, None] + yaw + offsets).reshape(-1)
    directions = np.stack((np.cos(angles), np.sin(angles)), axis=-1)[:, None, :]
    lo = np.array([r.lo for r in rects])[None, :, :] - pos
    hi = np.array([r.hi for r in rects])[None, :, :] - pos
    parallel = np.abs(directions) < 1e-12
    safe = np.where(parallel, 1.0, directions)
    a, b = lo / safe, hi / safe
    near = np.where(parallel, -np.inf, np.minimum(a, b))
    far = np.where(parallel, np.inf, np.maximum(a, b))
    enter = np.maximum(0.0, near.max(axis=-1))
    leave = far.min(axis=-1)
    miss = np.any(parallel & ((lo > 0) | (hi < 0)), axis=-1) | (enter > leave)
    hits = np.where(miss, BEAM_MAX_RANGE, np.minimum(enter, BEAM_MAX_RANGE))
    distances = hits.min(axis=1).reshape(4, rays_per_beam).min(axis=1)
    return dict(zip(BEAM_DIRS_BODY, map(float, distances)))


def simulate(world: SimWorld, start, goal, gains: Gains | None = None,
             dt: float = 0.05, t_limit: float = 120.0, tau: float = 0.25,
             drone_radius: float = 0.09, sensor_delay: float = 0.0,
             initial_yaw: float = 0.0):
    """Run the controller against the simulated world.

    Velocity is tracked through a first-order lag, so gains that look fine
    against an ideal integrator but oscillate on real hardware also oscillate
    here.
    """
    if dt <= 0 or t_limit <= 0 or tau < 0 or drone_radius < 0 or sensor_delay < 0:
        raise ValueError("dt/t_limit must be positive; tau/radius/delay must be nonnegative")
    ctrl = ReactiveController(goal, gains)
    pos = np.asarray(start, dtype=float).copy()
    vel = np.zeros(2)
    yaw = initial_yaw
    sensor_queue = deque(maxlen=int(math.ceil(sensor_delay / dt)) + 1)
    log = {"t": [], "pos": [], "state": [], "dist": [], "nearest": [], "clearance": []}
    t = 0.0
    collided = False
    step_clearance = world.clearance(pos) - drone_radius

    while t < t_limit:
        ranges = simulate_ranger(world, pos, yaw)
        sensor_queue.append((ranges, yaw))
        sensed_ranges, sensed_yaw = sensor_queue[0]
        v_cmd, yaw_rate, state = ctrl.step(sensed_ranges, pos, sensed_yaw, dt, vel=vel)

        log["t"].append(t)
        log["pos"].append(pos.copy())
        log["state"].append(state)
        log["dist"].append(float(np.linalg.norm(ctrl.goal - pos)))
        log["nearest"].append(min(ranges.values()))
        log["clearance"].append(step_clearance)

        if log["clearance"][-1] <= 0:
            collided = True
            break

        if state == ReactiveController.ARRIVED:
            break

        vel += (v_cmd - vel) * (1.0 - math.exp(-dt / tau) if tau else 1.0)
        next_pos = pos + vel * dt
        step_clearance = world.segment_clearance(pos, next_pos) - drone_radius
        pos = next_pos
        yaw = (yaw + yaw_rate * dt) % (2 * math.pi)
        t += dt

    # Include the final integrated step even when it lands on the time limit.
    if step_clearance <= 0:
        collided = True

    log["pos"] = np.array(log["pos"])
    log["t"] = np.array(log["t"])
    log["dist"] = np.array(log["dist"])
    log["nearest"] = np.array(log["nearest"])
    log["clearance"] = np.array(log["clearance"])
    log["min_clearance"] = min(float(log["clearance"].min()), step_clearance)
    log["collided"] = collided
    log["arrived"] = ctrl.state == ReactiveController.ARRIVED and not collided
    log["duration"] = t
    log["escape_fraction"] = (
        sum(1 for s in log["state"] if s == ReactiveController.ESCAPE)
        / max(len(log["state"]), 1)
    )
    return log


# ----------------------------------------------------------------------------
# 3. SCENARIOS
# ----------------------------------------------------------------------------


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
    """Detour around the closed side of a U-shaped obstacle."""
    w = SimWorld([0, 0], [5, 4], rects=[
        Rect([2.6, 1.0], [2.9, 3.0]),
        Rect([2.6, 1.0], [3.9, 1.3]),
        Rect([2.6, 2.7], [3.9, 3.0]),
    ])
    return "trap", w, np.array([0.7, 2.0]), np.array([4.5, 2.0])


def scenario_pocket():
    """Start inside the U; escape requires initially moving away from the goal."""
    _, w, _, _ = scenario_trap()
    return "pocket", w, np.array([3.5, 2.0]), np.array([1.0, 2.0])


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
    "pocket": scenario_pocket,
}


# ----------------------------------------------------------------------------
# 4. PLOTTING
# ----------------------------------------------------------------------------


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
        ax2.plot(log["t"], log["clearance"], color="#e37400", lw=0.9, label="propeller clearance")
        if esc.any():
            ax2.fill_between(log["t"], 0, log["dist"].max(), where=esc,
                             color="#e37400", alpha=0.12, step="mid")
        ax2.axhline(0.0, color="#c5221f", ls=":", lw=0.9)
        ax2.set_xlabel("t [s]"); ax2.set_ylabel("[m]")
        ax2.grid(alpha=0.25)
        if col == 0:
            ax2.legend(fontsize=8)

    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=140)
        print(f"Figure written to {save}")
    else:
        plt.show()


# ----------------------------------------------------------------------------
# 5. REAL FLIGHT
# ----------------------------------------------------------------------------


def wrap_pi(a: float) -> float:
    """Wrap an angle to [-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def fly(goal_xy, uri: str, height: float = 0.45, gains: Gains | None = None,
        rate_hz: float = 15.0, t_limit: float = 90.0, diag: bool = False):
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

    gains = gains or Gains.flight()
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
        est = {"x": 0.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "yaw": 0.0}
        lg = LogConfig(name="kalman", period_in_ms=50)
        lg.add_variable("kalman.stateX", "float")
        lg.add_variable("kalman.stateY", "float")
        lg.add_variable("kalman.statePX", "float")   # world-frame velocity,
        lg.add_variable("kalman.statePY", "float")   # needed for damping
        lg.add_variable("stabilizer.yaw", "float")

        def _on_data(_ts, data, _cfg):
            est["x"] = data["kalman.stateX"]
            est["y"] = data["kalman.stateY"]
            est["vx"] = data["kalman.statePX"]
            est["vy"] = data["kalman.statePY"]
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
                yaw0 = est["yaw"]          # heading to hold for the whole flight
                t = 0.0
                last_state = None
                flight_start = time.monotonic()
                previous_tick = flight_start - dt
                print(f"  origin ({origin[0]:.2f}, {origin[1]:.2f})  "
                      f"yaw0 {math.degrees(yaw0):.0f} deg")

                while t < t_limit:
                    loop_start = time.monotonic()
                    step_dt = loop_start - previous_tick
                    previous_tick = loop_start
                    ranges = {
                        "front": mr.front, "back": mr.back,
                        "left": mr.left, "right": mr.right,
                    }
                    if mr.up is not None and mr.up < 0.30:
                        print("Obstacle overhead -- landing.")
                        break

                    pos = np.array([est["x"], est["y"]]) - origin
                    yaw = est["yaw"]
                    vel_world = np.array([est["vx"], est["vy"]])
                    v_world, yaw_rate, state = ctrl.step(ranges, pos, yaw, step_dt,
                                                         vel=vel_world)

                    if state != last_state:
                        print(f"  t={t:5.1f}s  {state}   pos=({pos[0]:.2f},{pos[1]:.2f})")
                        last_state = state
                    if state == ReactiveController.ARRIVED:
                        print("Goal reached.")
                        break

                    # Hold the estimated takeoff heading. This cannot correct
                    # unobserved gyro bias; it uses the same yaw estimator.
                    if gains is None or gains.yaw_rate == 0.0:
                        yaw_err = wrap_pi(yaw0 - yaw)
                        yaw_rate = float(np.clip(2.0 * yaw_err, -1.0, 1.0))
                    else:
                        yaw_err = 0.0

                    # World -> body frame for MotionCommander.
                    v_body = rot(-yaw) @ v_world

                    if diag:
                        print(f"  t={t:5.1f} {state:6s} pos=({pos[0]:+.2f},{pos[1]:+.2f}) "
                              f"yaw={math.degrees(yaw):+6.1f} err={math.degrees(yaw_err):+5.1f} "
                              f"vW=({v_world[0]:+.2f},{v_world[1]:+.2f}) "
                              f"vB=({v_body[0]:+.2f},{v_body[1]:+.2f}) "
                              f"act=({vel_world[0]:+.2f},{vel_world[1]:+.2f}) "
                              f"F={ranges['front'] if ranges['front'] else -1:.2f}")

                    mc.start_linear_motion(float(v_body[0]), float(v_body[1]), 0.0,
                                           rate_yaw=math.degrees(yaw_rate))

                    # Sleep the REMAINDER of the period, not a full dt. Sleeping
                    # dt after doing the work makes the true period dt plus the
                    # radio round trip, so a nominal 10 Hz loop actually runs
                    # nearer 7 Hz -- and every millisecond of lag feeds the
                    # overshoot.
                    elapsed = time.monotonic() - loop_start
                    time.sleep(max(0.0, dt - elapsed))
                    t = time.monotonic() - flight_start

                mc.stop()
        except Exception as exc:
            print(f"\nERROR in flight loop: {exc}", file=sys.stderr)
            print("If airborne, kill power at the battery.", file=sys.stderr)
            return 1
        finally:
            lg.stop()
    print("Done.")
    return 0


# ----------------------------------------------------------------------------
# 6. ENTRY POINT
# ----------------------------------------------------------------------------


def stress(gains: Gains, trials: int = 150, seed: int = 7, t_limit: float = 120.0):
    """Randomized layouts. Four hand-built scenarios prove almost nothing;
    this is what tells you whether a gain change actually helped."""
    if trials < 1:
        raise ValueError("trials must be positive")
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
        if w.clearance(s) <= 0.09 or w.clearance(g) <= 0.09:
            continue
        done += 1
        log = simulate(w, s, g, gains, t_limit=t_limit)
        key = "reached" if log["arrived"] else ("collided" if log["collided"] else "timeout")
        res[key] += 1
        clearances.append(log["min_clearance"])
        if log["arrived"]:
            durations.append(log["duration"])

    print(f"{trials} randomized layouts (seed {seed}):")
    for k, v in res.items():
        print(f"  {k:9s} {v:4d}  ({100 * v / trials:.0f}%)")
    print(f"  clearance   5th pct {np.percentile(clearances, 5):.2f} m, "
          f"worst {min(clearances):.2f} m")
    if durations:
        print(f"  time        median {np.median(durations):.0f} s")
    print("\n  Clearance includes a 0.09 m drone radius and the full motion segment.")
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
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-yaw-sweep", action="store_true",
                    help="force the blind-wedge sweep off (already off with --fly)")
    ap.add_argument("--yaw-sweep", type=float, default=None, metavar="RAD_S",
                    help="re-enable the sweep at this rate; causes spiralling on "
                         "hardware, so leave it off unless you are debugging")
    ap.add_argument("--profile", choices=["sim", "flight"], default=None,
                    help="gain set. Defaults to flight with --fly, sim otherwise")
    # Field-tuning overrides. The spinning/erratic failure mode only appears on
    # real hardware, so it cannot be tuned out in simulation -- these exist so
    # you can adjust at the drone without editing the file.
    ap.add_argument("--v-max", type=float, default=None,
                    help="speed cap [m/s]. Lower = calmer")
    ap.add_argument("--d-influence", type=float, default=None,
                    help="obstacle influence radius [m]. Higher = reacts sooner")
    ap.add_argument("--d-panic", type=float, default=None,
                    help="hard-stop band [m]. Higher = keeps more distance")
    ap.add_argument("--k-repel", type=float, default=None,
                    help="repulsion strength. Higher = pushes away harder")
    ap.add_argument("--cmd-smooth", type=float, default=None,
                    help="0-1 output filter. Lower = smoother but laggier")
    ap.add_argument("--k-damp", type=float, default=None,
                    help="velocity damping. Raise if it overshoots and drifts")
    ap.add_argument("--rate", type=float, default=15.0, metavar="HZ",
                    help="control loop rate. Higher = less lag = less overshoot")
    ap.add_argument("--diag", action="store_true",
                    help="print pos, yaw, yaw error and commands every tick")
    ap.add_argument("--straight", action="store_true",
                    help="BISECTION TEST: disable obstacle avoidance entirely and "
                         "fly straight to the goal. If this still curves, the fault "
                         "is in position/yaw estimation, not the nav algorithm. "
                         "It will NOT avoid anything -- use open space only")
    args = ap.parse_args(argv)

    profile = args.profile or ("flight" if args.fly else "sim")
    gains = Gains.flight() if profile == "flight" else Gains()

    for attr, value in [("v_max", args.v_max), ("d_influence", args.d_influence),
                        ("d_panic", args.d_panic), ("k_repel", args.k_repel),
                        ("cmd_smooth", args.cmd_smooth), ("k_damp", args.k_damp)]:
        if value is not None:
            setattr(gains, attr, value)
    if args.yaw_sweep is not None:
        gains.yaw_rate = args.yaw_sweep
    if args.no_yaw_sweep:
        gains.yaw_rate = 0.0
    if args.straight:
        gains.k_repel = 0.0
        gains.d_influence = 0.01
        gains.yaw_rate = 0.0

    if args.fly:
        print("=" * 60)
        print(" MODE: FLIGHT -- this will connect to a real Crazyflie")
        print(f"   uri    {args.uri}")
        print(f"   goal   {args.goal[0]:+.2f}, {args.goal[1]:+.2f} m "
              f"(displacement from takeoff, not room coordinates)")
        print(f"   height {args.height:.2f} m")
        print(f"   profile {profile}: v_max {gains.v_max:.2f} m/s, "
              f"influence {gains.d_influence:.2f} m, panic {gains.d_panic:.2f} m")
        print(f"   yaw sweep {'OFF' if gains.yaw_rate == 0 else f'{gains.yaw_rate:.2f} rad/s'}"
              f", smoothing {gains.cmd_smooth:.2f}")
        print(" No plot is produced in this mode. If a plot window opens,")
        print(" you are simulating -- check that --fly was actually passed.")
        print("=" * 60)
        if args.straight:
            print(" *** --straight: OBSTACLE AVOIDANCE IS DISABLED ***")
            print("     Open space only. This isolates estimation from the")
            print("     navigation algorithm.")
        return fly(args.goal, args.uri, args.height, gains,
                   rate_hz=args.rate, diag=args.diag)

    print("=" * 60)
    print(" MODE: SIMULATION -- no hardware is touched, no radio opened")
    print(" To fly a real Crazyflie, add:  --fly --uri radio://0/80/2M")
    print("=" * 60)

    if args.stress:
        stress(gains, trials=args.trials, seed=args.seed)
        return 0

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    runs = []
    for nm in names:
        label, world, start, goal = SCENARIOS[nm]()
        log = simulate(world, start, goal, gains)
        verdict = "reached" if log["arrived"] else ("COLLIDED" if log["collided"] else "timeout")
        print(f"{label:8s} {verdict:9s} {log['duration']:5.1f} s  "
              f"escape {log['escape_fraction'] * 100:4.1f}%  "
              f"min propeller clearance {log['min_clearance']:.2f} m")
        runs.append((label, world, start, goal, log))

    if not args.no_plot:
        plot_runs(runs, save=args.save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
