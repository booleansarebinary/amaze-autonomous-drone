# Astrophage navigation progress

## Scope and inspection baseline

The immediate priority is offline navigation with manually supplied maps,
starts, and candidate locations while ultrasonic hardware is unavailable.
The eventual mission remains described in [mission.md](mission.md).
This record tracks the navigation chunks; the older sensor-first sequence and
new-branch recommendation in [design-plan.md](design-plan.md) are superseded
for this work. No replacement branch is needed.

Chunk 0 inspected the mission documents, Git configuration, Python scripts,
test tools, Docker files, and Ansur's reactive and mapped controllers without
editing files. The mission branch has no previous grid planner. The cached
`origin/MAIN_eridian_trench_run` version of `SensorMapPlanner._plan` provides
an A*-style search to adapt later: priority queue, costs, predecessors, and
obsolete-entry rejection. Its sensor mapping, diagonal moves, exploration
fallback, and unknown-space penalties do not belong in the initial static
unit-cost planner. Reactive avoidance remains a separate future integration.
Existing geometry and plotting helpers may be useful in later chunks.

## Chunk 1: grid representation and neighbors — PASS

### Changes and behavior

- `algorithms/grid_navigation.py`: adds `Grid`, `in_bounds`,
  `is_traversable`, and `neighbors`, with `_validate_cell` for coordinate
  validation. This pure module belongs alongside the existing algorithms
  and imports no flight, radio, sensor, or plotting code.
- `algorithms/test_grid_navigation.py`: adds nine focused `unittest` tests
  covering the public grid behavior.
- This progress record captures decisions and executed evidence.

`Grid` stores positive integer width and height and an immutable snapshot of
blocked cells. Changing the caller's obstacle set cannot alter the grid.
Membership in that set identifies obstacles; other in-bounds cells are free.
`in_bounds` checks both axes, `is_traversable` also excludes obstacles, and
`neighbors` filters four candidate steps in east, north, west, south order.
Each allowed step has unit cost; no search or heuristic is implemented yet.

Cells are integer `(x, y)` tuples: x indexes width and y indexes height.
Bounds are `0 <= x < width` and `0 <= y < height`. Diagram origin is lower
left, with x increasing right and y increasing upward. A future row-based
array must use `rows[y][x]`. Coordinates currently have cell units, with no
physical size or world origin assigned.

Malformed cell queries raise `ValueError`. Well-formed out-of-bounds queries
return false for bounds/traversability and have no neighbors. Blocked sources
also have no neighbors. Invalid dimensions and out-of-bounds or malformed
blocked-cell tuples raise `ValueError`; nothing is silently clamped.

### Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Rectangular grids preserve x/width and y/height | PASS | Rectangular bounds and traversability tests |
| Bounds exclude negatives and upper limits | PASS | Bounds and invalid-obstacle tests |
| Obstacles and out-of-bounds cells are not traversable | PASS | Traversability test |
| Corners, edges, and interior have only legal cardinal neighbors | PASS | Corner/edge, interior, blocked-neighbor, and single-cell cases |
| Neighbor order is deterministic | PASS | Ordered east/north/west/south expectations |
| Invalid dimensions and blocked coordinates are rejected | PASS | Constructor validation test |
| Queries reject malformed coordinates | PASS | Validation across all three query methods |
| Caller edits cannot alter obstacle membership | PASS | Obstacle snapshot test |

### Executed validation

Interpreter: existing test-flight virtual environment, Python 3.14.7.
No dependency installation was needed; production code uses standard-library
features compatible with the project's declared Python >=3.10. Execution on
Python 3.10 and the Docker Python 3.12 image was not performed.

Tests were written before the production module. Exact command, run from the
mission worktree root both before and after implementation:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation -v
```

- Before implementation: exit 1, one loader error because
  `algorithms.grid_navigation` did not exist. No behavioral assertions ran;
  this is missing-module evidence, not a behavioral assertion failure.
- After implementation: exit 0, nine tests passed, zero failures, zero errors,
  zero skips. Adding the production module resolved the missing import.

Executed example command:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -c "from algorithms.grid_navigation import Grid; grid = Grid(width=4, height=3, blocked={(1, 0)}); print('neighbors((0, 0)) =', grid.neighbors((0, 0))); print('in_bounds((3, 2)) =', grid.in_bounds((3, 2))); print('in_bounds((2, 3)) =', grid.in_bounds((2, 3)))"
```

Actual output (exit 0):

```text
neighbors((0, 0)) = [(0, 1)]
in_bounds((3, 2)) = True
in_bounds((2, 3)) = False
```

East from `(0, 0)` is blocked; west and south leave the map, so only north
remains. The last two outputs illustrate the rectangular axis convention.

Mutation checks: NOT DUE in Chunk 1. The boundary and Manhattan-distance
checkpoint is due in Chunk 2. No deliberate faults or mutation artifacts
were created. No hardware or historical reactive simulations were run.

### Limitations, Git state, and next chunk

There is no A*, heuristic, physical coordinate conversion, footprint clearance,
candidate policy, or waypoint follower yet. Altitude is assumed fixed.
Physical use requires validating the fixed-altitude model, localization,
clearance, tracking, and the connection from measured pose to the route.
Offline grid results do not establish physical flight readiness. Real/fake
candidate identity is absent from this module.

Branch remains `astrophage-collection`, tracking
`origin/MAIN_collect_the_astrophage`. No commit or push was performed, and
nothing was staged. This chunk's three new files remain untracked pending
review. Pre-existing README modifications and deletions of
`docs/architecture.md`, `docs/decisions.md`, and `docs/pr_walkthrough.md` remain
untouched. No prompts, logs, or temporary artifacts were added.

Next proposed chunk: Manhattan distance with goal, single-axis, and mixed-axis
tests, followed by isolated boundary and distance mutation checks. Stop for
review before beginning that chunk.
