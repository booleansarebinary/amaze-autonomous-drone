"""Broadcast simulated Crazyflie telemetry for dashboard testing."""

import asyncio
import json
import math
import time

from websockets.asyncio.server import serve


WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8765
UPDATE_PERIOD_SECONDS = 0.1

connected_clients = set()


async def handle_client(websocket) -> None:
    """Register a dashboard until its WebSocket connection closes."""
    connected_clients.add(websocket)
    print(f"Dashboard connected. Clients: {len(connected_clients)}")

    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"Dashboard disconnected. Clients: {len(connected_clients)}")


def generate_dummy_telemetry(elapsed_seconds: float) -> dict:
    """Generate the same JSON format as the real Crazyflie bridge."""
    battery_voltage = max(3.0, 4.2 - elapsed_seconds * 0.0005)
    roll = (
        math.sin(elapsed_seconds * 1.2) * 12
        - math.sin(elapsed_seconds * 3.1) * 1.5
    )
    pitch = math.sin(elapsed_seconds * 0.8 + 1.0) * 8
    yaw = (elapsed_seconds * 15) % 360

    return {
        "utc": int(time.time() * 1000),
        "crazyflie_timestamp": int(elapsed_seconds * 1000),
        "values": {
            "drone.battery.voltage": battery_voltage,
            "drone.attitude.roll": roll,
            "drone.attitude.pitch": pitch,
            "drone.attitude.yaw": yaw,
        },
    }


async def broadcast_dummy_telemetry() -> None:
    """Generate and broadcast dummy telemetry every 100 milliseconds."""
    start_time = time.monotonic()
    message_count = 0

    while True:
        elapsed_seconds = time.monotonic() - start_time
        message = json.dumps(generate_dummy_telemetry(elapsed_seconds))

        if connected_clients:
            clients = tuple(connected_clients)
            results = await asyncio.gather(
                *(client.send(message) for client in clients),
                return_exceptions=True,
            )
            for client, result in zip(clients, results):
                if isinstance(result, Exception):
                    connected_clients.discard(client)

        if message_count % 10 == 0:
            print(message)

        message_count += 1
        await asyncio.sleep(UPDATE_PERIOD_SECONDS)


async def run_websocket_server() -> None:
    print(
        "Dummy telemetry server running at "
        f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}",
    )
    print("No Crazyflie connection required.")
    print("Press Ctrl+C to stop.")

    async with serve(handle_client, WEBSOCKET_HOST, WEBSOCKET_PORT):
        await broadcast_dummy_telemetry()


def main() -> None:
    try:
        asyncio.run(run_websocket_server())
    except KeyboardInterrupt:
        print("\nDummy telemetry server stopped.")


if __name__ == "__main__":
    main()
