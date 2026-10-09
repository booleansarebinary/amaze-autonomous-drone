# Drone Telemetry and OpenMCT Integration Handoff

Prepared for mentor and team review on October 9, 2026.

## What this work accomplished

This work connects the flight program's estimated X and Y positions to an OpenMCT graph. The flight program saves measurements as JSON files, a separate bridge reads those files, and the dashboard receives live updates. The dashboard can also request saved measurements to show a completed flight.

The complete software path passed automated tests on Windows and with the bridge and dashboard running in Docker. Those tests used controlled measurements sent through the actual JSON writer used by the flight program. **A physical flight was not performed as part of those tests.** Continuous collection from an airborne drone, radio reliability, sensor accuracy, and the effect of file writing on flight logging still need a supervised hardware test.

This is a working two-metric demonstration and a starting point for a shared integration design. It does not require the dashboard team to adopt these exact filenames, metric names, or API messages. We can adapt the backend, add a translation layer, or agree on a shared interface together.

## Where the work lives

There are two local working folders, each on a different branch:

| Folder on the development laptop | Branch | Purpose |
| --- | --- | --- |
| `C:\Users\victo\amaze-test-flight` | `test_drone_flight` | Flight program, JSON writer, and integration tests |
| `C:\Users\victo\amaze-dashboard` | `victor/telemetry-dashboard-demo` | Demo bridge, OpenMCT integration, and Docker launch files |

At the time of this handoff, the original JSON export is in flight commit `80561d1`, while the later writer fixes, new integration tests, and dashboard demo changes include uncommitted files. **Checking out a branch name alone will not retrieve uncommitted work.** Before someone tests on another computer, the maintainer needs to review, commit, and share both sets of changes, or provide complete copies of these working folders. No team branch was merged or pushed as part of this handoff.

The following comparison describes the original committed dashboard files in the local demo checkout. It is not a claim that every dashboard branch, including `oliviawu`, has the same gaps.

## What the original dashboard already had and what changed

The original code already included an OpenMCT startup page and a Python WebSocket collector. That collector opened the radio itself and sent battery voltage, roll, pitch, and yaw in a combined message. It was useful groundwork, but it was not yet connected to the two-position-metric flight workflow demonstrated here.

| Area | Original local dashboard or early demo behavior | Change in this integration |
| --- | --- | --- |
| Measurements | The original collector logged battery and attitude. | This demo exposes estimated Position X and Position Y in meters. Battery and attitude were not added to the two-metric demo. |
| OpenMCT measurement definitions | `dictionary-plugin.js` only printed an installation message. | Defined a Crazyflie folder, two measurement objects, units, and the time/value mapping needed by graphs. |
| Graph data connection | Realtime and history plugins were commented out in the original page. | Installed a provider that supplies live samples and answers saved-history requests. A provider is the small adapter OpenMCT uses to obtain data. |
| Application startup | The original page expected assets at paths that did not match this checkout. We also encountered a bundle that did not expose the expected browser object. | Corrected asset paths, added a loader, and made startup errors visible instead of leaving a blank page. |
| Time axis | An early demo used a time-field definition that did not match OpenMCT's UTC time system. | Mapped OpenMCT's `utc` domain to the incoming `timestamp` field. |
| Simultaneous flight and display | The original collector opened its own radio connection. | Added a JSON-file source so the existing flight program remains the only radio owner during flight. |
| Complete sample batches | An early JSON bridge read only the latest point, which could skip points between reads. | Compare file snapshots and forward newly seen or changed valid samples, with saved history available separately. |
| Reopening a graph | An early demo answered history requests with an empty list. | Return stored points in the requested time range and recover missed samples after reconnecting. |
| Error handling | Invalid messages, multiple subscribers, and temporary file locks exposed failures. | Added input validation, separate subscriber handling, bounded queues, slow-client isolation, and Windows file-replacement retries. |
| Reviewing a flight | The initial time window was 15 minutes, and the demo lacked convenient time controls. | Default to a one-minute live window and expose OpenMCT's time settings for fixed historical ranges. |
| Docker | The root Docker template was not wired to these services and tried to run a nonexistent `myapp` module. | Added a separate image and Compose file for the telemetry demo. |

The demo uses OpenMCT's existing plotting tools. It does not replace OpenMCT with a newly written plotting application, and it does not modify OpenMCT's source under `openmct/`.

### Main changed and added files

In the flight folder:

- `algorithms/reactive_nav.py`: contains the X/Y JSON exporter and its validation, file-error handling, and bounded Windows rename retries. The later integration fixes did not change the navigation movement logic.
- `dev_scripts/test_telemetry_integration.py`: tests the writer, file bridge, and WebSocket transport.
- `dev_scripts/test_telemetry_plugin.cjs`: tests the frontend telemetry provider.
- `dev_scripts/telemetry_e2e_fixture.py` and `dev_scripts/test_telemetry_browser.cjs`: run isolated browser tests with temporary files and optional Docker containers.

In the dashboard folder:

- `dashboard/dataTest.py`: implements the demo bridge and its file, fake-data, and standalone radio modes.
- `dashboard/dictionary-plugin.js`: defines the two measurements OpenMCT can display.
- `dashboard/realtime-telemetry-plugin.js`: connects OpenMCT to the live and historical WebSocket messages.
- `dashboard/openmct-loader.js`, `dashboard/index.html`, and root `index.html`: load the application, configure it, and provide the entry page.
- `compose.telemetry.yml`, `dashboard/Dockerfile.demo`, and `dashboard/Dockerfile.demo.dockerignore`: build and launch the demo services.
- `dashboard/requirements-demo.txt` and `dashboard/README.md`: list native dependencies and operating instructions.

## How the measurements reach the graph

```text
Crazyflie with Flow deck
        |
        | Crazyradio connection
        v
Flight program running on Windows
        |
        | Existing logging callback receives estimated X and Y
        v
telemetry/kalman_state_x.json and telemetry/kalman_state_y.json
        |
        | Bridge reads the shared folder
        v
Telemetry bridge, running natively or in Docker
        |
        | WebSocket messages on port 8765
        v
OpenMCT in the browser, served on port 8000
```

The flight logger requests measurements every 50 milliseconds, or nominally 20 times per second. This is a configured rate, not a measured guarantee of delivery during flight. The callback records `kalman.stateX` and `kalman.stateY`, with the same host-generated UTC timestamp for both values. The timestamp is milliseconds since the Unix epoch; it is not the drone's boot-time clock or an exact sensor-acquisition time.

Each file contains a JSON array. For example, one X-position sample looks like this:

```json
[
  {"timestamp": 1791521255000, "value": 1.25}
]
```

The bridge checks the files approximately every 50 milliseconds. It reads data only; it does not send motion commands. In Docker, the telemetry folder is mounted read-only, so the container can read the files but cannot overwrite them.

Position X and Position Y are estimator coordinates in meters. They are not GPS coordinates or guaranteed physical ground truth. The flight command's goal is a displacement from the measured takeoff origin; the graph shows the raw estimator coordinates. Therefore a two-meter X goal does not necessarily produce a graph starting at exactly zero and ending at exactly two.

## What kind of API was built

An API is the agreed way two programs exchange information. This demo implements a **custom JSON-over-WebSocket API**, not a REST API.

A WebSocket keeps a connection open so the bridge can send measurements as they become available. The same connection also carries requests for saved measurements. HTTP on port 8000 serves the webpage and its files; it does not provide a telemetry REST service.

| Interface | Address or operation | Purpose |
| --- | --- | --- |
| Dashboard webpage | `http://localhost:8000/dashboard/` | Open the graph application in a browser. |
| Live data connection | `ws://localhost:8765` | Receive individual X/Y samples. |
| Saved data request | A `history` message on that same WebSocket | Ask for one metric between two timestamps. |
| Measurement definitions | `dashboard/dictionary-plugin.js` | Tell OpenMCT which measurements exist and how to interpret them. These are currently defined in JavaScript, not served by `/dictionary`. |

Example live message:

```json
{"id":"drone.position.x","timestamp":1791521255000,"value":1.25}
```

Here, `id` identifies the measurement, `timestamp` says when the host recorded it, and `value` is the position in meters. Y uses `drone.position.y`.

Example history request from the dashboard:

```json
{"type":"history","requestId":"review-1","id":"drone.position.x","start":1791521254000,"end":1791521256000}
```

Example response:

```json
{"type":"history","requestId":"review-1","points":[{"id":"drone.position.x","timestamp":1791521255000,"value":1.25}]}
```

The `requestId` lets the browser match the response to its request. The start and end bounds are inclusive. The bridge retains up to 100,000 points per metric for queries, about 83 minutes at a sustained 20 Hz. Saved JSON files are the underlying record; the bridge does not add a database.

There are no implemented telemetry endpoints such as `GET /history`, `GET /dictionary`, or `POST /telemetry`, and no takeoff, landing, or emergency-stop API. The older dashboard spec describes a different proposed contract; this demo should not be presented as an implementation of that whole spec.

## Why Docker is useful here

Docker packages an application with the software it needs into an image. A running instance of that image is a container. Docker Compose describes which containers to start and how they connect to folders and ports. Docker Desktop includes Compose on Windows. [Docker installation guidance](https://docs.docker.com/compose/install/).

The likely reason for using Docker as a team is to reduce differences between laptops and simplify startup. Instead of everyone separately configuring the bridge dependencies and dashboard assets, the demo builds one image and starts two services from it:

- `bridge` reads the flight JSON folder and exposes port 8765.
- `dashboard` serves the browser application on port 8000.

The image uses Python 3.12 and a pinned WebSocket dependency. It obtains OpenMCT browser assets from the tutorial's package lock. Node is used in the asset-building stage; it is not the runtime for the flight program.

The flight program remains on Windows with direct access to Crazyradio. This setup does not need to pass the USB dongle into Docker. Docker does not create sensor readings, verify the radio connection, or make the flight controller safe. It runs the supporting services consistently.

## Beginner setup before a live test

These commands are for **Git Bash on Windows**. Open Git Bash from the Start menu. Enter only the commands inside the blocks, not the terminal's `$` prompt or a line such as `victo@... MINGW64`.

### Get the complete code into the expected folders

Obtain the reviewed flight and dashboard changes described above. These instructions assume two sibling folders in your Windows user directory:

```text
C:\Users\YOUR_USERNAME\amaze-test-flight
C:\Users\YOUR_USERNAME\amaze-dashboard
```

In Git Bash, `~` means your user directory. Check the folders and branches:

```bash
cd ~/amaze-test-flight
pwd
git branch --show-current
git status --short
```

The expected flight branch is `test_drone_flight`. In another Git Bash window:

```bash
cd ~/amaze-dashboard
pwd
git branch --show-current
git status --short
```

The expected demo branch is `victor/telemetry-dashboard-demo`. Do not switch branches over unfinished local work just to match these names. Ask the maintainer for the reviewed version if the files or branches are missing. `fatal: not a git repository` usually means you are still in your home folder rather than inside a checkout; `pwd` tells you where you are.

### Install the software and prepare the drone connection

You need Git Bash, Python 3.10 or newer, Docker Desktop running Linux containers, and a browser. Install Docker Desktop using its [Windows setup instructions](https://docs.docker.com/desktop/setup/install/windows-install/). Follow any requested Windows or WSL setup and restart steps.

You also need the project's Crazyflie, its required Flow and Multi-ranger decks, Crazyradio, the configured radio URI, and the Windows USB driver for your radio. Follow [Bitcraze's Windows USB driver instructions](https://www.bitcraze.io/documentation/repository/crazyradio-firmware/master/building/usbwindows/). Complete the team's supervised flight-area and hardware checks before running `--fly`; that flag commands a real flight.

Close other programs connected to the same Crazyradio before flight, including a standalone telemetry collector or connected Crazyflie client. The flight script should be the only radio owner for this workflow.

### Prepare the flight Python environment

From the flight folder, check Python:

```bash
cd ~/amaze-test-flight
python --version
```

On a new checkout without a `.venv` folder, create a virtual environment. This is a project-specific place for Python packages:

```bash
python -m venv .venv
```

Skip that creation command if the provided environment already exists and works. Install the flight dependencies using that environment's Python:

```bash
./.venv/Scripts/python.exe -m pip install numpy cflib
./.venv/Scripts/python.exe -c "import numpy, cflib; print('Flight dependencies available')"
./.venv/Scripts/python.exe algorithms/reactive_nav.py --help
```

The help output should include `--fly`, `--goal`, `--height`, `--uri`, and `--diag`. These checks do not launch the drone. Using the explicit `.venv/Scripts/python.exe` path avoids accidentally running a different Python installation; activation is optional.

### Prepare Docker and the shared folder

Start Docker Desktop and wait until its engine is running. In the dashboard terminal:

```bash
cd ~/amaze-dashboard
docker version
docker compose version
mkdir -p ../amaze-test-flight/telemetry
```

`docker version` should show a server as well as a client. The `mkdir` command creates the telemetry folder if needed and does not clear existing files. The folder must exist before Docker mounts it.

Before using Docker, stop any old `python -m http.server 8000` server and `dataTest.py --fake` process. Use `Ctrl+C` in the terminal running each process. If a previous background process owns a port, identify it before stopping it; do not stop every Python process. Only one service can listen on each of ports 8000 and 8765 at a time.

## Live flight test using Docker

### Start the dashboard services in terminal one

```bash
cd ~/amaze-dashboard
docker compose -f compose.telemetry.yml up --build -d
docker compose -f compose.telemetry.yml ps
docker compose -f compose.telemetry.yml logs --tail 30 bridge
```

Keep the `-f compose.telemetry.yml` part: it chooses the working demo configuration instead of the older root template. `--build` rebuilds the image from the current files, and `-d` leaves the services running in the background. The first build needs internet access and may take longer while dependencies download.

The status output should show both `bridge` and `dashboard` running. Bridge logs should identify `/telemetry` as the source and port 8765 as the WebSocket listener. This Compose configuration selects **JSON-file mode**, not fake data or direct radio mode.

To watch connection messages continuously, run:

```bash
docker compose -f compose.telemetry.yml logs -f bridge
```

`Ctrl+C` here stops following the logs; it does not stop the detached containers.

### Open the graph before flight

Visit `http://localhost:8000/dashboard/` in the browser. Here, `localhost` means the same computer running Docker. This configuration is for local testing, not access from another teammate's laptop.

After a code update, press `Ctrl+Shift+R` to refresh scripts. Expand **Crazyflie**, select **Position X** or **Position Y**, and use **Realtime** mode in the bottom time controls. Opening the webpage does not launch the drone.

An empty graph before the first flight is normal. If recent files from a previous session exist, the graph may show those samples; the presence of a line alone does not prove that new measurements are arriving.

### Run the real flight in terminal two

Once the supervised hardware setup is ready:

```bash
cd ~/amaze-test-flight
./.venv/Scripts/python.exe algorithms/reactive_nav.py --fly --goal 2.0 0.0 --height 0.45 --uri radio://0/80/2M/E7E7E7E7E7 --diag
```

| Part of the command | Plain meaning |
| --- | --- |
| `--fly` | Connect to hardware and run the flight behavior. This is not a simulation. |
| `--goal 2.0 0.0` | Request a displacement of 2 meters along the controller's X coordinate and 0 along Y from the measured takeoff origin. |
| `--height 0.45` | Request a flight height of 0.45 meters. |
| `--uri radio://0/80/2M/E7E7E7E7E7` | Use this configured radio connection. It must match the team's actual drone setup. |
| `--diag` | Print position, heading, and command diagnostics. It does not enable JSON export; export is already part of this flight path. |

Run from `amaze-test-flight` so the relative `telemetry` path is the folder Docker reads. Do not also run `dataTest.py --uri ...` or bare `dataTest.py`; those modes open another radio connection. Do not run a fake source during a real-data test.

### Confirm that this run is collecting and displaying data

Have a second person monitor the dashboard while the flight operator attends to the drone. The display should show new samples as the flight callback writes them. A short delay is expected because data passes through logging, file writing, polling, and browser rendering; a maximum latency has not been established by a physical-flight test.

During the test, verify all three observations:

1. The flight terminal is printing fresh diagnostics.
2. `telemetry/kalman_state_x.json` and `telemetry/kalman_state_y.json` are receiving new timestamps and samples.
3. The corresponding OpenMCT graphs show new data at those times, with reasonable values in meters.

For a simple file check in a third Git Bash terminal, run the following twice a few seconds apart:

```bash
cd ~/amaze-test-flight
./.venv/Scripts/python.exe -c "import json; from pathlib import Path; [(print(p.name, 'samples=', len(s), 'latest=', s[-1] if s else None)) for p in sorted(Path('telemetry').glob('kalman_state_*.json')) for s in [json.loads(p.read_text())]]"
```

The sample counts and latest timestamps should advance. A brief read error can occur during Windows file replacement; rerun this manual check. The bridge itself retries file reads. Terminal diagnostics use takeoff-relative position while the saved values use raw estimator coordinates, so compare changes and timestamps rather than expecting both displays to have identical zero points.

If export prints `Telemetry JSON export disabled`, treat the data collection as failed even if the drone continues flying. Follow the team's flight procedure; stopping the dashboard or its containers is not a drone emergency-stop command.

### Review and preserve the flight after landing

Keep the JSON bridge running to view saved measurements. Use the bottom **Time Conductor Settings** gear, select **Fixed** time mode, and enter UTC start and end times covering the flight. The live window only covers the last minute by default; old samples do not move to the current time just because the page is reopened.

**Archive both files before the next flight.** The writer initializes fresh arrays at the next flight start and replaces the current X/Y files. After the flight process has finished, copy the folder with File Explorer or use:

```bash
cd ~/amaze-test-flight
mkdir -p flight-archives
cp -r telemetry "flight-archives/flight-$(date +%Y%m%d-%H%M%S)"
```

This creates a timestamped copy; it does not delete the working folder. Record the radio URI, command, flight time, operator, and any observed gaps alongside the saved files. Avoid committing generated flight data accidentally; these manually created archive folders are not automatically a team data-storage policy.

### Stop the services when finished

```bash
cd ~/amaze-dashboard
docker compose -f compose.telemetry.yml down
```

This stops and removes the demo containers and their network. It does not delete the host telemetry files. To start them again, repeat `docker compose -f compose.telemetry.yml up --build -d`.

## Alternative dashboard commands without Docker

Use this path instead of Docker, not alongside it on the same ports. The real-flight command is unchanged.

On first use, from the dashboard folder:

```bash
cd ~/amaze-dashboard
../amaze-test-flight/.venv/Scripts/python.exe -m pip install -r dashboard/requirements-demo.txt
npm.cmd --prefix openmct-tutorial ci
```

The second command requires Node and npm on Windows. With Docker, this asset setup happens inside the image instead. The native project has older dependency expectations, so the tested Docker build is the simpler setup for a new teammate.

In dashboard terminal one, start the JSON bridge:

```bash
cd ~/amaze-dashboard
../amaze-test-flight/.venv/Scripts/python.exe dashboard/dataTest.py --json-dir ../amaze-test-flight/telemetry
```

In dashboard terminal two, start the web server:

```bash
cd ~/amaze-dashboard
../amaze-test-flight/.venv/Scripts/python.exe -m http.server 8000
```

Keep both terminals open. Visit the same dashboard URL. Use a third terminal for the flight command. Stop the two dashboard processes with `Ctrl+C` after the flight and review are complete.

For a hardware-free visual check, replace the native bridge command with:

```bash
../amaze-test-flight/.venv/Scripts/python.exe dashboard/dataTest.py --fake
```

This produces synthetic X/Y curves near -1 to +1 meters. It proves that the live display can receive values, not that a drone is producing measurements. Stop it before selecting the real JSON source.

## What was tested and what remains to test

The work used test-driven development: write a regression for the intended behavior, observe it fail, implement the fix, and rerun the test. The browser test exposed a Windows file-replacement collision that separate component tests had missed; a specific regression and bounded retry were added for it.

Recorded results from the implementation verification:

| Test group | Result and scope |
| --- | --- |
| Python | 23 tests passed: 12 existing navigation/writer regressions and 11 new telemetry integration tests. |
| Frontend provider | 4 tests passed for malformed messages, multiple subscribers, history requests, retries, and timeouts. |
| Native browser integration | Passed with the actual writer, temporary JSON files, real bridge, OpenMCT, and rendered graph. |
| Docker browser integration | The same flow passed with the bridge and webpage in containers and the writer on Windows. |

The browser test compared 15 known samples for each metric, including exact timestamps and values. It covered opening the dashboard before the bridge, batches of live samples, bridge restart and recovery, refresh after data collection had stopped, fixed-time history, and visible graph pixels. Test processes used temporary folders and isolated ports, leaving real telemetry files alone.

Other regressions covered missing, empty, malformed, or inaccessible files; invalid numbers; duplicate or out-of-order timestamps; file reset; bounded queues; two clients; slow-client isolation; and a subscriber callback that fails. These checks cover identified failure cases, not every possible operating condition.

For a repeatable software check from `amaze-test-flight`:

```bash
./.venv/Scripts/python.exe -m pip install websockets==17.2
./.venv/Scripts/python.exe -m unittest algorithms.test_reactive_nav dev_scripts.test_telemetry_integration -v
node --test dev_scripts/test_telemetry_plugin.cjs
```

For the browser checks, install the test-only browser driver package and use an installed Chrome browser:

```bash
npm.cmd --prefix ../amaze-dashboard/openmct-tutorial install --no-save playwright-core
node dev_scripts/test_telemetry_browser.cjs
TELEMETRY_E2E_DOCKER=1 node dev_scripts/test_telemetry_browser.cjs
```

Build the Docker demo image before the Docker test. The test defaults expect adjacent checkout folders and Chrome at its usual Windows location. Set `CHROME_PATH`, `DASHBOARD_ROOT`, or `FLIGHT_PYTHON` if these differ. Installing tutorial dependencies again with `npm ci` removes the temporary Playwright installation, so reinstall it before browser testing. Do not run the repository's root `test.py` as a test-suite shortcut; it deletes files.

A hardware test still needs to establish whether samples arrive continuously while airborne, whether radio loss or estimator problems create gaps, and whether disk work affects logging timing. It should record duration, received sample counts, timestamp gaps, missing or invalid values, and the relationship between saved data and the graph. The expected 20 Hz configuration is a comparison point, not a pass result already obtained.

Current implementation limits also include full-array file rewrites on every sample, in-memory history limits, and separate atomic replacements for X and Y rather than one atomic transaction across both files. Persistent storage errors disable export. Existing dependency audit findings remain; the Docker stack is a local demo rather than a production-hardened deployment.

## Troubleshooting the test

| Symptom | What to check |
| --- | --- |
| `Cannot find a Crazyradio Dongle` | Check the physical radio connection, Windows driver, and whether another program owns the device. Docker does not fix USB discovery. |
| `unrecognized arguments: --diag` | Check the flight script version and folder with `pwd` and `--help`. Obtain the reviewed updated flight code. |
| Docker cannot connect to its server | Start Docker Desktop and wait for its engine; confirm `docker version` shows server information. |
| Port already in use | Stop the old native web server or fake bridge, or another known demo stack, before starting Compose. |
| Telemetry mount directory is missing | Run `mkdir -p ../amaze-test-flight/telemetry` from the dashboard folder and verify both folders are siblings. |
| Blank page or `openmct is not defined` | Use the reviewed loader/page files, build the current image, open the correct URL, and hard-refresh. Check browser console errors. |
| Graph is empty | Select a measurement rather than My Items, check source files and bridge logs, and choose a time window containing the samples. |
| Graph shows a smooth -1 to +1 curve regardless of the drone | Check for a fake source still running. The real workflow uses `--json-dir`. |
| Graph stops updating | Check latest file timestamps and the flight terminal for export errors before assuming the dashboard is at fault. |
| Missing `favicon.ico` message | This is a missing browser-tab icon; it does not explain missing telemetry. |

## Options for integrating with the team dashboard

The interface should be a joint decision based on what the dashboard already consumes and what the flight system can reliably provide. The two-metric demo is evidence that the data path is possible; it is not a reason to redesign the team's frontend around this particular bridge.

### Adapt the backend output to the existing dashboard

Have the dashboard team share a real example of the messages, identifiers, units, timestamps, and endpoints their current provider expects. Update the bridge to produce that format. For example, if the provider expects a combined `{utc, values}` message rather than separate `{id, timestamp, value}` messages, the bridge can translate the flight samples into that form.

This can preserve the existing dashboard connection code. The tradeoff is that the bridge needs a mapping to that dashboard contract, and new metrics may still need to be registered through the dashboard's existing mechanism.

### Add a small adapter between the two existing systems

Keep the flight exporter and the team's dashboard API as they are, and insert a translator that maps filenames or internal measurements to the dashboard's expected keys, time units, and message shape. The translator can live inside the backend service or as a separate component.

This keeps changes localized and lets each team continue independently. The tradeoff is one additional component to test and maintain. A simple mapping is preferable to maintaining two conflicting definitions of the same measurement.

### Agree on a shared telemetry contract

Write down one example message for a measurement and agree on metric names, units, coordinate origins, timestamps, live delivery, historical queries, and error behavior. Both sides implement and test that contract. A possible design is REST for metadata and saved history, plus WebSocket for live updates. That is a proposal for future work, not the API currently implemented by this demo.

This provides a clearer long-term boundary and makes it easier to add battery, attitude, and other measurements. It requires coordinated changes, so the team should choose the design together rather than treating either current implementation as mandatory.

### Choose the next integration step together

Start with a short review using the dashboard team's current runnable code and representative messages. Compare it with one X/Y sample from the flight exporter. Agree on which side should translate fields and which process owns the radio. Then add a shared test that feeds known samples through the agreed interface and checks the resulting graph.

The storage method is also negotiable. JSON files are convenient for today's inspection and replay; longer flights may benefit from a queued exporter, append-only recording, or a small database. Those changes can remain behind the agreed API so they do not require the dashboard layout to change.

The proposed acceptance point is a supervised short flight with archived JSON, advancing timestamps, and matching OpenMCT values, followed by a documented decision on the shared contract. Until that hardware run is completed, this work should be described as an automated, software-verified telemetry integration with hardware validation pending.
