"""Hardware-free regression tests against the real flight writer and demo bridge.

Run from the flight repo: python -m unittest dev_scripts.test_telemetry_integration -v
Set DASHBOARD_ROOT only when running these tests against a separate dashboard checkout.
"""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from algorithms.reactive_nav import TelemetryJsonWriter
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = Path(os.environ.get('DASHBOARD_ROOT', ROOT))
spec = importlib.util.spec_from_file_location('demo_bridge', DASHBOARD / 'dashboard/dataTest.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
X, Y = module.METRICS


class WriterTests(unittest.TestCase):
    def test_windows_reader_lock_retries_atomic_replace_without_losing_sample(self):
        with TemporaryDirectory() as directory:
            writer = TelemetryJsonWriter(directory)
            original = Path.replace
            calls = []

            def busy_once(path, target):
                calls.append(path)
                if len(calls) == 1:
                    raise PermissionError('Windows reader temporarily holds destination')
                return original(path, target)

            with patch.object(Path, 'replace', busy_once):
                writer.record(1234, 1.5, -2)
            self.assertTrue(writer.enabled)
            for name in writer.METRICS:
                points = json.loads((Path(directory) / (name + '.json')).read_text())
                self.assertEqual(points[0]['timestamp'], 1234)

    def test_invalid_sample_cannot_poison_json_or_separate_xy_pairs(self):
        with TemporaryDirectory() as directory:
            writer = TelemetryJsonWriter(directory)
            for timestamp, x, y in [(1000, float('nan'), 1), (1001, 1, float('inf')),
                                    (-1, 1, 2), (True, 1, 2), (1002, None, 2)]:
                writer.record(timestamp, x, y)
            writer.record(1003, -2.5, 0)
            for name in writer.METRICS:
                data = json.loads((Path(directory) / (name + '.json')).read_text())
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]['timestamp'], 1003)

    def test_initial_io_failure_disables_export_without_raising_in_flight(self):
        with patch.object(Path, 'mkdir', side_effect=PermissionError('read-only')):
            writer = TelemetryJsonWriter('unwritable')
        self.assertFalse(writer.enabled)

    def test_midflight_io_failure_preserves_last_good_file(self):
        with TemporaryDirectory() as directory:
            writer = TelemetryJsonWriter(directory)
            writer.record(1000, 1, 2)
            with patch.object(Path, 'replace', side_effect=PermissionError('busy')):
                writer.record(1001, 3, 4)
            self.assertFalse(writer.enabled)
            self.assertEqual(json.loads((Path(directory) / 'kalman_state_x.json').read_text()),
                             [{'timestamp': 1000, 'value': 1.0}])


class FileBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.bridge = module.TelemetryBridge()
        self.writer = TelemetryJsonWriter(self.directory)

    def drain(self):
        points = []
        while not self.bridge.queue.empty():
            points.append(json.loads(self.bridge.queue.get_nowait()))
        return points

    def test_whole_flight_batch_reaches_bridge_with_exact_values_and_timestamps(self):
        for i in range(50):
            self.writer.record(1700000000000 + i * 100, i / 10, -i / 20)
        self.bridge.poll_json_once(self.directory)
        points = self.drain()
        self.assertEqual(len(points), 100)  # not just the latest pair
        for key, filename in [(X, 'kalman_state_x'), (Y, 'kalman_state_y')]:
            source = json.loads((self.directory / (filename + '.json')).read_text())
            expected = [dict(id=key, **point) for point in source]
            self.assertEqual([p for p in points if p['id'] == key], expected)
            self.assertEqual(self.bridge.get_history(key, 0, 2e12), expected)
        self.bridge.poll_json_once(self.directory)
        self.assertEqual(self.drain(), [])

    def test_missing_partial_empty_wrong_shape_and_invalid_numbers_recover(self):
        path = self.directory / 'kalman_state_x.json'
        path.unlink()
        self.bridge.poll_json_once(self.directory)
        for content in ['{', '{}', 'null', '12', '[]', '[null,{},false]',
                        '[{"timestamp": 1000, "value": NaN}]',
                        '[{"timestamp": true, "value": 1}]',
                        '[{"timestamp": 1000, "value": "2"}]']:
            path.write_text(content)
            self.bridge.poll_json_once(self.directory)
            self.assertEqual(self.drain(), [], content)
        self.writer.record(1100, 0, -1)
        self.bridge.poll_json_once(self.directory)
        self.assertEqual(len(self.drain()), 2)

    def test_file_access_failure_retries_and_does_not_erase_history(self):
        self.writer.record(1000, 1, 2)
        self.bridge.poll_json_once(self.directory)
        with patch.object(Path, 'read_text', side_effect=PermissionError('busy')):
            self.bridge.poll_json_once(self.directory)
        self.assertEqual(len(self.bridge.get_history(X, 0, 2000)), 1)
        self.writer.record(1100, 3, 4)
        self.bridge.poll_json_once(self.directory)
        self.assertEqual(len(self.bridge.get_history(X, 0, 2000)), 2)

    def test_timestamp_correction_out_of_order_and_new_flight_reset(self):
        path = self.directory / 'kalman_state_x.json'
        path.write_text(json.dumps([{'timestamp': 2000, 'value': 2},
                                    {'timestamp': 1000, 'value': 1},
                                    {'timestamp': 2000, 'value': 3}]))
        self.bridge.poll_json_once(self.directory)
        self.assertEqual(self.bridge.get_history(X, 1500, 2000),
                         [{'id': X, 'timestamp': 2000, 'value': 3.0}])
        self.writer = TelemetryJsonWriter(self.directory)
        self.bridge.poll_json_once(self.directory)
        self.assertEqual(self.bridge.get_history(X, 0, 9999), [])
        self.writer.record(3000, 4, 5)
        self.bridge.poll_json_once(self.directory)
        self.assertEqual(len(self.bridge.get_history(X, 0, 9999)), 1)

    def test_backpressure_is_bounded_and_does_not_destroy_history(self):
        for i in range(2000):
            self.bridge.publish_sample(i, -i, 1000 + i)
        self.assertLessEqual(self.bridge.queue.qsize(), 1024)
        self.assertEqual(len(self.bridge.get_history(X, 0, 9999)), 2000)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_saturated_client_cannot_delay_a_healthy_view(self):
        class Client:
            def __init__(self):
                self.closed = False

            async def close(self, **kwargs):
                self.closed = True

        bridge = module.TelemetryBridge()
        slow, fast = Client(), Client()
        full = asyncio.Queue(maxsize=1)
        full.put_nowait('blocked')
        healthy = asyncio.Queue(maxsize=10)
        bridge.clients = {slow: full, fast: healthy}
        bridge.publish_sample(1, 2, 1000)
        task = asyncio.create_task(bridge.broadcast())
        try:
            received = [json.loads(await asyncio.wait_for(healthy.get(), 1)) for _ in range(2)]
            self.assertEqual([p['id'] for p in received], [X, Y])
            await asyncio.sleep(0)
            self.assertTrue(slow.closed)
            self.assertNotIn(slow, bridge.clients)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_real_writer_to_websocket_live_history_two_clients_and_reconnect(self):
        bridge = module.TelemetryBridge()
        async with serve(bridge.handle_client, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            url = f'ws://127.0.0.1:{port}'
            broadcaster = asyncio.create_task(bridge.broadcast())
            try:
                with TemporaryDirectory() as directory:
                    writer = TelemetryJsonWriter(directory)
                    async with connect(url) as one, connect(url) as two:
                        writer.record(1700000000100, 1.25, -0.5)
                        bridge.poll_json_once(Path(directory))
                        expected = [{'id': X, 'timestamp': 1700000000100, 'value': 1.25},
                                    {'id': Y, 'timestamp': 1700000000100, 'value': -0.5}]
                        for client in (one, two):
                            received = [json.loads(await asyncio.wait_for(client.recv(), 2)) for _ in range(2)]
                            self.assertEqual(received, expected)
                    # A late client must recover saved values without another flight sample.
                    async with connect(url) as late:
                        for bad in ['bad json', 'null', '[]', '{"type":"unknown"}']:
                            await late.send(bad)
                        await late.send(json.dumps({'type': 'history', 'requestId': 'test',
                                                   'id': X, 'start': 1700000000100, 'end': 1700000000100}))
                        response = json.loads(await asyncio.wait_for(late.recv(), 2))
                        self.assertEqual(response, {'type': 'history', 'requestId': 'test', 'points': [expected[0]]})
            finally:
                broadcaster.cancel()
                await asyncio.gather(broadcaster, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
