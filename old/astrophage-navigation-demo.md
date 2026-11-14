# Offline navigation demo

Run from the repository root with Python 3.10 or later. The basic text demo
uses the standard library and the existing grid planner; it requires no
sensor, drone, radio, dashboard, or dependency installation.

## Supply a map and endpoints

Map files contain positive integer dimensions and optional blocked cells:

```json
{
  "width": 3,
  "height": 2,
  "blocked": [[1, 0]]
}
```

Only `width`, `height`, and `blocked` are accepted. Blocked coordinates must
be integer `[x, y]` pairs inside the map. Omitting `blocked` means no obstacles.
Start and goal are supplied separately in grid cells, not meters.

```sh
python -B -m algorithms.grid_demo examples/navigation/open.json --start 0 0 --goal 3 2
python -B -m algorithms.grid_demo examples/navigation/detour.json --start 0 0 --goal 2 0
python -B -m algorithms.grid_demo examples/navigation/unreachable.json --start 0 0 --goal 2 0
```

If `python` does not select your installed interpreter, replace it with
that interpreter's executable path. All commands use the module entry point
from the repository root.

The printed map puts `(0, 0)` at lower left: x increases right and y increases
upward. Its symbols are `S` for start, `G` for goal, `B` when both share a
cell, `*` for route, `#` for blocked, and `.` for free.

For the detour example, the map and route are:

```text
***
S#G
Steps: 4
Cells: [(0, 0), (0, 1), (1, 1), (2, 1), (2, 0)]
```

Output is labeled `Planned route (offline)`. Default output is text, with
optional PNG pictures and planned-route JSON export described below.
All outputs describe offline plans. The three examples produce five steps,
four steps, and no route, respectively.

## Optional clearance

Without clearance arguments, the supplied grid is planned as a point grid;
the output explicitly says clearance was not applied. To apply the existing
clearance calculation, provide all three settings together:

```sh
python -B -m algorithms.grid_demo examples/navigation/clearance.json --start 1 2 --goal 5 2 --cell-size-m 0.25 --footprint-radius-m 0.1 --margin-m 0.05
```

These are test values, not measured vehicle dimensions or approved margins.
The radius should enclose the vehicle; margin reserves extra room. The
resulting map shows both original obstacles and clearance exclusions as `#`.
The original JSON file is not changed. A start or goal excluded by clearance
is invalid and must be supplied again at a usable location; it is not moved
automatically. See the [progress record](astrophage-navigation-progress.md)
for geometry and validation evidence.

## Optional saved picture

Install the optional plotting packages into your chosen development
environment only if you want a picture:

```sh
python -m pip install -r algorithms/requirements-grid-plot.txt
```

Then add `--plot` with a new `.png` destination. For example, in PowerShell:

```powershell
$plotPath = Join-Path ([IO.Path]::GetTempPath()) 'astrophage-detour.png'
python -B -m algorithms.grid_demo examples/navigation/detour.json --start 0 0 --goal 2 0 --plot "$plotPath"
```

The parent directory must exist. Existing files and the input map are never
overwritten; choose a different filename for another run. Keep generated
pictures outside commits. No window opens automatically.

The picture shows original obstacle cells in red, extra clearance exclusions
in orange, a blue planned route, a green start triangle, and a purple goal
star. Axes show grid-cell indices, not meters; integer coordinates mark cell
centers. Both axes use the same scale, with positive y upward. The title says
`Planned route (offline)`. If no route exists, a picture can still be saved:
it shows both endpoints with a `No route` title and no route line, and the
command still exits with code 1.

Text-only operation does not import Matplotlib. Requesting a picture without
the optional packages produces an installation message and exit code 2.
Image output errors also use exit code 2. JSON export is available separately
or together with a picture, as described below.

## Save the plan as JSON

Add `--export` with a new destination to save the plan and its settings.
This uses the standard library and does not require Matplotlib:

```powershell
$planPath = Join-Path ([IO.Path]::GetTempPath()) 'astrophage-detour-plan.json'
python -B -m algorithms.grid_demo examples/navigation/detour.json --start 0 0 --goal 2 0 --export "$planPath"
```

The export's schema version is 1, and `data_kind` is always `planned_route`.
It records:

| Field | Meaning |
|---|---|
| `status` | `route_found` or `unreachable` |
| `map` | Width, height, and original blocked cells |
| `planning_blocked` | Cells blocked after optional clearance |
| `start`, `goal` | Supplied `[x, y]` grid coordinates |
| `movement` | Four directions, unit step cost, Manhattan distance |
| `coordinates` | Cell units, axis/order conventions, cell-center waypoints, assumed unvalidated fixed altitude, and any physical scale |
| `clearance` | Whether clearance is enabled and the supplied radius/margin |
| `route`, `steps` | Route including both endpoints, and its number of steps |

For the detour, the route is `[[0,0],[0,1],[1,1],[2,1],[2,0]]` and `steps`
is 4. A valid map with no route is still exported, with `status: "unreachable"`,
`route: null`, and `steps: null`; the command exits 1. A valid start equal
to goal has a one-cell route and zero steps. Invalid requests exit 2.

Without physical settings, `cell_size_m`, `origin_m`, radius, and margin
are `null`. With the existing clearance flags, the supplied size, radius,
and margin are saved, along with the CLI's assumed origin `[0.0, 0.0]` meters.
The route itself always uses grid cells. No measured position or altitude
is invented. The same plan produces the same JSON content, with sorted
obstacle lists. Nonfinite numbers are rejected before creating the file.

The parent directory must exist; existing files and the input map are never
overwritten. Keep generated exports outside commits. You may combine
`--plot` and `--export`, using different output filenames. They are separate
writes: the picture is saved first, so it may remain if a later JSON write
fails. Output errors use exit code 2. An export records a plan; it is not a
measurement log or a command to fly.

## Exit codes and limitations

| Code | Meaning |
|---|---|
| 0 | A planned route exists, including a zero-step start-at-goal route |
| 1 | Inputs are valid, but no route connects the endpoints |
| 2 | Input, file, or configuration error; explanation appears on stderr |

The demo assumes a static supplied map and a fixed-altitude 2D model.
Map accuracy, physical dimensions, localization, altitude suitability,
route following, and the connection from measured pose to the first waypoint
remain unverified. It sends no flight commands and establishes no physical
flight readiness.
