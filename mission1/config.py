"""Foundation configuration (importable interfaces for the red-test gate)."""
from dataclasses import dataclass, field

@dataclass(frozen=True)
class PhysicalConfig:
    arena_width_m: float = 4.0
    arena_depth_m: float = 4.0
    flight_height_m: float = 0.4
    status: str = "PROPOSED"
    measurement_reference: str = "§16 Stage A.1–3; §20.4"

@dataclass(frozen=True)
class MissionConfig:
    schema_version: int = 1
    queue_capacity: int = 1024
    shutdown_timeout_s: float = 2.0
    output_dir: str = "mission_runs"
    run_filename_prefix: str = "mission1"
    physical: PhysicalConfig = field(default_factory=PhysicalConfig)

DEFAULT_CONFIG = MissionConfig()

