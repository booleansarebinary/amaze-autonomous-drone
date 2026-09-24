"""Hold station at the centre of a hand-held hula hoop (Crazyflie 2.x).

Hardware
    Crazyflie 2.x + Flow deck v2 (underneath) + Multi-ranger deck (on top).

How it works
    Hold the hoop HORIZONTALLY at the drone's hover height so the drone sits
    inside it. The four horizontal Multi-ranger beams then each hit the rim,
    and for a circle of radius R with the drone offset (x, y) from the centre:

        d_front = sqrt(R^2 - y^2) - x      d_back  = sqrt(R^2 - y^2) + x
        d_left  = sqrt(R^2 - x^2) - y      d_right = sqrt(R^2 - x^2) + y

    so the offset is half the difference of opposing beams:

        x = (d_back - d_front) / 2         y = (d_right - d_left) / 2

    That is exact and does not depend on R. It also comes out in the BODY
    frame, which is what MotionCommander.start_linear_motion wants, so yaw
    never enters the control path and neither does absolute position -- no
    Lighthouse, no Loco, and Flow deck drift does not matter.

    R is still used as a consistency check: an opposing pair spans the chord
    through the drone, so d_front + d_back must equal 2*sqrt(R^2 - y^2). When
    it does not, one of those beams is looking at an arm or through a gap at
    the wall, and it is dropped in favour of the other beam.

Usage
    python hoop_hover.py sim --profile sway         simulate and plot
    python hoop_hover.py sweep                      how fast can the hoop move
    python hoop_hover.py fly --calibrate            fly it (props off first!)
    pytest                                          run the tests

See README.md for the flight checklist and tuning notes.
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np

__all__ = [
    "BEAMS",
    "Gains",
    "HoopFollower",
    "SimConfig",
    "offset_from_opposing",
    "rot",
    "simulate",
    "sweep",
]

log = logging.getLogger("hoop_hover")

#: Multi-ranger horizontal beams, in the order (+x, -x, +y, -y).
BEAMS: tuple[str, str, str, str] = ("front", "back", "left", "right")

#: Body-frame unit vector each beam points along. +x forward, +y left.
BEAM_DIRS: dict[str, tuple[float, float]] = {
    "front": (1.0, 0.0),
    "back": (-1.0, 0.0),
    "left": (0.0, 1.0),
    "right": (0.0, -1.0),
}

#: Refuse to take off below this, and land if it is reached in flight [V].
VBAT_PREFLIGHT_MIN = 3.50
VBAT_LAND = 3.10


def rot(theta: float) -> np.ndarray:
    """2D rotation matrix for `theta` radians, counter-clockwise."""
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s], [s, c]])


def offset_from_opposing(near: float, far: float) -> float:
    """Offset along an axis from its two opposing beam ranges.

    `near` points along +axis (front for x, left for y), `far` along -axis.
    Exact for any circle, and independent of its radius.
    """
    return (far - near) / 2.0


# --------------------------------------------------------------- controller


@dataclass
class Gains:
    """Controller tuning. Every value is a metre, a second, or a rate."""

    hoop_radius: float = 0.45      # [m] 0.9 m hoop. `fly --calibrate` measures it
    kp: float = 2.4                # [1/s] command velocity per metre of offset
    kd: float = 0.30               # [s] damping on the offset rate
    ff_gain: float = 0.85          # fraction of estimated hoop velocity fed forward
    v_max: float = 0.80            # [m/s] command cap; below ~0.8 the drone cannot
                                   # keep up with a briskly moved hoop
    deadband: float = 0.025        # [m] offsets smaller than this are ignored
    ema_offset: float = 0.45       # offset low-pass (1 = no filtering)
    ema_rate: float = 0.25         # offset-derivative low-pass
    ema_hoop_vel: float = 0.20     # hoop-velocity estimate low-pass
    chord_tol: float = 0.16        # [m] chord-consistency tolerance
    max_offset: float = 0.95       # reject offsets beyond this fraction of R
    lost_hold: float = 2.5         # [s] hold still after losing the hoop, then give up
    search_timeout: float = 15.0   # [s] give up if the hoop is never seen

    def validate(self) -> None:
        """Raise ValueError on a combination that cannot fly."""
        if self.hoop_radius <= 0.05:
            raise ValueError("hoop_radius must be a real hoop, in metres")
        if not 0.0 < self.v_max <= 1.5:
            raise ValueError("v_max must be in (0, 1.5] m/s")
        if self.kp <= 0.0:
            raise ValueError("kp must be positive")
        for name in ("ema_offset", "ema_rate", "ema_hoop_vel"):
            if not 0.0 < getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.deadband >= self.hoop_radius:
            raise ValueError("deadband is larger than the hoop")


class HoopFollower:
    """Estimates the drone's offset from the hoop centre and drives it to zero.

    The controller is pure: `step` takes ranges and returns a body-frame
    velocity, so it runs identically against the simulator and the radio.
    """

    SEARCH = "search"     # has never seen the hoop
    TRACK = "track"       # holding the centre
    LOST = "lost"         # had it, lost it, holding still
    GIVEUP = "giveup"     # lost for too long; the caller should land

    def __init__(self, gains: Gains | None = None) -> None:
        self.g = gains or Gains()
        self.g.validate()
        self.state: str = self.SEARCH
        self.offset = np.zeros(2)      # filtered offset, body frame [m]
        self.rate = np.zeros(2)        # filtered d(offset)/dt [m/s]
        self.hoop_vel = np.zeros(2)    # estimated hoop velocity, body frame [m/s]
        self.command = np.zeros(2)     # last command issued [m/s]
        self.confidence = 0.0
        self.radius_est: float | None = None
        self._lost_t = 0.0
        self._elapsed = 0.0
        self._seen = False

    # -- estimation

    def _gate(self, d: float | None) -> float | None:
        """Drop readings that cannot be a rim hit seen from inside the hoop."""
        if d is None:
            return None
        if d < 0.03 or d > 2.2 * self.g.hoop_radius:
            return None
        return float(d)

    def _half_chord(self, other_axis: float) -> float:
        """Half the chord across the hoop at an offset of `other_axis`."""
        R = self.g.hoop_radius
        return math.sqrt(max(R * R - other_axis * other_axis, 0.0))

    def _axis(self, near: float | None, far: float | None,
              other_axis: float) -> tuple[float | None, float | None]:
        """Offset along one axis. Returns (value, chord) with chord None when
        only one beam contributed."""
        if near is not None and far is not None:
            return offset_from_opposing(near, far), near + far
        if near is not None:
            return self._half_chord(other_axis) - near, None
        if far is not None:
            return far - self._half_chord(other_axis), None
        return None, None

    def estimate(self, ranges: Mapping[str, float | None]) -> tuple[np.ndarray | None, float]:
        """Offset from the hoop centre, body frame, plus a 0..1 confidence.

        Returns (None, 0.0) when the readings cannot describe a hoop around
        the drone -- the caller should hold position rather than guess.
        """
        d = {b: self._gate(ranges.get(b)) for b in BEAMS}
        prev = self.offset

        x, chord_x = self._axis(d["front"], d["back"], prev[1])
        y, chord_y = self._axis(d["left"], d["right"], prev[0])
        if x is None or y is None:
            return None, 0.0

        # Validate each opposing pair against the chord it should span. On a
        # mismatch one beam is seeing something nearer than the rim -- an arm,
        # the person holding the hoop -- so trust the FARTHER beam, which is
        # the one still reaching the rim, and fall back to a single-beam
        # estimate on that axis.
        conf = 0.0
        if chord_x is not None:
            if abs(chord_x - 2.0 * self._half_chord(y)) < self.g.chord_tol:
                conf += 0.5
            else:
                near, far = d["front"], d["back"]
                x = (self._half_chord(y) - near if near >= far
                     else far - self._half_chord(y))
                chord_x = None
        if chord_y is not None:
            if abs(chord_y - 2.0 * self._half_chord(x)) < self.g.chord_tol:
                conf += 0.5
            else:
                near, far = d["left"], d["right"]
                y = (self._half_chord(x) - near if near >= far
                     else far - self._half_chord(x))
                chord_y = None

        off = np.array([x, y], dtype=float)
        if float(np.linalg.norm(off)) > self.g.max_offset * self.g.hoop_radius:
            return None, 0.0

        # With both pairs intact the hoop's own radius falls out. Used by
        # `fly --calibrate` and as a second opinion on the configured radius.
        if chord_x is not None and chord_y is not None:
            self.radius_est = 0.5 * (math.hypot(chord_x / 2.0, y)
                                     + math.hypot(chord_y / 2.0, x))
        return off, max(conf, 0.25)

    # -- control

    def step(self, ranges: Mapping[str, float | None], dt: float,
             drone_vel_body: Sequence[float] | None = None) -> tuple[np.ndarray, str]:
        """Advance one control tick.

        Args:
            ranges: metres per beam, None where the sensor saw nothing.
            dt: seconds since the previous call. Measure it, do not assume it.
            drone_vel_body: the drone's own velocity in the body frame, from
                the state estimator. Supplying it turns on hoop-velocity
                feedforward, which is what removes the lag behind a moving
                hoop; pass None to disable.

        Returns:
            (velocity command in the body frame [m/s], state).
        """
        g = self.g
        dt = max(float(dt), 1e-3)
        self._elapsed += dt
        raw, conf = self.estimate(ranges)
        self.confidence = conf

        if raw is None:
            if self._seen:
                self._lost_t += dt
                self.state = self.GIVEUP if self._lost_t > g.lost_hold else self.LOST
            elif self._elapsed > g.search_timeout:
                self.state = self.GIVEUP
            # Hold still rather than guess. A hoop we cannot see is a hoop we
            # cannot chase, and drifting blind is how a rim gets clipped.
            self.command = np.zeros(2)
            return self.command, self.state

        first_fix = not self._seen
        self._seen = True
        self._lost_t = 0.0
        self.state = self.TRACK

        if first_fix:
            # Snap on the first fix; easing in from zero would command a large
            # bogus velocity while the filter caught up.
            self.offset = raw.copy()
            self.rate[:] = 0.0
        else:
            alpha = g.ema_offset * min(1.0, conf + 0.4)
            previous = self.offset.copy()
            self.offset = (1.0 - alpha) * self.offset + alpha * raw
            # Differentiate the FILTERED offset so ranger noise does not
            # dominate the derivative term.
            self.rate = ((1.0 - g.ema_rate) * self.rate
                         + g.ema_rate * (self.offset - previous) / dt)

        # offset = drone - hoop, so hoop_vel = drone_vel - d(offset)/dt.
        if drone_vel_body is not None:
            measured = np.asarray(drone_vel_body, dtype=float) - self.rate
            self.hoop_vel = ((1.0 - g.ema_hoop_vel) * self.hoop_vel
                             + g.ema_hoop_vel * measured)
        else:
            self.hoop_vel = np.zeros(2)

        err = self.offset
        if float(np.linalg.norm(err)) < g.deadband:
            err = np.zeros(2)

        v = -g.kp * err - g.kd * self.rate + g.ff_gain * self.hoop_vel
        speed = float(np.linalg.norm(v))
        if speed > g.v_max:
            v = v / speed * g.v_max
        self.command = v
        return v, self.state

    def telemetry(self) -> dict[str, float | str]:
        """Flat dict for CSV logging and the Open MCT feed."""
        return {
            "state": self.state,
            "confidence": round(self.confidence, 3),
            "offset_x": round(float(self.offset[0]), 4),
            "offset_y": round(float(self.offset[1]), 4),
            "rate_x": round(float(self.rate[0]), 4),
            "rate_y": round(float(self.rate[1]), 4),
            "hoop_vel_x": round(float(self.hoop_vel[0]), 4),
            "hoop_vel_y": round(float(self.hoop_vel[1]), 4),
            "cmd_x": round(float(self.command[0]), 4),
            "cmd_y": round(float(self.command[1]), 4),
        }


# ---------------------------------------------------------------- simulator


@dataclass
class SimConfig:
    """Everything the simulator pretends to be wrong about the world."""

    radius: float = 0.45
    noise_frac: float = 0.02       # proportional ranger noise
    noise_abs: float = 0.005       # [m] noise floor
    dropout_base: float = 0.03     # dropout chance for a head-on rim hit
    dropout_grazing: float = 0.55  # extra chance as the hit angle goes oblique
    outlier_rate: float = 0.02     # chance a beam sees an arm instead of the rim
    latency_steps: int = 2         # command latency, radio plus logging
    tau: float = 0.22              # [s] velocity first-order lag
    background: float = 4.0        # [m] reading when a beam misses the hoop


def ray_circle(p: np.ndarray, u: np.ndarray, centre: np.ndarray,
               radius: float) -> float | None:
    """Distance from `p` along unit vector `u` to a circle, or None if it misses."""
    m = p - centre
    b = float(u @ m)
    disc = b * b - (float(m @ m) - radius * radius)
    if disc < 0.0:
        return None
    s = math.sqrt(disc)
    for t in sorted((-b - s, -b + s)):
        if t > 0.0:
            return t
    return None


def fake_ranges(rng: np.random.Generator, p: np.ndarray, yaw: float,
                centre: np.ndarray, cfg: SimConfig) -> dict[str, float | None]:
    """Simulate the four horizontal beams looking at a hoop rim."""
    out: dict[str, float | None] = {}
    for name in BEAMS:
        bx, by = BEAM_DIRS[name]
        u = rot(yaw) @ np.array([bx, by])
        t = ray_circle(p, u, centre, cfg.radius)
        if t is None:
            out[name] = cfg.background
            continue
        hit = p + t * u
        normal = (hit - centre) / max(float(np.linalg.norm(hit - centre)), 1e-9)
        cos_incidence = abs(float(u @ normal))
        # A thin glossy rim hit obliquely reflects the pulse away from the sensor.
        if rng.random() < cfg.dropout_base + cfg.dropout_grazing * (1.0 - cos_incidence):
            out[name] = None
            continue
        if rng.random() < cfg.outlier_rate:
            out[name] = float(rng.uniform(0.08, 0.35))  # an arm, a hand, a torso
            continue
        out[name] = float(t * (1.0 + rng.normal(0.0, cfg.noise_frac))
                          + rng.normal(0.0, cfg.noise_abs))
    return out


HoopPath = Callable[[float], np.ndarray]

#: Named hoop motions. Speeds are what a hand can plausibly do.
PROFILES: dict[str, HoopPath] = {
    "static": lambda t: np.array([0.0, 0.0]),
    "drift": lambda t: np.array([0.15 * t, 0.0]),
    "brisk": lambda t: np.array([0.35 * t, 0.0]),
    # 0.45 m/s peak: brisk, but a pace you can demo at.
    "sway": lambda t: np.array([0.10 * t, 0.29 * math.sin(2 * math.pi * 0.25 * t)]),
    # A shove. Much beyond the hoop radius and the drone is outside before it
    # can react, which it cannot recover from.
    "jump": lambda t: np.array([0.0 if t < 4.0 else 0.25, 0.0]),
}


def sinusoid(peak_speed: float, freq_hz: float = 0.25) -> HoopPath:
    """Side-to-side hoop motion with a given peak speed [m/s]."""
    amplitude = peak_speed / (2.0 * math.pi * freq_hz)
    return lambda t: np.array([0.0, amplitude * math.sin(2 * math.pi * freq_hz * t)])


def simulate(path: str | HoopPath = "sway", gains: Gains | None = None,
             cfg: SimConfig | None = None, *, feedforward: bool = True,
             dt: float = 0.05, t_end: float = 20.0, yaw: float = 0.6,
             seed: int = 3, settle: float = 2.0) -> dict:
    """Run the controller against the simulated hoop. Returns a log dict."""
    gains = gains or Gains()
    cfg = cfg or SimConfig()
    centre_at = PROFILES[path] if isinstance(path, str) else path
    label = path if isinstance(path, str) else "custom"

    rng = np.random.default_rng(seed)
    ctrl = HoopFollower(gains)
    p = centre_at(0.0) + np.array([0.06, -0.04])   # start slightly off-centre
    v = np.zeros(2)
    queue = [np.zeros(2)] * max(cfg.latency_steps, 1)

    rows: list[dict] = []
    t = 0.0
    while t < t_end:
        centre = centre_at(t)
        ranges = fake_ranges(rng, p, yaw, centre, cfg)
        v_body_measured = rot(-yaw) @ v
        v_cmd_body, state = ctrl.step(
            ranges, dt, v_body_measured if feedforward else None)

        rows.append({
            "t": t,
            "drone_x": p[0], "drone_y": p[1],
            "hoop_x": centre[0], "hoop_y": centre[1],
            "err": float(np.linalg.norm(p - centre)),
            **ctrl.telemetry(),
        })

        queue.append(rot(yaw) @ v_cmd_body)
        v += (queue.pop(0) - v) * (dt / cfg.tau)
        p = p + v * dt
        t += dt

    out: dict = {"rows": rows, "profile": label, "radius": cfg.radius}
    out["t"] = np.array([r["t"] for r in rows])
    out["pos"] = np.array([[r["drone_x"], r["drone_y"]] for r in rows])
    out["hoop"] = np.array([[r["hoop_x"], r["hoop_y"]] for r in rows])
    out["err"] = np.array([r["err"] for r in rows])
    out["state"] = [r["state"] for r in rows]
    settled = out["t"] > settle
    out["rms"] = float(np.sqrt(np.mean(out["err"][settled] ** 2)))
    out["max"] = float(out["err"][settled].max())
    out["valid_frac"] = float(np.mean([s == HoopFollower.TRACK for s in out["state"]]))
    out["escaped"] = bool(out["err"].max() > cfg.radius)
    return out


def write_csv(rows: Iterable[Mapping], path: Path) -> None:
    """Write simulator or flight rows to CSV."""
    rows = list(rows)
    if not rows:
        log.warning("nothing to write to %s", path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    log.info("wrote %d rows to %s", len(rows), path)


# ------------------------------------------------------------------ reports


def sweep(gains: Gains, cfg: SimConfig, *, trials: int = 3) -> list[dict]:
    """How fast can the hoop be moved before the drone falls out of it?"""
    print(f"Sinusoidal hoop motion at 0.25 Hz, R = {cfg.radius:.2f} m, "
          f"v_max = {gains.v_max:.2f} m/s")
    print(f"{'peak speed':>12} {'RMS':>8} {'worst':>9} {'tracked':>9}   verdict")
    results = []
    for peak in (0.20, 0.30, 0.45, 0.60, 0.75, 0.90):
        runs = [simulate(sinusoid(peak), gains, cfg, seed=s, t_end=16.0)
                for s in range(trials)]
        row = {
            "peak_speed": peak,
            "rms": float(np.mean([r["rms"] for r in runs])),
            "worst": max(r["max"] for r in runs),
            "valid_frac": float(np.mean([r["valid_frac"] for r in runs])),
            "escaped": any(r["escaped"] for r in runs),
        }
        results.append(row)
        print(f"{peak:9.2f} m/s {row['rms'] * 1000:6.0f} mm {row['worst'] * 1000:6.0f} mm "
              f"{row['valid_frac'] * 100:8.0f}%   "
              f"{'LOST THE HOOP' if row['escaped'] else 'holds centre'}")

    print("\nFeedforward on a steadily moving hoop (0.35 m/s):")
    for ff in (True, False):
        runs = [simulate("brisk", gains, cfg, feedforward=ff, seed=s) for s in range(5)]
        print(f"  {'with' if ff else 'without':>8} feedforward: "
              f"RMS {np.mean([r['rms'] for r in runs]) * 1000:5.0f} mm")
    return results


def plot(logs: Sequence[dict], save: str | None = None) -> None:
    """Trajectory and error plots. matplotlib is only imported here."""
    import matplotlib
    if save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, len(logs), figsize=(4.6 * len(logs), 7.2), squeeze=False)
    for col, entry in enumerate(logs):
        radius = entry["radius"]
        ax = axes[0][col]
        ax.plot(entry["hoop"][:, 0], entry["hoop"][:, 1], "-", lw=1.2,
                color="#8a8f98", label="hoop centre")
        ax.plot(entry["pos"][:, 0], entry["pos"][:, 1], "-", lw=1.4,
                color="#0b8043", label="drone")
        for i in (0, len(entry["t"]) // 2, len(entry["t"]) - 1):
            ax.add_patch(plt.Circle(entry["hoop"][i], radius, fill=False,
                                    color="#c5221f", lw=0.8, alpha=0.5))
        ax.set_aspect("equal")
        ax.grid(alpha=0.2)
        ax.set_title(f"{entry['profile']}: RMS {entry['rms'] * 1000:.0f} mm, "
                     f"max {entry['max'] * 1000:.0f} mm", fontsize=10)
        ax.set_xlabel("x [m]")
        if col == 0:
            ax.set_ylabel("y [m]")
            ax.legend(fontsize=8)

        ax2 = axes[1][col]
        ax2.plot(entry["t"], entry["err"] * 100, color="#1f77b4", lw=1.0)
        ax2.axhline(radius * 100, color="#c5221f", ls="--", lw=0.9)
        ax2.text(0.3, radius * 100 + 1, "rim", color="#c5221f", fontsize=8)
        ax2.set_ylim(0, radius * 100 + 10)
        ax2.set_xlabel("t [s]")
        ax2.set_ylabel("distance from centre [cm]")
        ax2.grid(alpha=0.25)
    fig.tight_layout()
    if save:
        fig.savefig(save, dpi=140)
        print(f"Figure written to {save}")
    else:
        plt.show()


# -------------------------------------------------------------- real flight


def _preflight(scf, gains: Gains) -> str | None:
    """Check the decks and the battery. Returns a reason to abort, or None."""
    for param, label in (("deck.bcFlow2", "Flow deck v2"),
                         ("deck.bcMultiranger", "Multi-ranger")):
        try:
            present = int(scf.cf.param.get_value(param, timeout=2.0))
        except Exception as exc:                       # noqa: BLE001 - report and abort
            # Unknown is not the same as present: never fly blind on this.
            return f"could not read {param} ({exc})"
        if not present:
            return f"{label} not detected"
        log.info("%s: detected", label)
    return None


def _read_battery(scf, timeout: float = 2.0) -> float | None:
    """One-shot battery voltage via a short log block, or None if unavailable."""
    from threading import Event

    from cflib.crazyflie.log import LogConfig

    got, holder = Event(), {}
    cfg = LogConfig(name="vbat", period_in_ms=100)
    cfg.add_variable("pm.vbat", "float")

    def _cb(_ts, data, _cfg):
        holder["v"] = data["pm.vbat"]
        got.set()

    try:
        scf.cf.log.add_config(cfg)
        cfg.data_received_cb.add_callback(_cb)
        cfg.start()
        got.wait(timeout)
        cfg.stop()
    except Exception:                                  # noqa: BLE001 - optional check
        return None
    return holder.get("v")


def calibrate_radius(mr, gains: Gains, samples: int = 60) -> float | None:
    """Measure the hoop radius. Hold the hoop steady around the grounded drone."""
    import time

    probe = HoopFollower(replace(gains, max_offset=0.99))
    seen: list[float] = []
    for _ in range(samples):
        probe.radius_est = None
        probe.estimate({b: getattr(mr, b) for b in BEAMS})
        if probe.radius_est:
            seen.append(probe.radius_est)
        time.sleep(0.05)
    if not seen:
        return None
    return float(np.median(seen))


def fly(uri: str, height: float, gains: Gains, *, rate_hz: float = 20.0,
        duration: float = 60.0, calibrate: bool = False, feedforward: bool = True,
        csv_path: Path | None = None, cache_dir: str = "./cache") -> int:
    """Fly the controller on a real Crazyflie. Returns a process exit code.

    NOT YET FLOWN ON HARDWARE. Run it with the propellers removed first and
    watch the printed offsets while someone moves the hoop around the drone.
    """
    try:
        import cflib.crtp
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.log import LogConfig
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
        from cflib.positioning.motion_commander import MotionCommander
        from cflib.utils.multiranger import Multiranger
    except ImportError:
        log.error("cflib is not installed:  pip install cflib")
        return 1

    import time

    gains.validate()
    ctrl = HoopFollower(gains)
    period = 1.0 / rate_hz
    rows: list[dict] = []

    cflib.crtp.init_drivers()
    log.info("connecting to %s", uri)
    try:
        with SyncCrazyflie(uri, cf=Crazyflie(rw_cache=cache_dir)) as scf:
            reason = _preflight(scf, gains)
            if reason:
                log.error("preflight failed: %s", reason)
                return 1

            vbat = _read_battery(scf)
            if vbat is None:
                log.warning("battery voltage unavailable; continuing")
            elif vbat < VBAT_PREFLIGHT_MIN:
                log.error("battery at %.2f V, below %.2f V. Charge it first.",
                          vbat, VBAT_PREFLIGHT_MIN)
                return 1
            else:
                log.info("battery %.2f V", vbat)

            # Body-frame velocity for the feedforward term, plus the battery.
            est = {"vx": 0.0, "vy": 0.0, "vbat": vbat or 4.0}
            telemetry = LogConfig(name="hoop", period_in_ms=50)
            telemetry.add_variable("stateEstimate.vx", "float")
            telemetry.add_variable("stateEstimate.vy", "float")
            telemetry.add_variable("stateEstimate.yaw", "float")
            telemetry.add_variable("pm.vbat", "float")

            def _on_data(_ts, data, _cfg):
                yaw = math.radians(data["stateEstimate.yaw"])
                world = np.array([data["stateEstimate.vx"], data["stateEstimate.vy"]])
                est["vx"], est["vy"] = rot(-yaw) @ world
                est["vbat"] = data["pm.vbat"]

            scf.cf.log.add_config(telemetry)
            telemetry.data_received_cb.add_callback(_on_data)
            telemetry.start()

            try:
                scf.cf.platform.send_arming_request(True)
                time.sleep(1.0)
            except AttributeError:
                pass  # firmware predates the arming API

            try:
                with Multiranger(scf) as mr:
                    if calibrate:
                        log.info("measuring hoop radius -- hold it steady and centred")
                        measured = calibrate_radius(mr, gains)
                        if measured:
                            gains.hoop_radius = measured
                            log.info("hoop radius %.3f m", measured)
                        else:
                            log.warning("no rim seen; keeping R = %.3f m",
                                        gains.hoop_radius)

                    with MotionCommander(scf, default_height=height) as mc:
                        time.sleep(2.0)
                        log.info("tracking -- hand above the drone to stop")
                        t, t_prev, last_state = 0.0, time.monotonic(), None
                        while t < duration:
                            if mr.up is not None and mr.up < 0.25:
                                log.info("hand overhead -- landing")
                                break
                            if est["vbat"] < VBAT_LAND:
                                log.warning("battery %.2f V -- landing", est["vbat"])
                                break

                            now = time.monotonic()
                            step_dt, t_prev = now - t_prev, now
                            ranges = {b: getattr(mr, b) for b in BEAMS}
                            v_body, state = ctrl.step(
                                ranges, step_dt,
                                (est["vx"], est["vy"]) if feedforward else None)

                            rows.append({"t": round(t, 3),
                                         **{b: ranges[b] for b in BEAMS},
                                         "vbat": round(est["vbat"], 2),
                                         **ctrl.telemetry()})
                            if state != last_state:
                                log.info("t=%5.1fs  %-7s offset=(%+.2f, %+.2f)",
                                         t, state, ctrl.offset[0], ctrl.offset[1])
                                last_state = state
                            if state == HoopFollower.GIVEUP:
                                log.warning("lost the hoop -- landing")
                                break

                            mc.start_linear_motion(float(v_body[0]), float(v_body[1]), 0.0)
                            time.sleep(period)
                            t += step_dt
                        mc.stop()
            except KeyboardInterrupt:
                # MotionCommander lands on the way out of its context manager.
                log.warning("interrupted -- landing")
            finally:
                telemetry.stop()
    except Exception as exc:                           # noqa: BLE001 - operator-facing
        log.error("flight aborted: %s", exc)
        log.error("If the Crazyflie is airborne, kill power at the battery.")
        return 1
    finally:
        if csv_path and rows:
            write_csv(rows, csv_path)

    log.info("done, %d control ticks", len(rows))
    return 0


# ------------------------------------------------------------------- the CLI


def _add_gain_args(parser: argparse.ArgumentParser) -> None:
    defaults = Gains()
    parser.add_argument("--radius", type=float, default=defaults.hoop_radius,
                        help="hoop radius [m] (default: %(default)s)")
    parser.add_argument("--kp", type=float, default=defaults.kp,
                        help="proportional gain [1/s] (default: %(default)s)")
    parser.add_argument("--kd", type=float, default=defaults.kd,
                        help="damping gain [s] (default: %(default)s)")
    parser.add_argument("--v-max", type=float, default=defaults.v_max,
                        help="speed cap [m/s] (default: %(default)s)")
    parser.add_argument("--no-feedforward", action="store_true",
                        help="disable hoop-velocity feedforward")


def _gains_from(args: argparse.Namespace) -> Gains:
    return Gains(hoop_radius=args.radius, kp=args.kp, kd=args.kd, v_max=args.v_max)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hoop_hover", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    sim = sub.add_parser("sim", help="simulate the controller")
    sim.add_argument("--profile", default="sway",
                     choices=list(PROFILES) + ["all"])
    sim.add_argument("--seed", type=int, default=3)
    sim.add_argument("--duration", type=float, default=20.0, help="[s]")
    sim.add_argument("--save", metavar="PNG", help="write the figure instead of showing it")
    sim.add_argument("--no-plot", action="store_true")
    sim.add_argument("--csv", type=Path, help="write the run to CSV")
    _add_gain_args(sim)

    swp = sub.add_parser("sweep", help="tracking accuracy against hoop speed")
    swp.add_argument("--trials", type=int, default=3)
    _add_gain_args(swp)

    flight = sub.add_parser("fly", help="fly it on a real Crazyflie")
    flight.add_argument("--uri", default="radio://0/80/2M/E7E7E7E7E7")
    flight.add_argument("--height", type=float, default=0.75, help="hover height [m]")
    flight.add_argument("--duration", type=float, default=60.0, help="[s]")
    flight.add_argument("--rate", type=float, default=20.0, help="control rate [Hz]")
    flight.add_argument("--calibrate", action="store_true",
                        help="measure the hoop radius before taking off")
    flight.add_argument("--csv", type=Path, help="write flight telemetry to CSV")
    flight.add_argument("--cache-dir", default="./cache", help=argparse.SUPPRESS)
    _add_gain_args(flight)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s", stream=sys.stdout)

    try:
        gains = _gains_from(args)
        gains.validate()
    except ValueError as exc:
        log.error("bad configuration: %s", exc)
        return 2

    if args.command == "fly":
        return fly(args.uri, args.height, gains, rate_hz=args.rate,
                   duration=args.duration, calibrate=args.calibrate,
                   feedforward=not args.no_feedforward, csv_path=args.csv,
                   cache_dir=args.cache_dir)

    cfg = SimConfig(radius=gains.hoop_radius)

    if args.command == "sweep":
        sweep(gains, cfg, trials=args.trials)
        return 0

    names = list(PROFILES) if args.profile == "all" else [args.profile]
    logs = []
    for name in names:
        entry = simulate(name, gains, cfg, feedforward=not args.no_feedforward,
                         seed=args.seed, t_end=args.duration)
        print(f"{name:8s} RMS {entry['rms'] * 1000:5.0f} mm   "
              f"max {entry['max'] * 1000:5.0f} mm   "
              f"tracked {entry['valid_frac'] * 100:3.0f}%"
              f"{'   RIM STRIKE' if entry['escaped'] else ''}")
        logs.append(entry)
    if args.csv:
        write_csv(logs[0]["rows"], args.csv)
    if not args.no_plot:
        plot(logs, save=args.save)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
