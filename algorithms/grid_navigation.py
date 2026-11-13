"""Hardware-free static grid at an assumed fixed altitude.

Cells are integer (x, y) tuples: x indexes width, y indexes height.
In diagrams, (0, 0) is lower left, +x points right, and +y points up.
Only listed obstacles are blocked; every other in-bounds cell is free.
Physical use requires validating the altitude model and localization.
"""

import heapq
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
