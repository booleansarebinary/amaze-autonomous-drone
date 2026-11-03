# amaze-autonomous-drone

## Navigation simulation

The default navigation simulator learns a map from its four range cones,
replans around obstacles, and explores when it cannot yet connect to the goal.
It receives no obstacle coordinates. Install the declared dependencies and run:

```bash
uv sync
uv run python algorithms/reactive_nav.py --scenario all
uv run python algorithms/reactive_nav.py --scenario all --save runs.png
uv run python algorithms/reactive_nav.py --stress --trials 150 --seed 7
uv run python -m unittest algorithms.test_reactive_nav -v
```

Use `--navigation reactive` for the earlier potential-field algorithm.
`--profile flight` retains that controller and its existing flight gains.
Mapped navigation needs yaw scanning to observe the blind wedges; disabling
the sweep can prevent progress.

See [the simulation report](docs/reactive_nav/mapped_navigation.md) for measured
efficiency, remaining failures, and reproducible comparisons, and
[the trajectory plot](docs/reactive_nav/mapped_runs.png) for the five built-in scenarios.

## Orbit prototype

Run the simulator from the repository root:

```bash
python3 algorithms/cache/orbit_prototype.py --scenario circle
```

For real flight, use a Crazyflie with Flow deck v2, Multi-ranger and Crazyradio,
with `cflib` installed in the Python environment running the script. Place an
isolated object on the drone's **left**, preferably about 0.55 m away, with a
surface intersecting the sensors at flight height. The drone approaches that
clearance sideways, then follows the surface counterclockwise.

```bash
python3 algorithms/cache/orbit_prototype.py --fly \
  --uri radio://0/80/2M/E7E7E7E7E7 --height 0.45 --speed 0.10 \
  --clearance 0.55 --timeout 120 --max-radius 3 --diag
```

This command initiates takeoff. Set `--uri` to your drone's address. Ctrl+C
requests landing. The controller also requests landing on approximate lap
completion, close obstacles, lost target, stale telemetry, low battery, time
limit, or distance limit. Landing depends on a working radio link. Distance and
lap checks use drifting local odometry; they are not a physical geofence.

Hardware mode is experimental and has not been flight-validated. Unlike the
ideal 360-degree simulator, it uses the four physical horizontal beams and
steers to keep a surface on the left. It cannot identify objects or guarantee
coverage of blind wedges, corners, or transparent/poorly reflecting surfaces.
Takeoff and landing use cflib's blocking MotionCommander routines; the mission
checks run before takeoff and during the boundary-following loop.
`--csv` and `--plot` currently apply only to simulation.

Offline checks (including mocked connection and landing cleanup):

```bash
python3 -m unittest algorithms.test_orbit_prototype -v
```
