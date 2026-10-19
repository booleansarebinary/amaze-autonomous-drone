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
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8765

telemetry_queue = queue.Queue(maxsize=1)

connected_clients = set()

def save_latest_telemetry(message):
    try:
        telemetry_queue.put_nowait(message)

    except queue.Full:
        try:
            telemetry_queue.get_nowait()
        except queue.Empty:
            pass

        telemetry_queue.put_nowait(message)

def collect_telemetry():
    """
    Connect to the Crazyflie and collect telemetry continuously.

    This function runs in a separate thread because SyncLogger blocks
    while it waits for data.
    """
    cflib.crtp.init_drivers()

    log_config = LogConfig(
        name="Telemetry",
        period_in_ms=100
    )

    log_config.add_variable("pm.vbat", "float")
    log_config.add_variable("stabilizer.roll", "float")
    log_config.add_variable("stabilizer.pitch", "float")
    log_config.add_variable("stabilizer.yaw", "float")

    print(f"Connecting to Crazyflie at {URI}...")

    try:
        with SyncCrazyflie(
            URI,
            cf=Crazyflie(rw_cache="./cache")
        ) as scf:
            print("Crazyflie connected!")

            with SyncLogger(scf, log_config) as logger:
                for timestamp, data, logconf in logger:
                    telemetry = {
                        "utc": int(time.time() * 1000),
                        "crazyflie_timestamp": timestamp,
                        "values": {
                            "drone.battery.voltage": data["pm.vbat"],
                            "drone.attitude.roll": data["stabilizer.roll"],
                            "drone.attitude.pitch": data["stabilizer.pitch"],
                            "drone.attitude.yaw": data["stabilizer.yaw"]
                        }
                    }

                    message = json.dumps(telemetry)

                    print(message)
                    save_latest_telemetry(message)

    except Exception as error:
        print(f"\nCrazyflie error: {error}")


async def handle_client(websocket):
    """
    Called whenever a dashboard connects to the WebSocket.
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

async def broadcast_telemetry():
    """
    Wait for telemetry from the collector thread and send it
    to every connected dashboard.
    """
    while True:
        message = await asyncio.to_thread(telemetry_queue.get)

        if connected_clients:
            await asyncio.gather(
                *[
                    client.send(message)
                    for client in connected_clients
                ],
                return_exceptions=True
            )

async def run_websocket_server():
    print(
        f"WebSocket server running at "
        f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"
    )

    async with serve(
        handle_client,\
        
        WEBSOCKET_HOST,
        WEBSOCKET_PORT
    ):
        await broadcast_telemetry()



def main():
    telemetry_thread = threading.Thread(
        target=collect_telemetry,
        daemon=True
    )

    telemetry_thread.start()

    try:
        asyncio.run(run_websocket_server())

    except KeyboardInterrupt:
        print("\nTelemetry and WebSocket server stopped.")


if __name__ == "__main__":
    main()