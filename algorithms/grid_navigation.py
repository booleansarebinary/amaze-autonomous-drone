"""Hardware-free static grid at an assumed fixed altitude.

Cells are integer (x, y) tuples: x indexes width, y indexes height.
In diagrams, (0, 0) is lower left, +x points right, and +y points up.
Only listed obstacles are blocked; every other in-bounds cell is free.
Physical use requires validating the altitude model and localization.
"""

import heapq
import math
from dataclasses import dataclass
from itertools import count


Cell = tuple[int, int]


def _validate_cell(cell: Cell) -> None:
    if (
        not isinstance(cell, tuple)
        or len(cell) != 2
        or any(type(coordinate) is not int for coordinate in cell)
    ):
        raise ValueError("cell must be an (x, y) tuple of integers")


def manhattan_distance(start: Cell, goal: Cell) -> int:
    """Minimum cardinal unit steps when obstacles are ignored.

    Each step changes exactly one axis by one. Obstacles can add steps,
    so this never overestimates a reachable goal's shortest route cost.
    This calculation is independent of map bounds or obstacle membership.
    """
    _validate_cell(start)
    _validate_cell(goal)
    return abs(start[0] - goal[0]) + abs(start[1] - goal[1])


@dataclass(frozen=True)
class Grid:
    """Finite occupancy grid; dimensions and obstacle membership cannot change."""

    width: int
    height: int
    blocked: frozenset[Cell] = frozenset()

    def __post_init__(self) -> None:
        for dimension in (self.width, self.height):
            # bool is an int subclass, but is not a meaningful grid dimension.
            if type(dimension) is not int or dimension <= 0:
                raise ValueError("grid dimensions must be positive integers")
        # Snapshot caller-owned sets so later edits cannot change the map.
        object.__setattr__(self, "blocked", frozenset(self.blocked))
        for cell in self.blocked:
            if not self.in_bounds(cell):
                raise ValueError(f"blocked cell outside grid: {cell}")

    def in_bounds(self, cell: Cell) -> bool:
        """Return False outside the grid; reject malformed coordinates."""
        _validate_cell(cell)
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def is_traversable(self, cell: Cell) -> bool:
        """A cell is traversable only if it is in bounds and unblocked."""
        return self.in_bounds(cell) and cell not in self.blocked

    def neighbors(self, cell: Cell) -> list[Cell]:
        """Return legal unit steps east, north, west, south, in that order.

        A blocked or out-of-bounds source has no legal steps.
        """
        if not self.is_traversable(cell):
            return []
        x, y = cell
        candidates = [(x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)]
        return [neighbor for neighbor in candidates if self.is_traversable(neighbor)]


def astar(grid: Grid, start: Cell, goal: Cell) -> list[Cell] | None:
    """Return a shortest cardinal route including both endpoints, or None.

    Blocked, out-of-bounds, or malformed endpoints raise ValueError.
    Equal priorities are explored in insertion order for repeatable routes.
    """
    for name, cell in (("start", start), ("goal", goal)):
        if not grid.is_traversable(cell):
            raise ValueError(f"{name} must be an in-bounds, unblocked cell: {cell}")

    # heapq selects the smallest entry. The sequence number breaks priority
    # ties in discovery order; cost is retained to recognize obsolete entries.
    sequence = count()
    frontier = [(manhattan_distance(start, goal), next(sequence), 0, start)]
    best_cost = {start: 0}
    predecessors: dict[Cell, Cell] = {}

    while frontier:
        _, _, cost, cell = heapq.heappop(frontier)
        # A cheaper route may have been queued since this entry was inserted.
        if cost != best_cost[cell]:
            continue
        # Finish when selected for expansion, after checking entry freshness.
        if cell == goal:
            route = [cell]
            while cell != start:
                cell = predecessors[cell]
                route.append(cell)
            route.reverse()
            return route

        for neighbor in grid.neighbors(cell):
            candidate_cost = cost + 1
            if candidate_cost < best_cost.get(neighbor, float("inf")):
                best_cost[neighbor] = candidate_cost
                predecessors[neighbor] = cell
                priority = candidate_cost + manhattan_distance(neighbor, goal)
                heapq.heappush(
                    frontier, (priority, next(sequence), candidate_cost, neighbor)
                )

    return None


@dataclass(frozen=True)
class GridCoordinates:
    """Square cells in meters with aligned +x/+y world and grid axes.

    origin_m is the lower-left outer boundary, not cell (0, 0)'s center.
    This defines a map frame; alignment with measured localization is unverified.
    """

    grid: Grid
    cell_size_m: float
    origin_m: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self) -> None:
        if (
            type(self.cell_size_m) not in (int, float)
            or not math.isfinite(self.cell_size_m)
            or self.cell_size_m <= 0
        ):
            raise ValueError("cell_size_m must be a finite positive number")
        self._validate_point(self.origin_m)
        for origin, cells in zip(self.origin_m, (self.grid.width, self.grid.height)):
            upper = origin + cells * self.cell_size_m
            half_cell = self.cell_size_m / 2
            if (
                not math.isfinite(upper)
                or origin + half_cell == origin
                or upper - half_cell == upper
            ):
                raise ValueError("map extents and cell centers must be representable")

    @staticmethod
    def _validate_point(point_m: tuple[float, float]) -> None:
        if (
            not isinstance(point_m, tuple)
            or len(point_m) != 2
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in point_m)
        ):
            raise ValueError("world point must be an (x, y) tuple of finite numbers in meters")

    def cell_center(self, cell: Cell) -> tuple[float, float]:
        """Return an in-bounds cell's center, including for blocked cells."""
        if not self.grid.in_bounds(cell):
            raise ValueError(f"cell outside grid: {cell}")
        x, y = cell
        origin_x, origin_y = self.origin_m
        return (
            origin_x + (x + 0.5) * self.cell_size_m,
            origin_y + (y + 0.5) * self.cell_size_m,
        )

    def world_to_cell(self, point_m: tuple[float, float]) -> Cell:
        """Find the containing cell; lower edges included, upper edges excluded.

        Internal boundaries belong to the positive side. Boundaries are the
        represented float values origin + index * cell_size_m, with no tolerance.
        """
        self._validate_point(point_m)
        indices = []
        for value, origin, cells in zip(
            point_m, self.origin_m, (self.grid.width, self.grid.height)
        ):
            if not origin <= value < origin + cells * self.cell_size_m:
                raise ValueError(f"world point outside grid: {point_m}")
            # Compare boundaries instead of dividing: subtraction/division can
            # round a point just below an edge into the cell on its other side.
            lower, upper = 0, cells
            while lower + 1 < upper:
                middle = (lower + upper) // 2
                if value < origin + middle * self.cell_size_m:
                    upper = middle
                else:
                    lower = middle
            indices.append(lower)
        return (indices[0], indices[1])


def inflate_obstacles(
    coordinates: GridCoordinates, footprint_radius_m: float, margin_m: float
) -> Grid:
    """Reserve whole-cell clearance for a circular footprint plus margin.

    Radius must conservatively enclose the vehicle; both inputs are provisional
    until dimensions and localization/tracking error are measured. Any contact
    at the requested clearance is rejected. Zero total clearance disables this
    operation. The source grid is never modified.
    """
    for value in (footprint_radius_m, margin_m):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("footprint radius and margin must be finite nonnegative meters")
    clearance_m = footprint_radius_m + margin_m
    if not math.isfinite(clearance_m):
        raise ValueError("combined clearance must be finite")
    grid = coordinates.grid
    if clearance_m == 0:
        return grid

    # Conservatively include near-contact despite decimal floating-point error.
    # This numerical guard is not a substitute for the physical margin.
    rounding_guard_m = max(1e-12, clearance_m * 1e-12)
    clearance_limit_m = clearance_m + rounding_guard_m
    cell_size_m = coordinates.cell_size_m
    blocked = set(grid.blocked)
    for x in range(grid.width):
        for y in range(grid.height):
            if (x, y) in grid.blocked:
                continue
            # Minimum distance from the entire candidate square to arena walls.
            wall_gap_m = min(x, y, grid.width - x - 1, grid.height - y - 1) * cell_size_m
            if wall_gap_m <= clearance_limit_m:
                blocked.add((x, y))
                continue
            for obstacle_x, obstacle_y in grid.blocked:
                # Adjacent squares touch. Subtract a full cell width to measure
                # square-to-square gaps rather than center-to-center distances.
                gap_x_m = max(abs(x - obstacle_x) - 1, 0) * cell_size_m
                gap_y_m = max(abs(y - obstacle_y) - 1, 0) * cell_size_m
                if math.hypot(gap_x_m, gap_y_m) <= clearance_limit_m:
                    blocked.add((x, y))
                    break
    return Grid(grid.width, grid.height, blocked)
