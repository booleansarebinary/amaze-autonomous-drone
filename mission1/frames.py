"""Importable frame/unit interfaces, intentionally incorrect before red tests."""
from .types import Vector2, Vector3

def body_to_world_xy(vector_body_m: Vector2, yaw_rad: float) -> Vector2:
    return (0.0, 0.0)

def world_to_body_xy(vector_world_m: Vector2, yaw_rad: float) -> Vector2:
    return (0.0, 0.0)

def arena_to_world_xy(point_arena_m: Vector2, origin_world_m: Vector2, arena_yaw_rad: float) -> Vector2:
    return (0.0, 0.0)

def world_to_arena_xy(point_world_m: Vector2, origin_world_m: Vector2, arena_yaw_rad: float) -> Vector2:
    return (0.0, 0.0)

def beam_direction_body(beam: str) -> Vector3:
    return (0.0, 0.0, 0.0)

def mm_to_m(value: float) -> float:
    return 0.0

def degrees_to_radians(value: float) -> float:
    return 0.0

def radians_to_degrees(value: float) -> float:
    return 0.0

