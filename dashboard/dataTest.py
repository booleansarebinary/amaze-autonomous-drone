import cflib.crtp

from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger


URI = "radio://0/80/2M/E7E7E7E7E7"


def main():
    cflib.crtp.init_drivers()

    log_config = LogConfig(
        name="Telemetry",
        period_in_ms=100
    )

    log_config.add_variable("pm.vbat", "float")
    log_config.add_variable("stabilizer.roll", "float")
    log_config.add_variable("stabilizer.pitch", "float")
    log_config.add_variable("stabilizer.yaw", "float")

    print(f"Connecting to {URI}...")

    try:
        with SyncCrazyflie(
            URI,
            cf=Crazyflie(rw_cache="./cache")
        ) as scf:
            print("Connected! Press Ctrl+C to stop.")

            with SyncLogger(scf, log_config) as logger:
                for timestamp, data, logconf in logger:
                    print(
                        f"Battery: {data['pm.vbat']:.2f} V | "
                        f"Roll: {data['stabilizer.roll']:.2f}° | "
                        f"Pitch: {data['stabilizer.pitch']:.2f}° | "
                        f"Yaw: {data['stabilizer.yaw']:.2f}°"
                    )

    except KeyboardInterrupt:
        print("\nTelemetry stopped.")

    except Exception as error:
        print(f"\nCrazyflie error: {error}")


if __name__ == "__main__":
    main()