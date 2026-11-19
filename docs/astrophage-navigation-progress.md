# Astrophage navigation progress

## Current direction and status

Improve the team lead's `algorithms/astrophage_collection_script.py` directly.
It remains the final runnable mission file; new runtime helpers belong there.
Tests stay in `algorithms/test_astrophage_collection_script.py`. Earlier
navigation modules are reference work, not a replacement runtime architecture.

Keep grid-point coordinates: `world = origin + index * spacing`, with no
half-cell offset. Use supplied static obstacles. Ultrasound, frontend work,
and reactive avoidance are outside this phase. No automatic physical flight.
The latest focused run passed 23 tests on Python 3.14.7. The mission script
has not changed during the current test phase. Physical flight is unverified.

This record summarizes completed work. The
[full record through commit 2603fd6](https://github.com/booleansarebinary/amaze-autonomous-drone/blob/2603fd6/docs/astrophage-navigation-progress.md)
preserves detailed historical commands, failing-test output, worked examples,
mutation assertions, restoration evidence, and earlier review-time Git status.
Results below are historical unless explicitly identified as newly executed.
The older [mission](mission.md), [design plan](design-plan.md), and
[follower design](astrophage-waypoint-follower-design.md) provide context;
their cell-center, separate-component, and reactive proposals do not override
the current single-script, grid-point decisions.

## Earlier offline work: retained as reference

These chunks concern the separate navigation modules. Their test results do
not establish that the team lead's script or a physical drone behaves correctly.
All listed implementation commits were approved and pushed to the mission branch.

| Chunk | What changed, in plain words | Recorded passing result | Commit |
|---|---|---|---|
| 0 | Inspected instructions, Git, Docker, and Ansur's navigation before choosing reusable ideas. | Inspection only | No code commit |
| 1 | Added a square-cell map and legal up/down/left/right neighbors in `grid_navigation.py`. | 9 tests | `72969d3` |
| 2 | Added Manhattan distance: horizontal steps plus vertical steps. | 14 tests | `594bf3f` |
| 3 | Added A* with best costs and predecessor links to return a shortest route. | 21 tests | `340ce02` |
| 4 | Checked difficult routes against an independent breadth-first search. | 28 methods, including 512 map/direction comparisons | `e1b10fa` |
| 5 | Added the earlier cell-center conversion with size and origin in meters. | 38 tests | `b6646f1` |
| 6 | Reserved whole cells around obstacle squares and arena walls for footprint plus margin. | 48 tests | `bb582f5` |
| 7A | Added a text-only supplied-map demonstration in `grid_demo.py`. | 57 tests | `b3f2fe9` |
| 7B | Added optional saved route pictures in `grid_plot.py`. | 64 with plotting; 59 passed/5 skipped without it | `ebb0b2b` |
| 7C | Added strict JSON planned-route export in `grid_export.py`. | 74 with plotting; 68 passed/6 skipped without it | `4811b39` |
| 8A | Added supplied-order candidate selection and explicit visit confirmation in `candidate_visits.py`. | 84 with plotting; 78 passed/6 skipped without it | `42e3915` |
| 8B | Added simulated detection that requests a fresh obstacle-aware route home. | 92 with plotting; 86 passed/6 skipped without it | `37c7934` |
| 9 | Inspected flight interfaces and documented a future measured-position follower. No follower implementation. | Documentation only | `873ea5a` |

The offline model uses cardinal unit-cost movement at an assumed fixed altitude.
Its A* includes both endpoints, distinguishes invalid inputs from no route, and
accepts the goal when selected for expansion. Its cell-center geometry and
whole-square inflation cannot be silently reused as grid-point geometry.
Physical altitude suitability, localization, and first/final route connections
remain unvalidated. Planned JSON and pictures are not measured flight data.

Earlier test-first failures were resolved before the recorded passing runs.
Material fixes included decimal-contact rounding in clearance and rejection of
nested/noninteger obstacle coordinates before CLI set construction. Plotting
dependencies were installed only in a temporary environment. Full failure and
fix details remain in the linked record rather than repeated here.

Remote commit `07d2a57` introduced the team lead's collection script and moved
earlier navigation files into `old/`. With user approval, 8A retained that new
script and restored the navigation modules to `algorithms/`, with documents
under `docs/`. Unrelated archived files remained. No history was rewritten.

### Recorded deliberate-fault checks

Each fault was applied separately to an isolated copy of the actual code,
with hardware excluded and tests unchanged. Correct code was restored and
passing baselines rerun. Temporary faults/drivers were not committed.

| Checkpoint | Injected faults | Recorded outcome |
|---|---|---|
| 2 | Accept upper x boundary; omit vertical distance | Both caught by intended assertions; 14-test baselines restored |
| 4 | Ignore obstacles; omit route start; refuse cheaper routes | All caught; 28-test baselines restored |
| 4, equivalent case | Remove obsolete-queue-entry guard | Survived because returned routes are unchanged under the current model; only extra work results. No artificial assertion added |
| 6 | Remove inflation; assume 1 m cells; ignore arena walls; omit margin | All four caught; final 48-test baselines restored |
| 8A | Revisit confirmed candidates | Three assertion failures; 10-test baseline restored |
| 8B | Ignore return obstacles; forget the return request | Three and four assertion failures respectively; 18-test baselines restored after each |

These results apply to the older modules, not the current script. No relevant
non-equivalent survivor remained in those checks. Syntax/import/infrastructure
failures were not counted as useful mutation detection.

## Current phase: read-only audit, Chunk -1

Baseline: `873ea5a45827acb66aa1e0b1bc2e004285861738`. No files changed, fetch,
installation, or hardware connection occurred. The audit inspected the actual
171-line script, existing tests, documentation, and supporting cflib calls.

Implemented but without focused script tests at that point: `to_cell`,
`to_meters`, `is_blocked`, `astar`, `corners`, `plan`, `fly`, and `main`.
The script plans grid-point routes and sends timed high-level flight commands.
Missing: live snapshots, measured arrival, continuous-segment checks, live
boundaries, explicit cancellation/fault handling, and mission JSONL output.
Home is assumed zero; a sign flip does not establish coordinate alignment.
The single 0.15 m CLEARANCE constant has no measured error-budget breakdown.

Existing README changes and deleted placeholders initially blocked synchronization.
At the user's direction, the placeholders were restored and the README was
committed as `051f30b`. That README contains older setup instructions, not a
verified current operator guide. The first priority was protecting useful
script behavior with separate tests before making small fixes.

## Current phase: Chunk 0 - synchronization and dependencies

**Purpose:** verify the repository baseline and software interfaces without
changing runtime code, installing dependencies, or connecting to hardware.

The clean worktree was `C:/Users/victo/amaze-hula-hoop`, on local branch
`astrophage-collection`, tracking `origin/MAIN_collect_the_astrophage`.
Verified origin: `https://github.com/booleansarebinary/amaze-autonomous-drone.git`.

`git fetch origin` succeeded. Fetched mission tip was
`873ea5a45827acb66aa1e0b1bc2e004285861738`; local HEAD was
`051f30babb777f8c9b94a9027ae29b28a90d0ed0`. The comparison command below returned
`1 0`: one local README commit, no incoming mission commits. No fast-forward
was needed, no divergence existed, and the audited script findings were unchanged.

```powershell
git rev-list --left-right --count HEAD...origin/MAIN_collect_the_astrophage
```

| Dependency or interface | Observed state | Remaining action |
|---|---|---|
| Python | Project selects 3.10, requires >=3.10, and has no local `.venv`; inspected sibling environment runs 3.14.7 | Establish a reproducible project environment separately |
| cflib | Installed and locked at 0.1.33 | Verify against actual firmware later |
| Required packages | PyUSB 1.3.1, libusb-package 1.0.30.0, NumPy 2.5.3, SciPy 1.18.1, packaging 25.0, PyYAML 6.0.3; imports passed | No installation performed |
| USB backend | Default libusb0/libusb1/OpenUSB unavailable; explicitly packaged libusb1 loads | Resolve default radio backend loading in a reviewed change |
| USB hardware | Windows enumeration found no matching Crazyradio `1915:7777` | Driver, firmware, decks and usable localization remain unverified |
| Docker/tools | Client 29.8.0 present; engine unavailable; uv/usbipd not on PATH | Native Windows is the initial proposed path; setup still pending |

Exact successful import check, exit 0:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -c "import sys,cflib,usb,numpy,scipy,packaging,yaml,libusb_package; print('Dependency imports passed'); print('Python:',sys.version.split()[0])"
```

It printed `Dependency imports passed` and `Python: 3.14.7`.
`docker version --format '{{.Client.Version}} {{if .Server}}{{.Server.Version}}{{end}}'`
exited 1 because the Linux-engine pipe was unavailable. Missing optional tool
lookups also returned 1; these were not failed Python imports or mission tests.
No software/backend fix was attempted. Hardware facts remain pending.

Library findings: PositionHlCommander waits estimated travel time and remembers
targets; it does not confirm arrival. Its context takes off/lands automatically,
and controller selection can write a parameter during construction.
MotionCommander resets the estimator on takeoff and repeats hover requests in
a background sender, default 0.2 s. Motor-stop APIs are not hover. Ordinary
Crazyflie.close_link sends a zero-thrust setpoint, which strict telemetry-only
cleanup must address. A reset is not proof of map alignment. The final command
family remains conditional on actual firmware and positioning capability.

**Acceptance:** PASS for directory/branch/remote verification, safe fetched
history comparison, preservation of local work, unchanged audit findings,
dependency/API inspection without connection, and no runtime/test edits.
Implementation tests and mutations: not applicable. Whitespace check passed.

**Git outcome:** `f298b1b` recorded this audit. The existing README push needed
separate approval; after approval, `051f30b` and then `f298b1b` were pushed
separately, one new commit per push. No reset, stash, or history rewrite.

**Plain-language recap:** We checked which code and tools we had before changing
anything. GitHub had no new mission code to bring in. Some software and hardware
requirements are still unresolved, and we did not connect to or fly the drone.

## Milestone 1A - grid-point conversion tests

**Purpose/files:** add seven GridPointConversionTests to
`algorithms/test_astrophage_collection_script.py`, plus this record.
Exercise `to_cell` and `to_meters`; keep the production script unchanged.

**Acceptance results - all PASS:**

- Zero point equals origin, without a half-cell offset.
- X/y remain distinct; configured origin and spacing apply to both axes.
- All 45 points in a rectangular example round-trip correctly.
- Between-point requests select the nearest point; negative meter positions work.
- Binary-exact halfway cases document Python's current ties-to-even rounding.
- Tests remain separate and execute only pure conversion functions.

Test settings are changed temporarily in memory with unittest.mock.patch and
restored after each test. No files are edited by that configuration substitution.
These characterization tests passed existing behavior immediately; no artificial
failing baseline or production fix was needed. They do not endorse every current
input or physical assumption. Mutations were not due for this small test chunk.

Exact test command used for both 1A and 1B, from the worktree root:

```powershell
& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_astrophage_collection_script -v
```

**Recorded result at 1A:** exit 0, 7 passed, zero failures/errors/skips on Python
3.14.7. Python 3.10 and unrelated navigation suites were not run. Whitespace
checks passed; the new-file no-index diff returned 1 for a file difference,
not a whitespace or test failure. No dependency was installed.

**Executed example:** requested `(0.26,0.34)` meters -> point `(3,3)` -> displayed
snapped meters `(0.30,0.30)`. The display used two decimal places. These are
conversion outputs, not measured movement. Reporting that adjustment in the
mission output remains a later change.

**Limits/Git:** no input-validation, planning, dry-run, or hardware claim.
Committed/pushed as `d31690c` after approval. The next reviewed chunk was 1B.

**Plain-language recap:** We checked that the script converts between grid points
and meters as expected. All seven tests passed, so the script needed no change.
Rounding can move a requested target; the script still needs to tell the user
when that happens.

## Milestone 1B - point clearance and A* tests

**Purpose/files:** add PointClearanceTests and GridPointSearchTests (six new
methods plus a route-assertion helper) to the same separate test file, and update
this record. Existing conversion tests and the production script stay unchanged.

**Acceptance results - all PASS:**

- Detect points inside/on/near a rectangle; permit distant points and no obstacles.
- Check later rectangles even when the first is far away.
- Use straight-line corner distance: 0.25 m on each axis is about 0.354 m,
  blocked at clearance 0.375 m and free at 0.3 m.
- Find four-step horizontal and two-step vertical shortest open routes.
- Find a six-step shortest detour around known blocked point `(2,1)`.
- Return None across a separating wall, from either side.
- Return one point and zero steps for a valid start equal to goal.
- Preserve all seven conversion tests and return valid in-bounds cardinal steps.

The search example uses AREA `(0,4,0,2)`, spacing 1 m and clearance 0.25 m:
five by three inclusive grid points. These are test values, not flight settings.
Expected forbidden points and hand-counted lengths are independent of the
production obstacle checker. Tests accept any equally short valid route.

**Recorded verification:** the exact command in 1A exited 0 with 13 passed and
zero failures/errors/skips on Python 3.14.7. The helper was strengthened to assert
a non-empty route before indexing, then the same 13 tests passed again.
`git diff --exit-code -- algorithms/astrophage_collection_script.py` exited 0;
`git diff --check` passed. No behavior failed and no production fix was needed.
No new run of unrelated suites or Python 3.10 was claimed. Mutation checks
remain due at Milestone 2's planning-validation checkpoint.

**Executed example:** start `(0,1)`, goal `(4,1)`, obstacle rectangle
`(1.75,0.75,2.25,1.25)` produced:

```text
[(0,1), (1,1), (1,0), (2,0), (3,0), (3,1), (4,1)]
steps: 6
```

Replacing the obstacle with wall `(1.75,0,2.25,2)` returned None. The displayed
detour is an observed example, not the only accepted route.

**Limits/Git:** point clearance does not validate the movement between points.
Invalid endpoints/configuration, wall clearance, exact-contact policy, footprint
allowances, measured route adherence and hardware remain unverified. No physical
or mocked-flight success is claimed. Committed/pushed as `2603fd6` after approval.

**Plain-language recap:** We checked whether points are too close to obstacles
and whether A* finds sensible shortest routes. All 13 tests passed. The example
took six steps around an obstacle and reported no route through a wall. We still
need to check the space between points before treating a route as safe to fly.

## Milestone 1C - corner-reduction tests

**Purpose/files:** add five CornerReductionTests in the same separate test file,
plus this record. Exercise `corners()` on valid cardinal paths without changing
the runtime script or its function contract.

**Acceptance results - all PASS:** straight runs in all four directions keep
only the destination; multiple turns and the final point stay in order; a
one-step path omits its start; a one-point path returns an empty command list;
retained points use the configured meter origin/spacing with no half-cell offset.
Temporary in-memory test settings are restored after each test.

**Executed test example:** with zero origin and 1 m spacing,
`[(0,0),(1,0),(2,0),(2,1),(2,2),(1,2),(0,2),(0,1)]` becomes
`[(2,0),(2,2),(0,2),(0,1)]`. Intermediate points along straight runs are removed;
each turn and the destination remain. This is a command-list result, not flight.

**Verification:** the exact unittest command in 1A exited 0: all 18 methods
passed, zero failures/errors/skips on Python 3.14.7. Five methods are new; the
previous 13 still pass. Existing behavior passed immediately, so no artificial
failing baseline or production fix was needed. `git diff --check` passed, and
the runtime-source diff is empty. No dependency changes or hardware access occurred.
Mutations are not due for this small characterization chunk; the planning
checkpoint remains due with Milestone 2. Python 3.10 was not executed.

**Limits/Git:** reduction does not check obstacle clearance between retained
points, actual start position, measured arrival, malformed paths, or flight.
An empty command list for a one-point path is not proof of physical arrival.
Committed and pushed as `e68c5d9` after approval. No runtime code changed.

**Plain-language recap:** We checked that the script removes unnecessary stops
on straight stretches while keeping the turns and destination. All 18 tests
passed, so the script needed no change. We still have to check that the actual
movement between these points is safe.

## Milestone 1D - complete route-planning tests

**Purpose/files:** add five `CompletePlanTests` to the separate test file and
record the results here. Exercise `plan()` with small supplied, grid-aligned
maps. The mission script and its function contracts remain unchanged.

**Acceptance results - all PASS:** two supplied targets stay in order and are
followed by a home leg; each tested leg ends at its intended grid point; no
targets yield only an empty home leg; blocked targets and blocked home report
the stop; a wall separating start and target reports no path. The supplied
target list remains unchanged. Temporary test settings are restored afterward.

**Executed example:** with 1 m spacing, no obstacles, and targets `(1,0)` then
`(1,1)`, the returned stop order was `(1,0)`, `(1,1)`, `(0,0)`; the first two
waypoint lists were `[(1,0)]` and `[(1,1)]`, and the home leg ended at `(0,0)`.
This is a planned route, not a measured flight or verified arrival.

**Verification:**
`& C:\Users\victo\amaze-test-flight\.venv\Scripts\python.exe -B -m unittest algorithms.test_astrophage_collection_script -v`
exited 0 on Python 3.14.7: 23 tests passed, zero failures/errors/skips.
The five new tests passed on the existing code, so there was no missing behavior
to demonstrate or production fix to make. No hardware or flight library was
used. Mutations are due at the Milestone 2 planning-validation checkpoint,
not for this characterization chunk. Python 3.10 was not tested.

**Limits/Git:** `plan()` has no measured position, segment clearance check,
input validation, or report of snapping to a grid point. An empty leg does not
establish arrival. Only the test file and this record are changed; this 1D
change is uncommitted and unpushed. Stop for review.

**Plain-language recap:** We checked that the script plans the stops in the
given order and adds a route home. It also reports when a stop is blocked or
cut off by a wall. All 23 tests passed, but these checks say nothing about what
a physical drone actually did.

## Remaining work and next review

Next proposed chunk: check that importing the script and running `--dry-run`
cannot call flight APIs. Keep radio access mocked and use the existing CLI.
No next chunk has started.

Then make small reviewed changes for input/snapping validation, continuous
segments and a measured clearance budget. Telemetry must establish coherent,
fresh position/velocity/yaw/altitude before feedback movement is added.
Monitoring must separate waypoint distance, finite-segment deviation, operating
bounds and obstacle clearance, including first/final connections and movement
between samples. One command owner must distinguish travel, braking, feedback
hold, controlled landing and motor shutdown, with explicit fault responses.

Firmware, decks, frame alignment, localization drift, sampling timing, braking,
settling and landing need real evidence. A supplied static map cannot detect
unmapped obstacles. No sensor/frontend work or automatic flight is authorized.
Operator instructions/configuration guides will use implemented commands only;
they are not yet available as verified live-testing procedures.

## Documentation cleanup - completed

Only the progress document changed. Repeated historical commands, review-time
Git status and duplicate explanations were condensed; full evidence remains
in the linked committed record. Each post-synchronization chunk now ends with
a plain-language recap. No runtime code, tests, dependencies or hardware changed.

Verification: `git diff --check -- docs/astrophage-navigation-progress.md` passed.
Implementation tests and mutations are not applicable and were not rerun.
The cleanup was committed/pushed as `e12e62d` after approval.

**Plain-language recap:** We shortened the record so the main decisions and
results are easier to find. The older detail is still available in Git history.
The code and its test results have not changed.
