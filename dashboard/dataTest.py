"""Read-only, two-metric telemetry bridge for the OpenMCT demo page."""
import argparse
import asyncio
import json
import math
import queue
import threading
import time
from pathlib import Path

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed


DEFAULT_URI = "radio://0/80/2M/E7E7E7E7E7"
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8765
METRICS = ("drone.position.x", "drone.position.y")
MAX_HISTORY = 100_000  # per metric; over 2 hours at the flight's 10 Hz


def valid_point(key, sample):
    """Return a strict browser-safe point, or None for corrupt input."""
    if key not in METRICS or not isinstance(sample, dict):
        return None
    timestamp, value = sample.get("timestamp"), sample.get("value")
    if (type(timestamp) is not int or not 0 <= timestamp <= 8_640_000_000_000_000
            or type(value) not in (int, float)):
        return None
    try:
        if not math.isfinite(value):
            return None
        return {"id": key, "timestamp": timestamp, "value": float(value)}
    except OverflowError:
        return None


class TelemetryBridge:
    def __init__(self):
        self.queue = queue.Queue(maxsize=1024)
        self.clients = {}
        self.history = {key: {} for key in METRICS}
        self.lock = threading.Lock()

    def get_history(self, key, start, end):
        with self.lock:
            return [point.copy() for timestamp, point in sorted(self.history.get(key, {}).items())
                    if start <= timestamp <= end]

    def _enqueue(self, point):
        message = json.dumps(point, allow_nan=False)
        while True:
            try:
                self.queue.put_nowait(message)
                return
            except queue.Full:
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass

    def publish_value(self, key: str, timestamp: int, value: float):
        """Queue one OpenMCT-compatible value without touching the radio."""
        point = valid_point(key, {"timestamp": timestamp, "value": value})
        if point is None:
            return
        with self.lock:
            history = self.history[key]
            if history.get(timestamp) == point:
                return
            history[timestamp] = point
            if len(history) > MAX_HISTORY:
                del history[next(iter(history))]
        self._enqueue(point)

    def publish_sample(self, x: float, y: float, timestamp: int | None = None):
        timestamp = int(time.time() * 1000) if timestamp is None else timestamp
        for key, value in ((METRICS[0], x), (METRICS[1], y)):
            self.publish_value(key, timestamp, value)

    def collect_from_crazyflie(self, uri: str):
        """Read Flow-deck position only; this bridge never sends commands."""
        import cflib.crtp
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.log import LogConfig
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
        from cflib.crazyflie.syncLogger import SyncLogger

        cflib.crtp.init_drivers()
        log_config = LogConfig(name="position", period_in_ms=100)
        log_config.add_variable("kalman.stateX", "float")
        log_config.add_variable("kalman.stateY", "float")
        print(f"Connecting read-only telemetry bridge to {uri}...")
        try:
            with SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache")) as scf:
                with SyncLogger(scf, log_config) as logger:
                    for _drone_timestamp, data, _log_config in logger:
                        self.publish_sample(data["kalman.stateX"], data["kalman.stateY"])
        except Exception as error:
            print(f"Crazyflie telemetry error: {error}")

    def collect_fake(self):
        """Produce moving X/Y values so the full dashboard can be checked safely."""
        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            self.publish_sample(math.cos(elapsed / 2), math.sin(elapsed / 2))
            time.sleep(0.1)

    def poll_json_once(self, directory: Path):
        """Read every new point, keeping saved history for late/reconnecting views."""
        directory = Path(directory)
        files = {
            METRICS[0]: directory / "kalman_state_x.json",
            METRICS[1]: directory / "kalman_state_y.json",
        }
        for key, path in files.items():
            try:
                samples = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeError):
                # Atomic file replacement on Windows can briefly deny access.
                # Preserve the last good history and retry on the next poll.
                continue
            if not isinstance(samples, list):
                continue
            points = {}
            for sample in samples[-MAX_HISTORY:]:
                point = valid_point(key, sample)
                if point is not None:
                    points[point["timestamp"]] = point
            with self.lock:
                previous = self.history[key]
                changed = [point for timestamp, point in sorted(points.items())
                           if previous.get(timestamp) != point]
                self.history[key] = points
            for point in changed:
                self._enqueue(point)

    def collect_from_json_files(self, directory: Path):
        """Only read files; reactive_nav.py remains the sole radio owner."""
        print(f"Reading flight telemetry from {directory.resolve()}")
        while True:
            self.poll_json_once(directory)
            time.sleep(0.05)

    async def _send_client(self, websocket, outgoing):
        while True:
            message = await outgoing.get()
            try:
                await asyncio.wait_for(websocket.send(message), timeout=2)
            except (TimeoutError, ConnectionClosed):
                # A blocked client must not hold up other viewers.
                await websocket.close(code=1013, reason="Reconnect to recover telemetry history")
                return

    async def handle_client(self, websocket):
        outgoing = asyncio.Queue(maxsize=1024)
        self.clients[websocket] = outgoing
        sender = asyncio.create_task(self._send_client(websocket, outgoing))
        print(f"Dashboard connected ({len(self.clients)} client(s)).")
        try:
            async for raw in websocket:
                try:
                    request = json.loads(raw)
                    if not isinstance(request, dict) or request.get("type") != "history":
                        continue
                    key = request.get("id")
                    start, end = request.get("start"), request.get("end")
                    if (key not in METRICS or type(start) not in (int, float)
                            or type(end) not in (int, float)
                            or not math.isfinite(start) or not math.isfinite(end)):
                        continue
                    response = {"type": "history", "requestId": request.get("requestId"),
                                "points": self.get_history(key, start, end)}
                    # History replies aren't silently dropped. Disconnect a
                    # saturated client so its pending request can be retried.
                    outgoing.put_nowait(json.dumps(response, allow_nan=False))
                except (ValueError, TypeError, OverflowError):
                    continue
                except asyncio.QueueFull:
                    await websocket.close(code=1013, reason="Telemetry client too slow")
                    break
        except ConnectionClosed:
            pass
        finally:
            self.clients.pop(websocket, None)
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    async def broadcast(self):
        while True:
            # No blocking worker thread left behind on shutdown.
            for _ in range(1024):
                try:
                    message = self.queue.get_nowait()
                except queue.Empty:
                    break
                for websocket, outgoing in list(self.clients.items()):
                    try:
                        outgoing.put_nowait(message)
                    except asyncio.QueueFull:
                        self.clients.pop(websocket, None)
                        asyncio.create_task(websocket.close(code=1013, reason="Telemetry client too slow"))
            await asyncio.sleep(0.01)

    async def serve(self, host=WEBSOCKET_HOST, port=WEBSOCKET_PORT):
        async with serve(self.handle_client, host, port):
            print(f"Telemetry WebSocket: ws://{host}:{port}")
            await self.broadcast()


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--fake", action="store_true", help="use synthetic X/Y values")
    source.add_argument("--json-dir", type=Path, metavar="DIRECTORY",
                        help="read X/Y JSON files produced by reactive_nav.py --fly")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--host", default=WEBSOCKET_HOST)
    parser.add_argument("--port", type=int, default=WEBSOCKET_PORT)
    args = parser.parse_args()

    bridge = TelemetryBridge()
    if args.fake:
        collector = bridge.collect_fake
    elif args.json_dir:
        collector = lambda: bridge.collect_from_json_files(args.json_dir)
    else:
        collector = lambda: bridge.collect_from_crazyflie(args.uri)
    threading.Thread(target=collector, daemon=True).start()
    try:
        asyncio.run(bridge.serve(args.host, args.port))
    except KeyboardInterrupt:
        print("Telemetry bridge stopped.")


if __name__ == "__main__":
    main()
