# Two-metric OpenMCT demo

This branch displays the Crazyflie's Flow-deck estimated position as two live
OpenMCT telemetry points: Position X and Position Y (meters).

## Run without hardware

From the repository root, install the Python and browser dependencies once:

```bash
python -m pip install -r dashboard/requirements-demo.txt
npm.cmd --prefix openmct-tutorial ci
```

Start the synthetic telemetry source in one terminal:

```bash
python dashboard/dataTest.py --fake
```

Start a static server in a second terminal:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/dashboard/`, then select **Crazyflie** and either
position metric in the OpenMCT tree.

## Read real telemetry

Run `python dashboard/dataTest.py --uri radio://0/80/2M/E7E7E7E7E7` instead of
`--fake`. This process is read-only, but it owns the Crazyradio connection.
Do not run it at the same time as `algorithms/reactive_nav.py --fly`.

## Show data from a real flight

`reactive_nav.py --fly` writes the two JSON files while it flies. Start this
bridge before flight so it reads those files and forwards new samples to the
dashboard without opening the Crazyradio:

```bash
python dashboard/dataTest.py --json-dir ../amaze-test-flight/telemetry
```

In another terminal, run `reactive_nav.py --fly` from `amaze-test-flight`.
The bridge and flight program can run together because only the flight program
connects to the radio.

## Docker launch for real-flight JSON

The dedicated demo compose file replaces the manual web server and JSON bridge.
It packages the Python dependency and the locked OpenMCT browser assets. The
flight process still runs on Windows with direct access to Crazyradio.
The root Dockerfile/docker-compose.yml are an older template; use the explicit
`-f compose.telemetry.yml` below.

Stop the previous native web server and fake bridge first (ports 8000 and 8765).
With Docker Desktop running, use Git Bash:

```bash
cd ~/amaze-dashboard
mkdir -p ../amaze-test-flight/telemetry
docker compose -f compose.telemetry.yml up --build -d
docker compose -f compose.telemetry.yml logs -f bridge
```

The telemetry bind mount is read-only inside the container. It must already
exist. Docker does not connect to Crazyradio and this image does not contain
cflib. It serves only the JSON-file or synthetic source.

In another Git Bash terminal, launch the flight when ready:

```bash
cd ~/amaze-test-flight
./.venv/Scripts/python.exe algorithms/reactive_nav.py --fly --goal 2.0 0.0 --height 0.45 --uri radio://0/80/2M/E7E7E7E7E7 --diag
```

Open `http://localhost:8000/dashboard/`, hard refresh after updates, and choose
Crazyflie -> Position X or Position Y. The bottom time controls select realtime
or fixed time. After a flight, use the Time Conductor Settings gear, select fixed
time, and enter UTC start/end times covering that flight. Stored values keep
their original timestamps; they do not move into the current live window.

To stop the two demo containers:

```bash
docker compose -f compose.telemetry.yml down
```

The host JSON files remain on disk. **Archive the telemetry directory before
starting another flight:** the current writer initializes fresh X/Y arrays and
replaces those two files at the next flight start. To inspect an archived folder,
set `TELEMETRY_DIR` to its absolute path before starting Compose.

## Repeatable tests (no hardware)

From the flight worktree, using the existing venv and Node:

```bash
cd ~/amaze-test-flight
./.venv/Scripts/python.exe -m unittest algorithms.test_reactive_nav dev_scripts.test_telemetry_integration -v
node --test dev_scripts/test_telemetry_plugin.cjs
node dev_scripts/test_telemetry_browser.cjs
```

Browser testing uses Chrome and `playwright-core` installed in the dashboard's
`openmct-tutorial/node_modules`. On another machine, install the test dependency
with `npm --prefix ../amaze-dashboard/openmct-tutorial install --no-save playwright-core`.
Set `CHROME_PATH`, `FLIGHT_PYTHON`, and/or `DASHBOARD_ROOT` to override the Windows
defaults. `npm ci` removes the temporary Playwright install, so reinstall it
after running that command if needed.

After building the demo image, run the same browser test against containers:

```bash
TELEMETRY_E2E_DOCKER=1 node dev_scripts/test_telemetry_browser.cjs
```

Tests use temporary JSON files, random local ports, and uniquely named Docker
projects. They clean up their own processes/containers and never run `--fly`.
The browser test compares both metrics' exact values/timestamps, tests delayed
bridge startup, live batches, bridge restart/backfill, saved history after page
refresh, and rendered blue graph pixels. Python/JS regressions also cover corrupt
input, missing/locked files, Windows rename retry, invalid numeric values, duplicate
timestamps, file reset, bounded queues, multiple clients/subscribers, timeout,
and slow-client isolation. Root `test.py` is deliberately excluded (it deletes files).

## Limits of this demo

- This is the two-position-metric demo requested for this personal branch; the
  older `SPEC.md` describes a different four-metric bridge contract.
- Up to 100,000 saved samples per metric are exposed by the bridge (about 83
  minutes at the flight logger's 20 Hz). The writer still stores the whole file.
- History requests share the WebSocket with live updates; there is no REST API.
- Sustained filesystem errors disable export and print an error in the flight
  terminal. That does not stop the flight controller. Individual X and Y file
  replacements are atomic; the pair is not a cross-file transaction.
- These are hardware-free integration tests. Sensor accuracy, radio dropouts,
  long-flight disk performance, and flight behavior still require hardware tests.
- Docker/npm reported existing dependency audit findings. The image is a local
  demo, not a production-hardened deployment; no blanket dependency upgrade was
  performed as part of this integration repair.
