"""Offline candidate ordering and visit bookkeeping; no hardware commands."""

from dataclasses import dataclass

from algorithms.grid_navigation import Cell, Grid, astar


@dataclass(frozen=True)
class CandidatePlan:
    """One candidate/return result; unreachable lists candidates tried this call."""

    status: str
    target: Cell | None = None
    route: tuple[Cell, ...] | None = None
    unreachable: tuple[Cell, ...] = ()


class CandidateVisits:
    """Try supplied locations in order; only explicit confirmation marks a visit.

    Candidate cells must be valid and free on the supplied (possibly inflated)
    grid. Duplicate cells represent one location, preserving first occurrence.
    This is a selection policy, not a sensor validator or flight controller.
    Optional home must be free on the same grid. A simulated detection latches
    return planning; it does not assert collection, flight, or measured arrival.
    """

    def __init__(self, grid: Grid, candidates, *, home: Cell | None = None):
        if home is not None and not grid.is_traversable(home):
            raise ValueError(f"home must be an in-bounds, unblocked cell: {home}")
        cells = tuple(candidates)
        for cell in cells:
            if not grid.is_traversable(cell):
                raise ValueError(f"candidate must be an in-bounds, unblocked cell: {cell}")
        self._grid = grid
        self._candidates = tuple(dict.fromkeys(cells))
        self._visited: set[Cell] = set()
        self._pending: Cell | None = None
        self._home = home
        self._return_requested = False

    def simulate_detection(self, current: Cell) -> CandidatePlan:
        """Accept an explicit offline event and plan home from a supplied cell.

        Invalid inputs leave search unchanged. Repeated valid events only
        replan home; they never restart search or confirm additional visits.
        No sensor evidence is accepted or validated by this simulation API.
        """
        if self._home is None:
            raise ValueError("home must be supplied before simulated detection")
        self._validate_current(current)
        self._return_requested = True
        self._pending = None
        return self._plan_return(current)

    def _validate_current(self, current: Cell) -> None:
        if not self._grid.is_traversable(current):
            raise ValueError(f"current position must be an in-bounds, unblocked cell: {current}")

    def _plan_return(self, current: Cell) -> CandidatePlan:
        route = astar(self._grid, current, self._home)
        if route is None:
            # Failure to get home cannot authorize a new candidate visit.
            return CandidatePlan("return_unreachable", target=self._home)
        return CandidatePlan("return_planned", self._home, tuple(route))

    @property
    def visited(self) -> frozenset[Cell]:
        """Return a snapshot that callers cannot use to alter visit tracking."""
        return frozenset(self._visited)

    def plan_next(self, current: Cell) -> CandidatePlan:
        """Select the first reachable unvisited cell from the supplied position.

        Recheck unreachable cells on each call; they were not visited, and a
        caller may supply a new position. Planning never confirms arrival.
        After simulated detection, every call plans home instead, even after
        an unreachable result. A one-cell home route is not measured arrival.
        """
        self._validate_current(current)
        if self._return_requested:
            return self._plan_return(current)
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
