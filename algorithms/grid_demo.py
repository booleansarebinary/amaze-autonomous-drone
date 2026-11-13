"""Display a planned static-grid route without sensors, radio, or a drone."""

import argparse
import json
from pathlib import Path

from algorithms.grid_navigation import Grid, GridCoordinates, astar, inflate_obstacles


def load_grid(path: Path) -> Grid:
    """Read width, height, and optional blocked [x, y] pairs from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or not {"width", "height"} <= data.keys()
        or data.keys() - {"width", "height", "blocked"}
    ):
        raise ValueError("map requires width and height; only blocked is optional")
    blocked = data.get("blocked", [])
    if not isinstance(blocked, list) or any(
        not isinstance(cell, list) or len(cell) != 2
        or any(type(value) is not int for value in cell) for cell in blocked
    ):
        raise ValueError("blocked must be a list of integer [x, y] pairs")
    # JSON arrays become tuples at the existing grid boundary; Grid validates
    # integer coordinates, dimensions, and obstacle bounds.
    return Grid(data["width"], data["height"], frozenset(tuple(cell) for cell in blocked))


def render_grid(grid: Grid, start, goal, route) -> str:
    """Display highest y first so (0, 0) appears at the lower left."""
    route_cells = set(route or [])
    rows = []
    for y in reversed(range(grid.height)):
        row = []
        for x in range(grid.width):
            cell = (x, y)
            if cell == start == goal:
                marker = "B"
            elif cell == start:
                marker = "S"
            elif cell == goal:
                marker = "G"
            elif cell in grid.blocked:
                marker = "#"
            else:
                marker = "*" if cell in route_cells else "."
            row.append(marker)
        rows.append("".join(row))
    return "\n".join(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path, help="JSON map with width, height, and blocked cells")
    parser.add_argument("--start", type=int, nargs=2, required=True, metavar=("X", "Y"))
    parser.add_argument("--goal", type=int, nargs=2, required=True, metavar=("X", "Y"))
    parser.add_argument("--cell-size-m", type=float, help="square cell size in meters")
    parser.add_argument("--footprint-radius-m", type=float, help="provisional enclosing radius")
    parser.add_argument("--margin-m", type=float, help="provisional extra clearance")
    args = parser.parse_args(argv)
    start, goal = tuple(args.start), tuple(args.goal)
    clearance_values = (args.cell_size_m, args.footprint_radius_m, args.margin_m)
    clearance_enabled = any(value is not None for value in clearance_values)
    try:
        grid = load_grid(args.map)
        if clearance_enabled:
            if any(value is None for value in clearance_values):
                raise ValueError("cell size, footprint radius, and margin must be supplied together")
            grid = inflate_obstacles(
                GridCoordinates(grid, args.cell_size_m), args.footprint_radius_m, args.margin_m
            )
        route = astar(grid, start, goal)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    print("Planned route (offline)")
    print("Grid cells: x right, y up; (0, 0) at lower left.")
    if clearance_enabled:
        print(f"Clearance: radius {args.footprint_radius_m:g} m + margin {args.margin_m:g} m.")
    else:
        print("Clearance: not applied (point grid).")
    print("S=start, G=goal, B=start and goal, *=route, #=blocked, .=free")
    print(render_grid(grid, start, goal, route))
    if route is None:
        print("No planned route exists between the supplied cells.")
        return 1
    print(f"Steps: {len(route) - 1}")
    print(f"Cells: {route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
