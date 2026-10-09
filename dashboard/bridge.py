import asyncio, json, time, threading
import websockets
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig

URI = 'radio://0/80/2M/E7E7E7E7E7'   # change to your drone's URI

clients = set()
loop = asyncio.new_event_loop()

async def broadcast(msg):
    for ws in list(clients):
        try:
            await ws.send(msg)
        except Exception:
            clients.discard(ws)

def on_log(timestamp, data, logconf):
    now = int(time.time() * 1000)
    # Map cflib names to the keys used in dronePlugin.js
    out = {
        'battery': data['pm.vbat'],
        'roll':    data['stabilizer.roll'],
        'pitch':   data['stabilizer.pitch'],
    }
    for key, value in out.items():
        msg = json.dumps({'key': key, 'timestamp': now, 'value': value})
        asyncio.run_coroutine_threadsafe(broadcast(msg), loop)

def drone_thread():
    cflib.crtp.init_drivers()
    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        lg = LogConfig(name='telemetry', period_in_ms=100)
        lg.add_variable('pm.vbat', 'float')
        lg.add_variable('stabilizer.roll', 'float')
        lg.add_variable('stabilizer.pitch', 'float')
        scf.cf.log.add_config(lg)
        lg.data_received_cb.add_callback(on_log)
        lg.start()
        while True:
            time.sleep(1)

async def handler(ws):
    clients.add(ws)
    try:
        await ws.wait_closed()
    finally:
        clients.discard(ws)

async def main():
    async with websockets.serve(handler, 'localhost', 8765):
        await asyncio.Future()

threading.Thread(target=drone_thread, daemon=True).start()
asyncio.set_event_loop(loop)
loop.run_until_complete(main())