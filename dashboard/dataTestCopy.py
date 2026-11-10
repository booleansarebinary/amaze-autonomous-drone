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
        print("[QUEUE] Telemetry added to queue.")

    except queue.Full:
        try:
            telemetry_queue.get_nowait()
            print("[QUEUE] Removed old telemetry.")

        except queue.Empty:
            pass

        telemetry_queue.put_nowait(message)
        print("[QUEUE] Latest telemetry added to queue.")


def collect_telemetry():
    """
    Connect to the Crazyflie and collect telemetry continuously.
    Runs in a separate thread because SyncLogger blocks.
    """
    cflib.crtp.init_drivers()
    print("[INIT] Crazyflie drivers initialized.")

    log_config = LogConfig(
        name="Telemetry",
        period_in_ms=100
    )

    log_config.add_variable("pm.vbat", "float")
    log_config.add_variable("stabilizer.roll", "float")
    log_config.add_variable("stabilizer.pitch", "float")
    log_config.add_variable("stabilizer.yaw", "float")

    print(f"[CONNECT] Connecting to Crazyflie at {URI}...")

    try:
        with SyncCrazyflie(
            URI,
            cf=Crazyflie(rw_cache="./cache")
        ) as scf:
            print("[SUCCESS] Crazyflie connected!")

            with SyncLogger(scf, log_config) as logger:
                print("[LOGGING] Waiting for telemetry data...")

                for timestamp, data, logconf in logger:
                    print("[RECEIVED] Telemetry received from Crazyflie:")
                    print(f"  Battery: {data['pm.vbat']} V")
                    print(f"  Roll:    {data['stabilizer.roll']}")
                    print(f"  Pitch:   {data['stabilizer.pitch']}")
                    print(f"  Yaw:     {data['stabilizer.yaw']}")

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

                    print("[JSON] Serialized telemetry:")
                    print(message)

                    save_latest_telemetry(message)

    except Exception as error:
        print(f"[ERROR] Crazyflie connection or logging failed: {error}")


async def handle_client(websocket):
    """
    Called whenever a dashboard connects to the WebSocket.
    """
    connected_clients.add(websocket)

    print(
        "[WEBSOCKET] Dashboard connected successfully! "
        f"Clients: {len(connected_clients)}"
    )

    try:
        await websocket.wait_closed()

    finally:
        connected_clients.discard(websocket)

        print(
            "[WEBSOCKET] Dashboard disconnected. "
            f"Clients: {len(connected_clients)}"
        )


async def broadcast_telemetry():
    """
    Get telemetry from the collector thread and send it
    to every connected dashboard.
    """
    while True:
        message = await asyncio.to_thread(telemetry_queue.get)

        print("[BROADCAST] Retrieved telemetry from queue.")

        if connected_clients:
            clients = list(connected_clients)

            print(
                f"[SEND] Sending telemetry to {len(clients)} dashboard(s)..."
            )

            results = await asyncio.gather(
                *[
                    client.send(message)
                    for client in clients
                ],
                return_exceptions=True
            )

            for client, result in zip(clients, results):
                if isinstance(result, Exception):
                    connected_clients.discard(client)
                    print(f"[SEND ERROR] Failed to send telemetry: {result}")
                else:
                    print("[SEND SUCCESS] Telemetry sent to dashboard.")

        else:
            print("[WAITING] No dashboards connected; telemetry not sent.")


async def run_websocket_server():
    print(
        f"[SERVER] Starting WebSocket server at "
        f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"
    )

    async with serve(
        handle_client,
        WEBSOCKET_HOST,
        WEBSOCKET_PORT
    ):
        print("[SERVER] WebSocket server is running!")
        await broadcast_telemetry()


def main():
    print("[STARTUP] Starting telemetry collector thread...")

    telemetry_thread = threading.Thread(
        target=collect_telemetry,
        daemon=True
    )

    telemetry_thread.start()

    try:
        asyncio.run(run_websocket_server())

    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Telemetry and WebSocket server stopped.")


if __name__ == "__main__":
    main()