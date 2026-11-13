"""Save validated offline planning results as deterministic, strict JSON."""

import json
from pathlib import Path


def save_plan(path, original_grid, planning_grid, start, goal, route, *,
              cell_size_m=None, footprint_radius_m=None, margin_m=None):
    """Save a supplied plan to a new file; never label it measured flight data."""
    plan = {
        "schema_version": 1,
        "data_kind": "planned_route",
        "status": "unreachable" if route is None else "route_found",
        "map": {"width": original_grid.width, "height": original_grid.height,
                "blocked": sorted(original_grid.blocked)},
        "planning_blocked": sorted(planning_grid.blocked),
        "start": start,
        "goal": goal,
        "movement": {"directions": 4, "step_cost": 1, "heuristic": "manhattan"},
        "coordinates": {
            "order": "x,y", "units": "cells", "x_direction": "right", "y_direction": "up",
            "waypoints": "cell_centers", "altitude_model": "assumed_fixed_unvalidated",
            "cell_size_m": cell_size_m,
            # The current CLI supplies a zero origin only when meter settings
            # are configured. A grid-only run has no physical frame assigned.
            "origin_m": None if cell_size_m is None else (0.0, 0.0),
        },
        "clearance": {
            "enabled": footprint_radius_m is not None and footprint_radius_m + margin_m > 0,
            "footprint_radius_m": footprint_radius_m,
            "margin_m": margin_m,
        },
        "route": route,
        "steps": None if route is None else len(route) - 1,
    }
    # Serialize first so invalid nonfinite numbers cannot create a bad file.
    text = json.dumps(plan, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8", newline="\n") as output:
        output.write(text)
