"""Local-only test fixture. All flight-like samples go into a temporary folder.

JSON lines on stdin control a real bridge subprocess and the actual flight
writer. No cflib imports, radio connections, or flight commands are performed.
"""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from algorithms.reactive_nav import TelemetryJsonWriter


def main():
    dashboard = Path(os.environ.get('DASHBOARD_ROOT', ROOT))
    docker = os.environ.get('TELEMETRY_E2E_DOCKER') == '1'
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
        SimpleHTTPRequestHandler, directory=str(dashboard)))
    http_port = server.server_port
    if docker:
        server.server_close()
    else:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    bridge = None
    with TemporaryDirectory(prefix='flight-telemetry-e2e-') as directory:
        writer = TelemetryJsonWriter(directory)
        compose = ['docker', 'compose', '-f', str(dashboard / 'compose.telemetry.yml'),
                   '-p', f'amaze-telemetry-e2e-{os.getpid()}']
        environment = dict(os.environ, TELEMETRY_DIR=directory, TELEMETRY_PORT=str(port),
                           DASHBOARD_PORT=str(http_port))

        def docker_command(*args):
            subprocess.run(compose + list(args), env=environment, check=True,
                           stdout=sys.stderr, stderr=sys.stderr, timeout=60)

        def wait_port(target):
            deadline = time.monotonic() + 8
            while True:
                try:
                    with socket.create_connection(('127.0.0.1', target), timeout=0.1):
                        return
                except OSError:
                    if time.monotonic() > deadline:
                        raise RuntimeError(f'test service on {target} did not start')
                    time.sleep(0.05)

        try:
            if docker:
                docker_command('up', '-d', '--no-build', 'dashboard')
                wait_port(http_port)
            print(json.dumps({'url': f'http://127.0.0.1:{http_port}/dashboard/',
                              'port': port}), flush=True)
            for line in sys.stdin:
                request = json.loads(line)
                action = request['action']
                if action == 'start':
                    if docker:
                        docker_command('up', '-d', '--no-build', 'bridge')
                    else:
                        bridge = subprocess.Popen([sys.executable, '-u', str(dashboard / 'dashboard/dataTest.py'),
                                               '--json-dir', directory, '--host', '127.0.0.1', '--port', str(port)],
                                              stdout=sys.stderr, stderr=sys.stderr)
                    wait_port(port)
                elif action == 'stop':
                    if docker:
                        docker_command('stop', '-t', '1', 'bridge')
                    else:
                        bridge.terminate()
                        bridge.wait(timeout=5)
                        bridge = None
                elif action == 'write':
                    for sample in request['samples']:
                        writer.record(sample['timestamp'], sample['x'], sample['y'])
                elif action == 'exit':
                    break
                else:
                    raise ValueError(action)
                print(json.dumps({'ok': action}), flush=True)
        finally:
            if docker:
                # Only the unique test project created above; preserve user services.
                docker_command('down', '-t', '1')
            else:
                if bridge is not None:
                    bridge.terminate()
                    bridge.wait(timeout=5)
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    main()
