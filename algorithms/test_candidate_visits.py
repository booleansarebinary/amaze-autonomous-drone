"""Offline candidate ordering and explicit visit confirmation tests."""

import unittest

from algorithms.candidate_visits import CandidateVisits
from algorithms.grid_navigation import Grid, GridCoordinates, inflate_obstacles


class CandidateVisitsTests(unittest.TestCase):
    def test_supplied_order_takes_priority_over_nearest_candidate(self):
        visits = CandidateVisits(Grid(5, 2), [(4, 0), (1, 0)])
        plan = visits.plan_next((0, 0))
        self.assertEqual(plan.status, "target_selected")
        self.assertEqual(plan.target, (4, 0))
        self.assertEqual((plan.route[0], plan.route[-1]), ((0, 0), (4, 0)))
        self.assertEqual(len(plan.route) - 1, 4)
        self.assertEqual(plan.unreachable, ())

    def test_planning_even_at_the_target_does_not_mark_a_visit(self):
        visits = CandidateVisits(Grid(3, 2), [(2, 0)])
        first = visits.plan_next((0, 0))
        self.assertEqual(first.target, (2, 0))
        self.assertEqual(visits.visited, frozenset())
        again = visits.plan_next((2, 0))
        self.assertEqual(again.target, (2, 0))
        self.assertEqual(again.route, ((2, 0),))
        self.assertEqual(visits.visited, frozenset())

    def test_only_confirmed_visits_are_skipped_and_completion_is_explicit(self):
        visits = CandidateVisits(Grid(4, 2), [(1, 0), (3, 0)])
        self.assertEqual(visits.plan_next((0, 0)).target, (1, 0))
        visits.confirm_visit((1, 0))
        snapshot = visits.visited
        self.assertEqual(snapshot, frozenset({(1, 0)}))
        self.assertEqual(visits.plan_next((1, 0)).target, (3, 0))
        visits.confirm_visit((3, 0))
        finished = visits.plan_next((3, 0))
        self.assertEqual(finished.status, "all_visited")
        self.assertIsNone(finished.target)
        self.assertIsNone(finished.route)
        self.assertEqual(finished.unreachable, ())
        self.assertEqual(visits.visited, frozenset({(1, 0), (3, 0)}))
        self.assertEqual(snapshot, frozenset({(1, 0)}))

    def test_unreachable_candidate_is_reported_without_becoming_visited(self):
        grid = Grid(5, 3, blocked={(2, y) for y in range(3)})
        visits = CandidateVisits(grid, [(4, 1), (1, 1)])
        plan = visits.plan_next((0, 1))
        self.assertEqual(plan.target, (1, 1))
        self.assertEqual(plan.unreachable, ((4, 1),))
        self.assertEqual(visits.visited, frozenset())
        visits.confirm_visit((1, 1))
        next_plan = visits.plan_next((1, 1))
        self.assertEqual(next_plan.status, "all_unreachable")
        self.assertEqual(next_plan.unreachable, ((4, 1),))
        self.assertEqual(visits.visited, frozenset({(1, 1)}))

    def test_no_targets_and_all_unreachable_have_distinct_results(self):
        grid = Grid(5, 3, blocked={(2, y) for y in range(3)})
        for candidates, status, unreachable in [
            ([], "no_targets", ()),
            ([(4, 1), (3, 2)], "all_unreachable", ((4, 1), (3, 2))),
        ]:
            with self.subTest(candidates=candidates):
                visits = CandidateVisits(grid, candidates)
                plan = visits.plan_next((0, 1))
                self.assertEqual(plan.status, status)
                self.assertEqual(plan.unreachable, unreachable)
                self.assertIsNone(plan.target)
                self.assertIsNone(plan.route)
                self.assertEqual(visits.visited, frozenset())

    def test_confirmation_requires_the_current_selected_cell(self):
        visits = CandidateVisits(Grid(4, 2), [(1, 0), (3, 0)])
        with self.assertRaises(ValueError):
            visits.confirm_visit((1, 0))
        self.assertEqual(visits.plan_next((0, 0)).target, (1, 0))
        for wrong_cell in [(0, 0), (3, 0), (-1, 0)]:
            with self.subTest(wrong_cell=wrong_cell):
                with self.assertRaises(ValueError):
                    visits.confirm_visit(wrong_cell)
                self.assertEqual(visits.visited, frozenset())
        visits.confirm_visit((1, 0))
        with self.assertRaises(ValueError):
            visits.confirm_visit((1, 0))

    def test_duplicate_cells_are_one_location_and_input_order_is_snapshotted(self):
        candidates = [(1, 0), (1, 0), (2, 0)]
        visits = CandidateVisits(Grid(4, 2), candidates)
        candidates.append((3, 0))
        self.assertEqual(visits.plan_next((0, 0)).target, (1, 0))
        visits.confirm_visit((1, 0))
        self.assertEqual(visits.plan_next((1, 0)).target, (2, 0))
        visits.confirm_visit((2, 0))
        self.assertEqual(visits.plan_next((2, 0)).status, "all_visited")

    def test_invalid_candidate_or_current_cell_is_rejected(self):
        grid = Grid(3, 2, blocked={(1, 0)})
        for invalid in [(1, 0), (-1, 0), (3, 0), (0, 2), (0.5, 0), [0, 0]]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    CandidateVisits(grid, [invalid])
                visits = CandidateVisits(grid, [])
                with self.assertRaises(ValueError):
                    visits.plan_next(invalid)

    def test_unreachable_candidates_are_rechecked_from_a_new_supplied_position(self):
        grid = Grid(5, 3, blocked={(2, y) for y in range(3)})
        visits = CandidateVisits(grid, [(4, 1)])
        self.assertEqual(visits.plan_next((0, 1)).status, "all_unreachable")
        plan = visits.plan_next((3, 1))
        self.assertEqual(plan.target, (4, 1))
        self.assertEqual(plan.route, ((3, 1), (4, 1)))
        self.assertEqual(plan.unreachable, ())

    def test_candidate_route_uses_the_supplied_clearance_grid(self):
        original = Grid(9, 7, blocked={(4, 3)})
        planning = inflate_obstacles(GridCoordinates(original, 0.25), 0.1, 0.05)
        visits = CandidateVisits(planning, [(7, 3)])
        plan = visits.plan_next((1, 3))
        self.assertEqual(plan.target, (7, 3))
        self.assertEqual(len(plan.route) - 1, 10)
        self.assertEqual((plan.route[0], plan.route[-1]), ((1, 3), (7, 3)))
        for cell in plan.route:
            self.assertNotIn(cell, planning.blocked)


if __name__ == "__main__":
    unittest.main()
