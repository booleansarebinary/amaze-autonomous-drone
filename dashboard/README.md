# Two-metric OpenMCT demo

This combined branch contains the Crazyflie flight code, JSON telemetry writer,
OpenMCT demo, bridge, Docker setup, and integration tests in one checkout. The
demo displays estimated Position X and Position Y (meters).

## Get the combined branch

Clone the combined branch once, then run commands from that repository root:

```bash
git clone --branch telemetry-integration-combined https://github.com/booleansarebinary/amaze-autonomous-drone.git
cd amaze-autonomous-drone
git branch --show-current
```

The branch output should be `telemetry-integration-combined`. If you already
have this branch checked out, just open a terminal at the repository root.

## Run without hardware

Install the Python and browser dependencies:

```bash
python -m pip install -r dashboard/requirements-demo.txt
npm.cmd --prefix openmct-tutorial ci
```

Start synthetic telemetry in one terminal and the static server in another;
keep both running:

```bash
python dashboard/dataTest.py --fake
python -m http.server 8000
```

Open `http://localhost:8000/dashboard/`, then select **Crazyflie** and either
position metric in the OpenMCT tree.

## Show telemetry from a real flight

The flight program writes `telemetry/kalman_state_x.json` and
`telemetry/kalman_state_y.json`. Start the bridge from the repository root:

```bash
python dashboard/dataTest.py --json-dir telemetry
```

In another terminal at the same repository root, run the flight command when
the supervised hardware setup is ready:

```bash
./.venv/Scripts/python.exe algorithms/reactive_nav.py --fly --goal 2.0 0.0 --height 0.45 --uri radio://0/80/2M/E7E7E7E7E7 --diag
```

The bridge reads the files; it does not open the Crazyradio. Do not run
`dataTest.py --uri ...` alongside the flight command, because that mode also
tries to own the radio. The `--fly` command is a real flight, not a simulation.

## Docker launch

Docker Compose serves the webpage and runs the JSON bridge. The flight process
still runs on Windows, where it can use the Crazyradio. Stop any native server
or bridge already using ports 8000 or 8765. With Docker Desktop running, use
Git Bash from the repository root:

```bash
mkdir -p telemetry
docker compose -f compose.telemetry.yml up --build -d
docker compose -f compose.telemetry.yml logs -f bridge
```

Run the same flight command above in a second terminal at the repository root.
Open `http://localhost:8000/dashboard/`, hard-refresh if needed, and choose
Crazyflie -> Position X or Position Y. To stop the containers:

```bash
docker compose -f compose.telemetry.yml down
```

The telemetry folder is mounted read-only inside Docker; the host flight
process writes it. Archive the folder before the next flight, because starting
a flight initializes fresh X/Y files and replaces the prior files.

## Repeatable software tests (no hardware)

From the repository root, with the flight virtual environment and Node installed:

```bash
./.venv/Scripts/python.exe -m unittest algorithms.test_reactive_nav dev_scripts.test_telemetry_integration -v
node --test dev_scripts/test_telemetry_plugin.cjs
npm.cmd --prefix openmct-tutorial install --no-save playwright-core
node dev_scripts/test_telemetry_browser.cjs
```

After building the demo image, the browser test can also exercise the Docker
stack:

```bash
TELEMETRY_E2E_DOCKER=1 node dev_scripts/test_telemetry_browser.cjs
```

Tests use temporary JSON files and never run `--fly`. They cover exact sample
values and timestamps, delayed bridge startup, live batches, restart/backfill,
saved history after refresh, and rendered graph pixels, plus error and
reconnection cases. The test script uses Chrome; set `CHROME_PATH` if it is
not at the default Windows location. Installing tutorial dependencies with
`npm ci` removes the temporary Playwright package, so reinstall it before the
browser test if needed.

## Limits

- This is a two-position-metric demo; it does not add battery or attitude data.
- The bridge uses a custom JSON-over-WebSocket interface, not a telemetry REST API.
- The flight logger is configured for 20 Hz, but physical in-flight delivery,
  sensor accuracy, radio dropouts, and long-flight performance still need a
  supervised hardware test.
- JSON file export errors do not stop the flight controller. X and Y files are
  replaced individually, not as one cross-file transaction.
- The Docker image is for local demonstration, not a production deployment.
