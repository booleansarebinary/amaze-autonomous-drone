"""Offline candidate ordering and visit bookkeeping; no hardware commands."""

from dataclasses import dataclass

from algorithms.grid_navigation import Cell, Grid, astar


@dataclass(frozen=True)
class CandidatePlan:
    """One selection result; unreachable lists only candidates tried this call."""

    status: str
    target: Cell | None = None
    route: tuple[Cell, ...] | None = None
    unreachable: tuple[Cell, ...] = ()


class CandidateVisits:
    """Try supplied locations in order; only explicit confirmation marks a visit.

    Candidate cells must be valid and free on the supplied (possibly inflated)
    grid. Duplicate cells represent one location, preserving first occurrence.
    This is a selection policy, not a sensor validator or flight controller.
    """

    def __init__(self, grid: Grid, candidates):
        cells = tuple(candidates)
        for cell in cells:
            if not grid.is_traversable(cell):
                raise ValueError(f"candidate must be an in-bounds, unblocked cell: {cell}")
        self._grid = grid
        self._candidates = tuple(dict.fromkeys(cells))
        self._visited: set[Cell] = set()
        self._pending: Cell | None = None

    @property
    def visited(self) -> frozenset[Cell]:
        """Return a snapshot that callers cannot use to alter visit tracking."""
        return frozenset(self._visited)

    def plan_next(self, current: Cell) -> CandidatePlan:
        """Select the first reachable unvisited cell from the supplied position.

        Recheck unreachable cells on each call; they were not visited, and a
        caller may supply a new position. Planning never confirms arrival.
        """
        if not self._grid.is_traversable(current):
            raise ValueError(f"current position must be an in-bounds, unblocked cell: {current}")
        unreachable = []
        for candidate in self._candidates:
            if candidate in self._visited:
                continue
            route = astar(self._grid, current, candidate)
            if route is None:
                unreachable.append(candidate)
                continue
            self._pending = candidate
            return CandidatePlan("target_selected", candidate, tuple(route), tuple(unreachable))

        self._pending = None
        if not self._candidates:
            status = "no_targets"
        elif len(self._visited) == len(self._candidates):
            status = "all_visited"
        else:
            status = "all_unreachable"
        return CandidatePlan(status, unreachable=tuple(unreachable))

    def confirm_visit(self, current: Cell) -> None:
        """Accept an offline arrival assertion for the most recently selected cell.

        Matching a supplied cell is not evidence of measured physical arrival.
        """
        if not self._grid.is_traversable(current) or current != self._pending:
            raise ValueError("visit confirmation must match the current selected candidate")
        self._visited.add(current)
        self._pending = None
