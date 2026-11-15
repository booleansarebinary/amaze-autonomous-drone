import time
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig

URI = "radio://0/80/2M/E7E7E7E7E7"

def telemetry_callback(timestamp, data, logconf):
    print(
        f"Battery: {data['pm.vbat']:.2f} V | "
        f"Roll: {data['stabilizer.roll']:.2f}° | "
        f"Pitch: {data['stabilizer.pitch']:.2f}° | "
        f"Yaw: {data['stabilizer.yaw']:.2f}°"
    )

cflib.crtp.init_drivers()

cf = Crazyflie()
cf.open_link(URI)

log_config = LogConfig(name="Telemetry", period_in_ms=100)
log_config.add_variable("pm.vbat", "float")
log_config.add_variable("stabilizer.roll", "float")
log_config.add_variable("stabilizer.pitch", "float")
log_config.add_variable("stabilizer.yaw", "float")

log_config.data_received_cb.add_callback(telemetry_callback)

cf.log.add_config(log_config)
log_config.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    log_config.delete()
    cf.close_link()
