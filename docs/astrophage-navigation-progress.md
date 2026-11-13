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

Subsequent Git outcome: after separate approval, Chunk 1 was committed as
`72969d3` (`Add static occupancy grid and cardinal neighbors`) and pushed
alone to `origin/MAIN_collect_the_astrophage`. The status above records the
state at the original Chunk 1 review.

## Chunk 2: Manhattan-distance heuristic — PASS

### Changes and explanation

- `algorithms/grid_navigation.py`: adds `manhattan_distance(start, goal)`.
  It reuses `_validate_cell`, then adds the absolute x and y differences.
- `algorithms/test_grid_navigation.py`: adds five test methods covering the
  goal itself, horizontal and vertical movement in both directions, mixed-axis
  cases, and malformed endpoints. Existing nine grid tests remain unchanged.
- This record adds the acceptance evidence and controlled mutation results.

The calculation is `abs(start_x - goal_x) + abs(start_y - goal_y)`. A legal
step changes exactly one axis by one cell at cost one, so the result is the
shortest distance on an obstacle-free grid. Obstacles can require extra steps;
the calculation never overestimates a reachable goal's shortest route cost
(an admissible heuristic). Across any legal adjacent step its value changes
by at most one, matching the unit step cost (a consistent heuristic).

This helper is independent of a map: it accepts integer coordinate tuples,
including negative coordinates, but does not decide whether they are valid
endpoints on a particular grid. Endpoint traversability belongs to the later
search. It returns a cell-step count, not meters or flight time. There is
still no A* search in this chunk. The small formula needs only 12 production
lines including its explanation, rather than padding it to the chunk guide.

### Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Goal itself has distance zero | PASS | Goal-itself test returns 0 |
| Either axis counts unit steps in both directions | PASS | Horizontal returns 4; vertical returns 5 |
| Mixed axes sum their step counts | PASS | Four mixed cases return 7, including opposite signs |
| Reuse integer tuple validation for both endpoints | PASS | Malformed-endpoint subtests reject either endpoint |
| Match four-direction, unit-cost assumptions | PASS | Formula and admissibility/consistency reasoning above |
| Boundary fault detected by existing behavioral assertions | PASS | Inclusive-width mutant fails intended bounds assertion |
| Distance fault detected by behavioral assertions | PASS | Missing-y mutant fails intended vertical assertion |
| Restore correct code and rerun normal tests | PASS | Both temporary restorations and final worktree suite pass |

### Tests and worked example

All commands below use the existing Python 3.14.7 interpreter, with `-B`
preventing bytecode artifacts. Run from the mission worktree root:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation -v
```

Tests were added before the function. The first run exited 1: the existing
nine grid tests passed, but the five new methods could not call the absent
function (`AttributeError`, 17 error reports including subtests). These were
missing-function errors, not assertion failures. Adding the function resolved
them. After implementation and again after mutation checks, exit 0: 14 tests
passed, zero failures, zero errors, zero skips.

Executed worked example:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -c "from algorithms.grid_navigation import manhattan_distance; print('same cell:', manhattan_distance((3, 2), (3, 2))); print('horizontal:', manhattan_distance((1, 2), (5, 2))); print('vertical:', manhattan_distance((3, 1), (3, 6))); print('mixed:', manhattan_distance((1, 2), (4, 6)))"
```

Actual output, exit 0:

```text
same cell: 0
horizontal: 4
vertical: 5
mixed: 7
```

The mixed case needs at least three horizontal and four vertical moves.
It does not demonstrate that a route exists through any supplied obstacles.

### Controlled mutation checkpoint

Exact executed command (temporary driver is outside the repository):

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B C:\Users\victo\AppData\Local\Temp\astrophage_chunk2_mutation_check.py
```

The driver copied only the actual navigation module and unchanged tests into
an isolated temporary package. Each subprocess ran the same unittest command
above from that copy, with `PYTHONPATH` removed. No sensor, radio, or flight
module was included or executed. Baseline: 14 tests passed. Faults were
injected one at a time into the copied production module.

| Fault | Intended detecting test | Actual result |
|---|---|---|
| Change `x < self.width` to `x <= self.width` in `Grid.in_bounds` | `test_rectangular_bounds_use_x_for_width_and_y_for_height` | Exit 1; rejects mutant because `(4, 0)` incorrectly returns true for width 4. Seven assertion failures across bounds, neighbors, traversability, and validation; no errors. |
| Omit the y-distance term from `manhattan_distance` | `test_vertical_distance_in_both_directions` | Exit 1; rejects mutant because distance is 0 instead of 5. Five assertion failures including four mixed-axis cases; no errors. |

No mutant survived. Syntax, import, or infrastructure failures were not used
as detection evidence. The original implementation was restored after each
fault and the temporary suite passed all 14 tests each time. Tests remained
byte-for-byte unchanged, and SHA-256 checks confirmed that the working-tree
module and tests were never altered by the driver. The temporary package was
removed after its resolved location was checked inside the system temporary
directory. Driver exit: 0; cleanup confirmed. The external driver is not a
tracked artifact and is not part of the proposed commit.

### Git state, limitations, and next chunk

Chunk 2 changes only the existing navigation module, its tests, and this
progress record. They remain unstaged and uncommitted; no commit or push was
performed for Chunk 2. No outgoing commit exists against the cached mission
upstream. The pre-existing README change and three documentation deletions
remain untouched. `git diff --check` passes.

Limitations: no search, physical conversion, clearance inflation, or follower.
No hardware or flight evidence was obtained. Fixed-altitude suitability and
localization still require physical validation. A different movement or cost
model would require reassessing this heuristic.

Next proposed chunk: smallest complete A* search, adapting the existing
search structure identified in Chunk 0. Stop here for review; commit and
push of Chunk 2 require separate explicit approval.

Subsequent Git outcome: after approval of a plain-language commit body,
Chunk 2 was committed as `594bf3f` (`Add Manhattan distance for cardinal
grid navigation`) and pushed alone to `origin/MAIN_collect_the_astrophage`.
The Git state above records the original Chunk 2 review.

## Chunk 3: smallest complete A* search — PASS

### Purpose and changes

The purpose and acceptance criteria were presented for review before work
began, and implementation was authorized. This chunk connects the existing
grid and distance estimate into a shortest-route search.

- `algorithms/grid_navigation.py`: adds `astar(grid, start, goal)` and
  standard-library `heapq` and `itertools.count` imports. No dependencies added.
- `algorithms/test_grid_navigation.py`: adds seven search tests and a route
  validation helper checking endpoints, length, free cells, and unit steps.
- This record adds search decisions, test evidence, and a worked search.

The implementation adapts the queue/cost/predecessor structure inspected in
Ansur's `SensorMapPlanner._plan` on the cached trench mission branch. It uses
the existing `Grid.neighbors` and `manhattan_distance` functions. Sensor-built
maps, diagonal movement, exploration fallbacks, and unknown-space penalties
are not imported. No second map representation or mission controller is added.

### How search works

`g` is the best known number of steps from the start to a cell. `h` is the
Manhattan estimate of steps remaining. `f = g + h` is the priority for further
exploration. Python's `heapq` is a priority queue: it efficiently selects the
entry with the smallest priority without sorting the entire collection.

Entries contain `(f, insertion_number, g, cell)`. The increasing insertion
number makes equal priorities follow discovery order, combined with the
grid's east/north/west/south order. Tests require repeatability and shortest
length, without requiring one specific route when several shortest routes tie.

For each legal neighbor, search considers a route one step longer than the
current route. If it improves the neighbor's known cost, both that cost and
its predecessor (the cell it came from) are updated and a new entry is queued.
Old entries remain in the queue; when selected, an entry whose stored cost
differs from the current best is skipped. The goal is accepted only when
selected for expansion after this check. Predecessors are followed backward
from the goal, then reversed to return the start-to-goal route.

The return value includes both endpoints. Start equal to goal produces a
one-cell route, provided that cell is valid. Blocked, out-of-bounds, or
malformed endpoints raise `ValueError`. Valid but disconnected endpoints
return `None`; a partial route is not substituted for reaching the goal.

### Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Open-map shortest route includes both endpoints | PASS | 4-by-3 grid returns a valid 5-step route |
| Route detours around supplied obstacles | PASS | 3-by-2 grid returns a valid 4-step route |
| Returned cells and consecutive moves are legal | PASS | Shared assertions in all four nontrivial route tests |
| Cheaper discoveries update cost and predecessor | PASS | Regression route has 17 steps; runtime trace records `(4, 3)` improving from 11 to 9 |
| Obsolete entries are skipped | PASS | Code check and runtime trace of outdated `(4, 3)` entry with stored cost 11 and best cost 9 |
| Finish when goal is selected, not first discovered | PASS | Goal check follows queue removal and freshness check; tiny search trace below |
| Equal-priority choices are deterministic | PASS | Repeated calls return the same shortest route |
| Invalid endpoints differ from no route | PASS | Four invalid endpoint cases raise; disconnected valid endpoints return `None` |
| Start equal to goal returns one valid cell | PASS | Focused one-cell route test |

### Tests and results

Exact test command from the mission worktree root:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation -v
```

Seven search tests were written first. A temporary search skeleton returning
`None` allowed behavioral assertions to run before implementing the search.
Red result: exit 1, 21 methods run, nine assertion failures including endpoint
subtests, zero errors, zero skips. The 14 existing tests and the disconnected
case passed; that case alone could not distinguish the skeleton from search.

After replacing the skeleton with search: exit 0, all 21 tests passed, zero
failures, zero errors, zero skips. Interpreter remains Python 3.14.7. No Docker
build, dependency installation, sensor, radio, or flight operation was needed.

The regression map was selected using a deterministic, hardware-free
exploratory script comparing search with and without cheaper-cost updates.
The exploratory first-discovery-only search returned 19 steps; the actual
implementation returns 17. This exploration was not a controlled mutation of
the actual implementation and is not counted as mutation evidence. The test
checks the route's validity and length, not internal dictionary contents.

Mutation checks: NOT DUE in Chunk 3. The prior boundary/distance checkpoint
remains recorded in Chunk 2. Actual planner mutations and independent
breadth-first-search comparisons are due in Chunk 4.

### Executed worked search

Exact example command:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -c "from algorithms.grid_navigation import Grid, astar; grid = Grid(3, 2, blocked={(1, 0)}); route = astar(grid, (0, 0), (2, 0)); print('route:', route); print('steps:', len(route) - 1); print('unreachable:', astar(Grid(3, 2, blocked={(1, 0), (1, 1)}), (0, 0), (2, 0)))"
```

Actual output, exit 0:

```text
route: [(0, 0), (0, 1), (1, 1), (2, 1), (2, 0)]
steps: 4
unreachable: None
```

For the first input, the direct step east is blocked. A temporary diagnostic
using Python's `sys.settrace` observed the actual implementation without
editing it. Its selected cells and predecessor assignments were:

| Selected cell | g: steps so far | h: estimate remaining | f: priority | New predecessor assignment |
|---|---:|---:|---:|---|
| `(0, 0)` | 0 | 2 | 2 | `(0, 1)` comes from `(0, 0)`, cost 1 |
| `(0, 1)` | 1 | 3 | 4 | `(1, 1)` comes from `(0, 1)`, cost 2 |
| `(1, 1)` | 2 | 2 | 4 | `(2, 1)` comes from `(1, 1)`, cost 3 |
| `(2, 1)` | 3 | 1 | 4 | `(2, 0)` comes from `(2, 1)`, cost 4 |
| `(2, 0)` | 4 | 0 | 4 | Goal selected; follow predecessors backward |

The estimate initially understates the four-step detour, as expected.
The same diagnostic on the 8-by-7 regression input observed the predecessor
of `(4, 3)` being replaced with `(3, 3)`, reducing its cost from 11 to 9, and
the old queue entry later being skipped. No tracing code was added to the
production module or tests, and no diagnostic artifacts were saved in Git.

### Limitations, Git state, and next proposed chunk

This is offline pathfinding for a static, supplied, four-direction unit-cost
map. Broad edge-case coverage, independent shortest-path verification, and
planner mutations are still pending. Physical conversion, clearance,
candidate policy, and waypoint following are not implemented. Fixed-altitude
suitability and localization must be physically validated; these results do
not demonstrate physical flight readiness.

Only the navigation module, its tests, and this progress record changed for
Chunk 3. They remain unstaged and uncommitted. No commit or push was performed.
Pre-existing README modifications and deletions of `docs/architecture.md`,
`docs/decisions.md`, and `docs/pr_walkthrough.md` remain untouched. Branch is
`astrophage-collection`, tracking `origin/MAIN_collect_the_astrophage`.
No outgoing commits exist against the cached upstream. Whitespace checks
use `git diff --check`.

Next proposal: Chunk 4 will strengthen invalid-input and difficult-map cases,
compare shortest lengths with an independently written breadth-first-search
test oracle, and challenge obstacle checking and reconstruction with isolated
faults. Its purpose must be reviewed before implementation begins. Stop here
for Chunk 3 review; commit and push also require explicit approval.
