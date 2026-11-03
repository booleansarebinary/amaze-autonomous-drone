# Crazyflie telemetry bridge

This Python process reads telemetry from a Crazyflie over Crazyradio and makes
it available to the React dashboard at `ws://localhost:8765`.

From the project root, create a virtual environment and install the bridge:

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` on Windows PowerShell or
`source .venv/bin/activate` on macOS/Linux, then run:

```bash
pip install -r server/requirements.txt
python server/crazyflie_bridge.py
```

Copy `.env.example` to `.env.local` so Vite connects to the bridge. Restart the
local Vite process after changing the environment file.

The bridge URI defaults to `radio://0/80/2M/E7E7E7E7E7`. Update `URI` in
`crazyflie_bridge.py` if your Crazyflie uses a different radio address.

## Test without a drone

Run the dummy server instead of `crazyflie_bridge.py`:

```bash
python server/dummyTest.py
```

Open the dashboard and select **Dummy feed** in the top bar. The button connects
to `VITE_DUMMY_TELEMETRY_URL`, which defaults to `ws://localhost:8765`. The
dummy server and real bridge use the same port, so run only one at a time.
