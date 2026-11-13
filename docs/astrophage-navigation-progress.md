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

Subsequent Git outcome: Chunk 3 was committed with the approved plain-language
body as `340ce02` (`Add A* search for static grid routes`) and pushed alone
to `origin/MAIN_collect_the_astrophage`. The Git state above records its
original review.

## Chunk 4: planner edge cases and independent verification — PASS

### Purpose, changes, and behavior

The previously proposed verification scope was authorized before starting.
This chunk checks existing behavior more thoroughly; no production change
was needed. The A* module is unchanged from Chunk 3.

- `algorithms/test_grid_navigation.py`: adds `breadth_first_steps`, seven test
  methods, and stronger independent assertions in `assert_valid_route`.
- This progress record documents coverage, executed results, and mutations.

Breadth-first search explores cells in order of the number of steps needed
to reach them, using a first-in/first-out queue (`collections.deque`). With
equal step costs, the first arrival at the goal has the shortest length.
This test-only checker uses raw dimensions and blocked-cell coordinates,
its own movement/bounds checks, and a different movement order. It calls no
production neighbor, traversability, heuristic, or search function and does
not reconstruct a route. Its valid-input behavior is checked against four
hand-counted examples: open map, detour, disconnected map, and start at goal.

For each returned A* route, independent assertions check both endpoints,
integer tuple coordinates, map bounds, blocked-cell exclusion, and one-cell
horizontal/vertical moves. Length is compared with the independent answer;
an unreachable result must be `None`. The assertions do not demand the same
route when multiple shortest routes exist.

The deterministic comparison covers all obstacle combinations except the
two fixed free opposite-corner endpoints on three shapes:

| Shape | Optional obstacle cells | Maps | Requests, both directions |
|---|---:|---:|---:|
| 3 by 3 | 7 | 128 | 256 |
| 4 by 2 | 6 | 64 | 128 |
| 2 by 4 | 6 | 64 | 128 |
| Total | | 256 | 512 |

### Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Invalid inputs are distinct from a valid map with no route | PASS | Invalid endpoints raise `ValueError`; barriers/enclosures return `None` |
| Start equals goal still requires a valid free cell | PASS | Single-cell route succeeds; blocked/outside same-cell requests raise |
| Both endpoints reject every map boundary and malformed cells | PASS | Negative/upper x/y limits, floats, bools, NaN/infinity, wrong tuple size, list, string, and None |
| Detours and narrow passages remain valid | PASS | Existing detour plus 5-by-5 wall-gap example requiring eight steps |
| Rectangular and one-cell-wide maps preserve coordinates | PASS | 4-by-2/2-by-4 comparison sets and 1-by-5/5-by-1 routes in both directions |
| Every returned route cell and move is checked independently | PASS | Stronger shared route assertions applied to examples and comparison cases |
| Independent checker agrees on shortest length or no route | PASS | All 512 requests across 256 maps agree |
| Obstacle and reconstruction faults produce behavioral failures | PASS | Both required mutants detected; details below |
| Additional meaningful planner fault is detected | PASS | Keeping first discoveries gives 19 instead of 17 steps |
| Equivalent mutation is explained, correct code restored | PASS | Outdated-entry guard experiment documented below; all restored suites pass |

### Test-first verification and exact commands

The expanded tests were written before considering production changes. Their
first run already passed: the existing planner supplied the required behavior.
No artificial failure or implementation change was introduced to manufacture
a red/green cycle for this verification-only chunk. The deliberate faults
below supplied behavioral failures against the same passing tests.

Normal test command from the mission worktree root, using Python 3.14.7:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation -v
```

Initial expanded suite and final restored worktree run: exit 0; 28 methods
passed, zero failures, zero errors, zero skips. The 512 comparison requests
are subtests within one method, not 512 additional test methods. No
dependency installation, Docker build, hardware, or flight was involved.

### Controlled mutation checkpoint

Exact executed command; the driver is outside the repository:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B C:\Users\victo\AppData\Local\Temp\astrophage_chunk4_mutation_check.py
```

The driver copies the actual production module and unchanged relevant tests
into a temporary package and runs the full 28-method suite in a fresh Python
subprocess for each case. `PYTHONPATH` is removed, and no sensor, flight, or
radio module is included. The child loads the same suite with unittest's
standard loader and runner. Unchanged baseline: all 28 passed.

| Injected fault | Intended detecting test | Actual outcome |
|---|---|---|
| Remove obstacle membership check from `Grid.is_traversable` | `test_obstacle_requires_a_detour` | Detected by length assertion: 2 instead of 4 steps. Full suite: 461 assertion failures including subtests, zero errors/skips; exit 1. |
| Return `route[1:]`, omitting the starting cell | `test_open_grid_returns_a_shortest_route_with_both_endpoints` | Detected by starting-endpoint assertion. Full suite: 193 assertion failures including subtests, zero errors/skips; exit 1. |
| Replace cheaper-cost comparison with first-discovery-only membership check | `test_later_cheaper_route_replaces_an_earlier_discovery` | Detected by length assertion: 19 instead of 17 steps. Full suite: one assertion failure, zero errors/skips; exit 1. |
| Remove obsolete-entry guard | Output-equivalent under the present route contract | Survived: all 28 passed; zero failures/errors/skips, exit 0. This repeats expansions without changing returned routes; explanation below. |

The last mutation is equivalent for route results under the current static
grid and consistent Manhattan heuristic. The lower-cost entry is expanded
before its obsolete entry, and already considers the same neighbors at lower
cost. The older entry cannot improve those costs. Removing the check wastes
work without changing the route. The guard is retained for efficiency; no
assertion about internal expansion counts was manufactured to kill it.

All three non-equivalent mutants failed through intended behavioral
assertions, not syntax/import/infrastructure errors. No relevant behavioral
mutant survived, so no coverage repair was needed. Correct source was
restored after every experiment, and each of the four restored temporary
baselines passed all 28 methods. Copied tests stayed byte-for-byte unchanged;
SHA-256 checks confirmed the workspace module and tests were never modified
by the driver. Cleanup was restricted to the verified system temporary
directory and confirmed complete. Driver exit: 0. No deliberate fault or
temporary driver is part of this change.

### Executed worked example

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -c "from algorithms.grid_navigation import Grid, astar; from algorithms.test_grid_navigation import breadth_first_steps; blocked = {(2, y) for y in range(5) if y != 2}; grid = Grid(5, 5, blocked); route = astar(grid, (0, 0), (4, 0)); print('blocked:', sorted(blocked)); print('route:', route); print('A* steps:', len(route) - 1); print('independent checker steps:', breadth_first_steps(5, 5, blocked, (0, 0), (4, 0)))"
```

Actual output, exit 0:

```text
blocked: [(2, 0), (2, 1), (2, 3), (2, 4)]
route: [(0, 0), (1, 0), (1, 1), (1, 2), (2, 2), (3, 2), (4, 2), (4, 1), (4, 0)]
A* steps: 8
independent checker steps: 8
```

The route must pass through the opening at `(2, 2)`, making it longer than
the four-step direct distance. Both algorithms report eight steps.

### Limitations, Git state, and next proposal

Finite-map agreement is strong regression evidence, not a proof of every
possible input or physical navigation. The checker assumes valid endpoints
and unit costs; it is test-only. No world-coordinate conversion, clearance,
candidate policy, or follower exists yet. Fixed-altitude suitability and
localization require physical validation. No physical readiness is claimed.

Only the test file and this progress record changed. The production module
has no diff. Nothing was staged, committed, or pushed for Chunk 4. Existing
README modifications and deletions of `docs/architecture.md`,
`docs/decisions.md`, and `docs/pr_walkthrough.md` remain untouched. Branch
remains `astrophage-collection`, tracking `origin/MAIN_collect_the_astrophage`.
There are no outgoing commits against the cached upstream. Final whitespace
check command is `git diff --check`.

Next proposed purpose: Chunk 5 will define cell size, physical origin, axis
directions, meter units, cell-center waypoints, and explicit boundary rules.
It will test negative world coordinates and reject out-of-map points rather
than clamp them. These conversions will issue no drone commands. Present
the concrete conventions for review before implementing Chunk 5. Stop here
for review; commit and push require explicit approval.

Subsequent Git outcome: after approval, Chunk 4 was committed with its
plain-language body as `e1b10fa` (`Verify grid routes with independent search
and fault checks`) and pushed alone to `origin/MAIN_collect_the_astrophage`.
The preceding Git state records the original Chunk 4 review.

## Chunk 5: physical coordinate conversion — PASS

### Purpose, conventions, and files

The conversion purpose and conventions were proposed at the Chunk 4 review;
the instruction to commit/push Chunk 4 and continue authorized this chunk.
This adds map-frame coordinates in meters without sending drone commands.

- `algorithms/grid_navigation.py`: adds frozen `GridCoordinates`, configuration
  validation, `cell_center`, `world_to_cell`, and `_validate_point`. It refers
  to the existing `Grid`; there is no second occupancy map.
- `algorithms/test_grid_navigation.py`: adds ten conversion tests.
- This progress record adds conversion decisions and executed evidence.

Cells are square with configurable `cell_size_m`. `origin_m` is the
lower-left outer map boundary in meters, defaulting to `(0.0, 0.0)`.
Map-frame +x/+y align with grid +x/+y: x indexes width, y indexes height.
No rotation or measured-localization frame transform is implied.

For cell `(x, y)`, the center is:

```text
world_x = origin_x + (x + 0.5) * cell_size_m
world_y = origin_y + (y + 0.5) * cell_size_m
```

Cell-center coordinates are the intended future waypoint convention. A
world point belongs to the cell whose lower edges are included and upper
edges excluded. Thus an internal edge belongs to its positive side. The
outer lower map boundaries are included; upper boundaries are outside.
Out-of-map points raise `ValueError`; they are never silently clamped.

The cell boundaries are the represented floating-point values
`origin + index * cell_size_m`, with no implicit tolerance. The lookup
compares these boundaries by repeatedly halving the candidate range of
cells. This avoids subtraction/division rounding a point just inside an
edge into the wrong cell. It uses logarithmic lookup and allocates no full
boundary array. Numerical tolerance is not a substitute for measured
localization uncertainty, which belongs in later physical validation.

Sizes must be finite and positive; points/origin must be finite numeric
two-tuples. Booleans are rejected. Construction also rejects overflowing
map extents and configurations whose boundary-adjacent half-cell offsets
cannot be represented at the configured coordinate magnitude. Cell queries
reuse the existing integer coordinate and bounds validation.

Conversion is independent of traversability: a blocked cell still has a
physical location. A converted cell must pass the existing grid/planner
checks before it can be used as a route endpoint.

### Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Cell size, origin, axes, and meter units are explicit | PASS | Documented class/configuration and asymmetric coordinate examples |
| Waypoints use cell centers | PASS | Center formula and exact expected coordinates |
| Coordinates round-trip on rectangular grids | PASS | Every center on 4-by-2 and 2-by-4 maps converts back to its cell |
| Negative world coordinates are supported | PASS | Nonzero negative origin and negative-point tests |
| Internal boundaries belong to positive side | PASS | Separate x/y boundary tests, including decimal cell sizes |
| Outer boundaries are explicit with no clamping | PASS | Exact upper edges/outside lower edges rejected; nearest inside values accepted |
| Invalid cells, points, sizes, and origins are rejected | PASS | Type, shape, nonfinite, nonpositive, bounds, and representability cases |
| Conversion remains separate from obstacle checks and commands | PASS | Blocked-cell conversion test; no flight/radio dependency or command path |

### Test-first evidence and results

Exact initial command, run from the mission worktree root:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation.GridCoordinatesTests -v
```

Nine tests were written first, followed by an empty conversion skeleton with
the proposed fields and constant-return methods. Red result: exit 1,
nine methods run, 47 behavioral assertion failures including subtests,
zero errors, zero skips. The assertions exercised missing conversion and
validation behavior rather than failing on an absent import. A tenth
representability test was added before the full implementation.

After implementing conversion, exact full-suite command:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation -v
```

Result: exit 0; all 38 methods passed, zero failures, zero errors, zero skips.
This includes the existing 512 A*/independent-search comparison requests.
Interpreter remains Python 3.14.7; no dependencies were installed. Python
3.10 and Docker Python 3.12 were not separately executed.

Mutation checks: NOT DUE in Chunk 5. The required clearance-removal and
axis/unit faults are due in Chunk 6. No mutation artifacts were added here.
No hardware, radio, or flight code was run.

### Executed worked example

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -c "from algorithms.grid_navigation import Grid, GridCoordinates; coordinates = GridCoordinates(Grid(4, 2), 0.5, (-1.0, -0.5)); print('cell (2, 1) center in meters:', coordinates.cell_center((2, 1))); print('point (0.25, 0.25) cell:', coordinates.world_to_cell((0.25, 0.25))); print('internal boundary (0.0, 0.0) cell:', coordinates.world_to_cell((0.0, 0.0))); print('negative point (-0.9, -0.4) cell:', coordinates.world_to_cell((-0.9, -0.4)))"
```

Actual output, exit 0:

```text
cell (2, 1) center in meters: (0.25, 0.25)
point (0.25, 0.25) cell: (2, 1)
internal boundary (0.0, 0.0) cell: (2, 1)
negative point (-0.9, -0.4) cell: (0, 0)
```

For the first result: `-1 + 2.5 * 0.5 = 0.25` on x, and
`-0.5 + 1.5 * 0.5 = 0.25` on y. The map spans `[-1, 1)` on x and
`[-0.5, 0.5)` on y. Coordinates `(1.0, 0.0)` and `(0.0, 0.5)` are rejected
by the executed boundary tests.

### Limitations, Git state, and next proposal

These are coordinates in an assumed aligned map frame, not measured drone
positions or evidence of physical tracking. Connecting an actual starting
pose to a cell-center route remains unvalidated. Fixed-altitude suitability,
frame alignment, localization quality, and physical clearance still require
validation. No altitude value, follower, radio connection, or flight command
was introduced. Offline coordinate conversion proves no flight readiness.

Chunk 4 was committed and pushed as approved before this work. Chunk 5's
module, tests, and progress-record changes remain unstaged and uncommitted;
no Chunk 5 commit or push was made. Pre-existing README modifications and
deletions of `docs/architecture.md`, `docs/decisions.md`, and
`docs/pr_walkthrough.md` remain untouched. Branch is `astrophage-collection`,
tracking `origin/MAIN_collect_the_astrophage`, with no outgoing commits
against the cached upstream. Whitespace verification uses `git diff --check`.

Next proposed purpose: Chunk 6 will reserve room for a provisional drone
footprint plus configurable uncertainty margin, using cell geometry and
arena boundaries. A route through a narrow gap may become unavailable while
a wider route remains. Present the footprint, margin, and collision rules
for review before implementing that chunk. Stop here for Chunk 5 review;
committing and pushing this change require separate explicit approval.

Subsequent Git outcome: after approval, Chunk 5 was committed with the simpler
body as `b6646f1` (`Convert grid cells to map coordinates in meters`) and
pushed alone to `origin/MAIN_collect_the_astrophage`. The preceding status
records the original Chunk 5 review.

## Chunk 6: clearance-aware planning — PASS

### Purpose and files

The footprint-plus-margin purpose was reviewed and implementation authorized
along with the Chunk 5 commit/push. This chunk prepares a new blocked-cell map
that the existing A* function can use without changes to search.

- `algorithms/grid_navigation.py`: adds `inflate_obstacles(coordinates,
  footprint_radius_m, margin_m)`, reusing `GridCoordinates` and `Grid`.
- `algorithms/test_grid_navigation.py`: adds ten clearance tests.
- This record documents geometry, provisional inputs, test results, and faults.

Both radius and margin must be supplied explicitly as finite nonnegative
meters. Their sum must be finite. There is no assumed hardware dimension or
default physical margin. The radius must conservatively enclose the drone's
horizontal footprint; the margin must account for measured positioning,
tracking, map, and other relevant uncertainties before physical use. All
numerical examples here are test configurations, not validated flight values.

### Geometry and behavior

Required clearance is footprint radius plus margin. A candidate cell is kept
only if its entire square is farther than that clearance from all original
obstacle squares and arena walls. Contact at the requested clearance is
rejected. This is conservative over the whole cell, rather than just its
center or the center of an obstacle. It also covers the cardinal segments
between retained cell-center waypoints under the assumed static 2D geometry.
It does not cover actual vehicle tracking or the connection from measured
starting pose to the route.

For an obstacle at index `(obstacle_x, obstacle_y)`, square-to-square gaps are:

```text
gap_x_m = max(abs(x - obstacle_x) - 1, 0) * cell_size_m
gap_y_m = max(abs(y - obstacle_y) - 1, 0) * cell_size_m
distance_m = hypot(gap_x_m, gap_y_m)
```

`hypot` computes the straight-line distance from these perpendicular gaps,
including diagonal corner separation. Adjacent squares touch and have zero
gap. Wall clearance uses the minimum distance from the full candidate square
to the four arena edges. Map translation does not change these distances;
cell size does. Only original obstacles are used when classifying cells,
so new exclusions do not recursively inflate each other. The original map
is unchanged, and the returned `Grid` is directly usable by `astar`.

A tiny conservative numerical allowance is added for comparison:
`max(1e-12 meters, clearance_m * 1e-12)`. This rejects near-contact when
decimal floating-point rounding would otherwise incorrectly allow it.
It is separate from the physical margin. Zero radius and zero margin
explicitly disable the operation and return the original grid.

Whole-cell exclusion can reject routes that a finer or less conservative
planner could use. Any positive clearance excludes outermost arena cells
and obstacle-adjacent cells, even where a cell center alone might fit.
Callers must check the supplied start and goal on the resulting grid;
existing A* raises `ValueError` if either becomes blocked and returns `None`
if valid endpoints have become disconnected.

### Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Explicit provisional footprint radius and configurable margin | PASS | Required parameters, finite/nonnegative validation, documented physical limitations |
| Account for full obstacle/candidate squares and diagonal corners | PASS | Adjacent square and Euclidean corner-distance tests |
| Include arena boundaries and reject exact contact | PASS | All four walls, exact threshold, and decimal-rounding tests |
| Narrow corridor becomes unavailable | PASS | Original eight-step route becomes `None` with both endpoints still free |
| Wider corridor remains usable | PASS | Eight-step route survives through its middle row |
| Preserve meter scaling and translation behavior | PASS | 0.25/0.5 m cell sizes differ correctly; shifted origin gives identical exclusions |
| Radius and margin both affect exclusions | PASS | Increasing only margin blocks a previously usable cell |
| Preserve input map and explicit zero-clearance mode | PASS | Original obstacle set unchanged; zero total clearance returns unchanged map |
| Clearance-removal and unit defects detected | PASS | Both required mutations fail behavioral assertions |
| Restore correct code and rerun normal suite | PASS | Four restored temporary suites and final worktree suite pass |

### Test-first sequence and actual results

Exact first test command from the mission worktree root:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation.ClearanceTests -q
```

Nine tests were written before implementation. An empty skeleton returning
the input grid let them exercise the missing behavior. Red result: exit 1,
nine methods run, 22 assertion failures including subtests, zero errors,
zero skips. After implementation, the then-current 47-method suite passed.

Review identified a decimal-contact issue: `3 * 0.1` compares slightly
greater than `0.3`. A tenth test reproduced incorrect acceptance at an
obstacle and at a wall, using this exact command:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation.ClearanceTests.test_decimal_clearance_contact_is_not_lost_to_rounding -q
```

Red result: exit 1, one method, two behavioral assertion failures, zero
errors/skips. Adding the conservative rounding allowance resolved the fault.

Exact final full-suite command, also run after all mutations:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_grid_navigation -q
```

Result: exit 0; 48 methods passed, zero failures, zero errors, zero skips,
including the existing 512 independent route-length comparisons. Interpreter
is Python 3.14.7. No dependency installation, hardware, radio, or flight run.

### Controlled mutation checkpoint

Exact command; the driver remains outside the repository:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B C:\Users\victo\AppData\Local\Temp\astrophage_chunk6_mutation_check.py
```

The final checkpoint uses the actual implementation and unchanged final tests
in a temporary isolated package. Each fault runs alone in a fresh Python
subprocess, with `PYTHONPATH` removed, using unittest's standard suite loader
and runner. Baseline: all 48 pass. No hardware adapter is included.

| Fault | Intended detecting test | Final actual result |
|---|---|---|
| Return original map for every nonnegative clearance | `test_narrow_corridor_becomes_unreachable_with_clearance` | Eight-step corridor incorrectly remains available. 13 assertion failures including subtests, zero errors/skips; exit 1. |
| Replace configured cell size with 1.0 m | `test_cell_size_changes_physical_clearance_and_origin_does_not` | Cell `(6, 3)` incorrectly remains free with the smaller cells. Six assertion failures, zero errors/skips; exit 1. |
| Disable arena-wall clearance check | `test_arena_boundaries_reserve_the_whole_cell_and_reject_contact` | Arena-edge cell `(0, 2)` incorrectly remains free. Seven assertion failures including subtests, zero errors/skips; exit 1. |
| Omit margin from total clearance | `test_footprint_and_margin_add_in_meters` | Cell `(6, 3)` incorrectly remains free when margin should exclude it. Two assertion failures, zero errors/skips; exit 1. |

All faults were caught by intended behavioral assertions. No mutant survived;
syntax/import/infrastructure failures were not used as detection evidence.
The initial 47-test implementation also detected the four faults; after the
decimal fix, the complete checkpoint was rerun against the final 48 tests.
Each restored temporary baseline passed all 48 methods. Copied tests stayed
byte-for-byte unchanged; SHA-256 checks confirmed that workspace source and
tests were never altered by mutation runs. Temporary copies were removed
after checking their resolved location inside the intended temporary root.
Driver exit: 0; cleanup confirmed. No mutation artifact is part of the change.

### Executed worked example

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -c "from algorithms.grid_navigation import Grid, GridCoordinates, astar, inflate_obstacles; narrow = Grid(11, 7, {(x, y) for x in range(3, 8) for y in (2, 4)}); wide = Grid(11, 9, {(x, y) for x in range(3, 8) for y in (2, 6)}); narrow_clear = inflate_obstacles(GridCoordinates(narrow, 0.25), 0.1, 0.05); wide_clear = inflate_obstacles(GridCoordinates(wide, 0.25), 0.1, 0.05); print('narrow before clearance steps:', len(astar(narrow, (1, 3), (9, 3))) - 1); print('narrow after clearance route:', astar(narrow_clear, (1, 3), (9, 3))); route = astar(wide_clear, (1, 4), (9, 4)); print('wide after clearance route:', route); print('wide after clearance steps:', len(route) - 1)"
```

Actual output, exit 0:

```text
narrow before clearance steps: 8
narrow after clearance route: None
wide after clearance route: [(1, 4), (2, 4), (3, 4), (4, 4), (5, 4), (6, 4), (7, 4), (8, 4), (9, 4)]
wide after clearance steps: 8
```

Both examples use 0.25 m cells, a test footprint radius of 0.10 m, and a
test margin of 0.05 m. The narrow opening is one cell (0.25 m) wide;
the wider opening is three cells (0.75 m) wide. These are planned routes
under supplied geometry, not measured vehicle motion or validated dimensions.

### Limitations, Git state, and next proposal

The simple implementation checks every cell against original obstacles:
time scales with width times height times obstacle count. It is intended
for small supplied maps; no new optimization framework is introduced.
The circle, margin, static obstacle map, fixed altitude, localization, and
tracking assumptions must be validated before physical use. Inflation does
not validate actual starting-pose connections, braking, moving obstacles,
or flight readiness. Fine passages may be rejected conservatively.

Chunk 5 was committed and pushed before this work. Chunk 6 changes only the
navigation module, its tests, and this progress record. They remain unstaged
and uncommitted; no Chunk 6 commit or push was made. Existing README changes
and deletions of `docs/architecture.md`, `docs/decisions.md`, and
`docs/pr_walkthrough.md` remain untouched. Branch is `astrophage-collection`,
tracking `origin/MAIN_collect_the_astrophage`; no outgoing commits exist
against the cached upstream. Whitespace check: `git diff --check`.

Next proposed purpose: split Chunk 7 into a text command-line demonstration,
visualization, and planned-route JSON export if needed to keep each change
small. Review the first subchunk's supplied map/start/goal input and text
output before implementation. It will use the existing planner without a
dashboard, sensor, or radio dependency. Stop here for Chunk 6 review;
commit and push require separate explicit approval.
