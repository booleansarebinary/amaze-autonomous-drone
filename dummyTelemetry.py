import asyncio
import json
import math
import time

from websockets.asyncio.server import serve


WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8765
UPDATE_PERIOD_SECONDS = 0.1

connected_clients = set()


async def handle_client(websocket):
    """
    Register a dashboard when it connects and remove it when it disconnects.
    """
    connected_clients.add(websocket)

    print(
        "Dashboard connected. "
        f"Clients: {len(connected_clients)}"
    )

    try:
        await websocket.wait_closed()

    finally:
        connected_clients.discard(websocket)

        print(
            "Dashboard disconnected. "
            f"Clients: {len(connected_clients)}"
        )


def generate_dummy_telemetry(elapsed_seconds):
    """
    Generate simulated Crazyflie values using the same JSON format
    as the real telemetry program.
    """
    battery_voltage = max(
        3.2,
        4.2 - elapsed_seconds * 0.0005
    )

    roll = (
        math.sin(elapsed_seconds * 1.2) * 12
        + math.sin(elapsed_seconds * 3.1) * 1.5
    )

    pitch = (
        math.sin(elapsed_seconds * 0.8 + 1.0) * 8
    )

    yaw = (
        elapsed_seconds * 15
    ) % 360

    telemetry = {
        "utc": int(time.time() * 1000),
        "crazyflie_timestamp": int(elapsed_seconds * 1000),
        "values": {
            "drone.battery.voltage": battery_voltage,
            "drone.attitude.roll": roll,
            "drone.attitude.pitch": pitch,
            "drone.attitude.yaw": yaw
        }
    }

    return telemetry


async def broadcast_dummy_telemetry():
    """
    Generate and broadcast dummy telemetry every 100 milliseconds.
    """
    start_time = time.monotonic()
    message_count = 0

    while True:
        elapsed_seconds = time.monotonic() - start_time

        telemetry = generate_dummy_telemetry(elapsed_seconds)
        message = json.dumps(telemetry)

        if connected_clients:
            await asyncio.gather(
                *[
                    client.send(message)
                    for client in list(connected_clients)
                ],
                return_exceptions=True
            )

        # Print approximately once per second instead of ten times per second.
        if message_count % 10 == 0:
            print(message)

        message_count += 1

        await asyncio.sleep(UPDATE_PERIOD_SECONDS)


async def run_websocket_server():
    print(
        "Dummy telemetry server running at "
        f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"
    )

    print("No Crazyflie connection required.")
    print("Press Ctrl+C to stop.")

    async with serve(
        handle_client,
        WEBSOCKET_HOST,
        WEBSOCKET_PORT
    ):
        await broadcast_dummy_telemetry()


def main():
    try:
        asyncio.run(run_websocket_server())

    except KeyboardInterrupt:
        print("\nDummy telemetry server stopped.")


if __name__ == "__main__":
    main()