# Dashboard Telemetry Bridge — Spec

**Status:** Draft, awaiting review
**Owner:** Dashboard team (backend)
**Scope of this spec:** the Python backend ("bridge") that reads Crazyflie telemetry and serves it to OpenMCT. The OpenMCT plugin is the frontend team's work and is out of scope, except for the contract it consumes (section 4).

> How to use this file: this is the single source of truth for the bridge. Humans read it top to bottom. AI agents should treat sections 4 (Contract), 5 (Acceptance Criteria), 6 (Out of Scope) and 9 (Repo Rules) as binding and must not invent requirements that are not listed here. If the code and this spec disagree, stop and reconcile them; do not silently pick one.

---

## 1. Overview

Crazyflie drone telemetry (battery, attitude) must appear live in the OpenMCT dashboard. A backend process runs in parallel to OpenMCT, listens to the drone, and exposes the data over two interfaces: a REST endpoint that describes the telemetry, and a WebSocket that streams values.

**First milestone goal:** the 4 variables from `dashboard/dataTest.py` stream from the drone (or a fake source) into OpenMCT and can be plotted live.

## 2. Architecture

```
Crazyflie --radio--> [Source thread] --> Hub (asyncio) --WS /realtime----> OpenMCT plugin
 (or FakeSource)      cflib callback      fan-out         GET /dictionary-> (frontend team)
```

| Component | Responsibility | Depends on |
|---|---|---|
| **Source** | Produces `Sample(timestamp, values)`. Two implementations: `CrazyflieSource` (cflib `LogConfig` callback API) and `FakeSource` (synthetic data, no hardware). | cflib (Crazyflie only) |
| **Hub** | Receives samples from the source thread, splits them into per-variable messages, fans out to all WS clients. One bounded queue per client; slow clients drop oldest messages. | Source |
| **API** | FastAPI app: `GET /dictionary`, `WS /realtime`. CORS enabled for the OpenMCT dev origin. | Hub, Config |
| **Config** | Drone URI, variable list, log period, host/port, CORS origin. Single place that defines the telemetry variables. | none |

Design rules:

- The variable list in Config is the only place variable names are defined. Both interfaces are generated from it.
- The cflib callback runs on cflib's thread. It may only build a `Sample` and hand it to the event loop via `loop.call_soon_threadsafe`. It must not touch asyncio objects directly.
- The bridge runs as its own process, alongside OpenMCT. It does not serve OpenMCT.

## 3. Telemetry variables (first milestone)

| Key | Display name | Unit | Format | Range |
|---|---|---|---|---|
| `pm.vbat` | Battery Voltage | V | `%.2f` | TBD |
| `stabilizer.roll` | Roll | deg | `%.2f` | TBD |
| `stabilizer.pitch` | Pitch | deg | `%.2f` | TBD |
| `stabilizer.yaw` | Yaw | deg | `%.2f` | TBD |

Variables to add: thrust, speed, position x/y/z, distance from start, and deck sensors (Flow Deck v2, Multi-Ranger).

Log period: 100 ms. All four are `float` and fit in one 26-byte log packet. Adding variables beyond one packet's capacity requires additional `LogConfig`s (out of scope now).

## 4. Contract

The two interfaces are one contract. They are joined by `key`.

**Key rule:** every `key` that appears on the WebSocket MUST appear in the dictionary. A client MUST ignore WS messages whose key it does not know.

### 4.1 `GET /dictionary`

Returns `200` with JSON:

```json
{
  "measurements": [
    {
      "key": "pm.vbat",
      "name": "Battery Voltage",
      "unit": "V",
      "format": "%.2f"
    }
  ]
}
```

`min` and `max` (numbers) are optional fields, present only once the team confirms ranges.

Static for the lifetime of the process. Available whether or not the drone is connected.

### 4.2 `WS /realtime`

Server-to-client only. The bridge ignores any message a client sends. Each message is one JSON text frame containing one value for one variable:

```json
{"key": "stabilizer.roll", "timestamp": 1790000000123, "value": 1.23}
```

- `timestamp`: integer, milliseconds since Unix epoch, UTC. Stamped by the bridge on arrival of the sample, **not** the drone's boot-relative timestamp.
- `value`: JSON number.
- All variables from the same sample share the same `timestamp`.
- The stream starts immediately on connect. There is no subscribe handshake and no per-key filtering: every client receives every variable. Clients filter by `key`.

### 4.3 Defaults

Bridge listens on `0.0.0.0:8000`. CORS allows `http://localhost:8080` (OpenMCT dev server). Both configurable.

## 5. Acceptance Criteria

Each criterion should be verifiable by an automated test using `FakeSource` unless marked **[HW]**.

1. **Dictionary served.** `GET /dictionary` returns the measurements in section 3 with all fields in 4.1.
2. **Dictionary independent of drone.** `GET /dictionary` succeeds when the source is disconnected or has never connected.
3. **Stream format.** A WS client connecting to `/realtime` receives frames matching 4.2 with no handshake.
4. **Rate.** With a 100 ms period, each variable arrives about every 100 ms (tolerance: +/- 50 ms average over 5 s).
5. **Key rule.** Every `key` seen on the WS over a 5 s run is present in the dictionary.
6. **Timestamps.** `timestamp` is within 1 s of the host's current UTC time and non-decreasing per key.
7. **Fan-out.** Two simultaneous WS clients each receive the full stream.
8. **Slow client isolation.** A client that stops reading does not delay other clients and does not grow bridge memory without bound.
9. **Fake mode.** `--fake` runs the full pipeline with no cflib link and no Crazyradio.
10. **[HW] Real drone.** With a powered Crazyflie and Crazyradio, values on the WS match the values printed by `dashboard/dataTest.py` within normal sample variation.
11. **[HW] Drone loss.** If the radio link drops, the API stays up, the source retries with backoff, and streaming resumes when the drone returns.
12. **CORS.** A browser page on the configured origin can call `GET /dictionary` and open the WS without CORS errors.

## 6. Out of Scope

- The OpenMCT plugin, providers, and any change to `openmct/` (frontend team).
- Historical data: no storage, no `/history` endpoint. Plots start empty and fill live.
- Sending commands to the drone. The bridge is read-only for this milestone. The team's Notion ("9/21/26") lists start/stop mission and an abort button (drone safely lands) as future dashboard features; they need their own spec and safety review.
- Authentication, TLS, multi-drone support.
- Per-client subscription filtering.
- More than one `LogConfig` / variables beyond section 3.
- Dictionary changes at runtime (restart the bridge to change variables).
- A `status` message for drone connectivity (see Open Questions).

## 7. Edge Cases

- **Drone unreachable at startup:** API starts anyway; source retries with backoff; WS clients connect and receive nothing until data flows.
- **Drone lost mid-run:** same as above; no crash, no partial frames.
- **Client disconnects abruptly:** its queue is removed; no error propagates to other clients.
- **No clients connected:** samples are discarded, not buffered.
- **cflib TOC cache:** cflib writes/reads the log TOC cache. The path must be configurable and default to `./cache` (matching `dataTest.py`), so running from the repo root works.
- **Timestamp wrap/reset:** irrelevant by design; the drone timestamp is not used.
- **Unknown log variable** (name not on the firmware): fail fast at startup with a clear error naming the variable.

## 8. Configuration

Defaults (all overridable by CLI flag or environment variable; exact names decided at implementation):

| Setting | Default |
|---|---|
| Drone URI | `radio://0/80/2M/E7E7E7E7E7` |
| Log period (ms) | `100` |
| Host / port | `0.0.0.0` / `8000` |
| CORS origin | `http://localhost:8080` |
| cflib cache dir | `./cache` |
| Source | Crazyflie (`--fake` selects FakeSource) |

## 9. Repo Rules

- **Language/tooling:** Python >=3.10, managed with `uv`. New dependencies (proposed): `fastapi`, `uvicorn`; dev: `pytest`, an async test client (`httpx`, plus WS testing via FastAPI's `TestClient`). Add them with `uv add`, not by editing `pyproject.toml` by hand.
- **Location:** `dashboard/bridge/`. `dashboard/dataTest.py` stays untouched as a reference.
- **Team workflow:** start with `docker compose up --build`; add Python packages with `uv add [package]`. NOTE: the current `Dockerfile` is a broken template (python:3.9, runs nonexistent `myapp`), so Docker support for the bridge needs fixing as part of implementation.
- **Run (proposed, from repo root):**
  - `uv run python -m dashboard.bridge --fake`
  - `uv run python -m dashboard.bridge --uri radio://0/80/2M/E7E7E7E7E7`
  - `uv run pytest dashboard`
- **Testing:** every acceptance criterion not marked [HW] gets an automated test against `FakeSource`. Tests must not require hardware or network beyond localhost.
- **Do not edit** anything under `openmct/` from backend work.
- **Do not run** root `test.py` (it deletes files).
- **Commits:** the human author writes commit messages. Agents propose, humans commit.
- **Flight safety:** the bridge never sends control commands; keep it that way.

## 10. Open Questions

1. Should the bridge emit a `status` message (drone connected/lost) on the WS so OpenMCT can show staleness? Currently out of scope.  
