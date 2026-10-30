"""Typed interfaces for the independent red-test gate."""
from dataclasses import dataclass
from enum import Enum

Vector2 = tuple[float, float]
Vector3 = tuple[float, float, float]

class RangeOutcome(str, Enum):
    HIT = "HIT"
    NO_RETURN = "NO_RETURN"
    INVALID = "INVALID"

@dataclass(frozen=True)
class Outcome:
    accepted: bool
    reason: str

@dataclass(frozen=True)
class RangeReading:
    beam: str
    monotonic_s: float
    outcome: RangeOutcome
    distance_m: float | None
    reason: str
    device_timestamp_ms: int | None = None
    received_monotonic_ns: int | None = None

@dataclass(frozen=True)
class DroneState:
    monotonic_s: float
    pos_world_m: Vector3
    vel_world_mps: Vector3
    yaw_rad: float
    roll_rad: float
    pitch_rad: float
    battery_v: float | None = None
    device_timestamp_ms: int | None = None

@dataclass(frozen=True)
class Command:
    vel_body_mps: Vector3
    yaw_rate_radps: float

