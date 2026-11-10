"""Stream Crazyflie telemetry to the dashboard over a local WebSocket."""

import asyncio
import json
import queue
import threading
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger
from websockets.asyncio.server import serve

URI = "radio://0/80/2M/E7E7E7E7E7"
WEBSOCKET_HOST = "0.0.0.0"
WEBSOCKET_PORT = 8765

telemetry_queue: queue.Queue[str] = queue.Queue(maxsize=1)
connected_clients = set()


def save_latest_telemetry(message: str) -> None:
    """Keep only the newest sample when the dashboard falls behind."""
    try:
        telemetry_queue.put_nowait(message)
    except queue.Full:
        try:
            telemetry_queue.get_nowait()
        except queue.Empty:
            pass
        telemetry_queue.put_nowait(message)


def collect_telemetry() -> None:
    """Collect blocking Crazyflie log data in a dedicated thread."""
    cflib.crtp.init_drivers()

    log_config = LogConfig(name="Telemetry", period_in_ms=100)
    log_config.add_variable("pm.vbat", "float")
    log_config.add_variable("stabilizer.roll", "float")
    log_config.add_variable("stabilizer.pitch", "float")
    log_config.add_variable("stabilizer.yaw", "float")

    print(f"Connecting to Crazyflie at {URI}...")

    try:
        with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./.cache/crazyflie")) as scf:
            print("Crazyflie connected!")

            with SyncLogger(scf, log_config) as logger:
                for timestamp, data, _log_config in logger:
                    telemetry = {
                        "utc": int(time.time() * 1000),
                        "crazyflie_timestamp": timestamp,
                        "values": {
                             "drone.battery.voltage": round(data["pm.vbat"], 1),
                             "drone.attitude.roll": round(data["stabilizer.roll"], 1),
                             "drone.attitude.pitch": round(data["stabilizer.pitch"], 1),
                             "drone.attitude.yaw": round(data["stabilizer.yaw"], 1),
},
                    }

                    message = json.dumps(telemetry)
                    print(message)
                    save_latest_telemetry(message)
    except Exception as error:
        print(f"\nCrazyflie error: {error}")


async def handle_client(websocket) -> None:
    """Track a dashboard connection until it closes."""
    connected_clients.add(websocket)
    print(f"Dashboard connected. Clients: {len(connected_clients)}")

    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"Dashboard disconnected. Clients: {len(connected_clients)}")


async def broadcast_telemetry() -> None:
    """Send each fresh telemetry sample to all connected dashboards."""
    while True:
        message = await asyncio.to_thread(telemetry_queue.get)

        if connected_clients:
            clients = tuple(connected_clients)
            results = await asyncio.gather(
                *(client.send(message) for client in clients),
                return_exceptions=True,
            )
            for client, result in zip(clients, results):
                if isinstance(result, Exception):
                    connected_clients.discard(client)


async def run_websocket_server() -> None:
    print(f"WebSocket server running at ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")

    async with serve(handle_client, WEBSOCKET_HOST, WEBSOCKET_PORT):
        await broadcast_telemetry()


def main() -> None:
    telemetry_thread = threading.Thread(target=collect_telemetry, daemon=True)
    telemetry_thread.start()

    try:
        asyncio.run(run_websocket_server())
    except KeyboardInterrupt:
        print("\nTelemetry and WebSocket server stopped.")


if __name__ == "__main__":
    main()
