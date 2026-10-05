from cflib.crtp import init_drivers
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger

URI = "radio://0/80/2M"  # adjust to your setup

def build_log_configs():
    lg_state = LogConfig(name="State", period_in_ms=100)  # 10 Hz
    lg_state.add_variable("pm.vbat", "float")
    lg_state.add_variable("pm.batteryLevel", "uint8_t")
    lg_state.add_variable("stabilizer.roll", "float")
    lg_state.add_variable("stabilizer.pitch", "float")
    lg_state.add_variable("stabilizer.yaw", "float")

    lg_pos = LogConfig(name="Position", period_in_ms=100)
    lg_pos.add_variable("stateEstimate.x", "float")
    lg_pos.add_variable("stateEstimate.y", "float")
    lg_pos.add_variable("stateEstimate.z", "float")

    lg_rates = LogConfig(name="Rates", period_in_ms=100)
    lg_rates.add_variable("gyro.x", "float")
    lg_rates.add_variable("gyro.y", "float")
    lg_rates.add_variable("gyro.z", "float")

    return [lg_state, lg_pos, lg_rates]


def evaluate_status(state):
    vbat = state.get("pm.vbat", 4.2)
    roll = state.get("stabilizer.roll", 0.0)
    pitch = state.get("stabilizer.pitch", 0.0)
    gx, gy, gz = (state.get(k, 0.0) for k in ("gyro.x", "gyro.y", "gyro.z"))

    if vbat < 3.2:
        return "EMERGENCY_LOW_BATTERY"
    if abs(roll) > 45 or abs(pitch) > 45:
        return "EMERGENCY_TILT_LIMIT"
    if vbat < 3.4:
        return "WARNING_LOW_BATTERY"
    if max(abs(gx), abs(gy), abs(gz)) > 1000:
        return "WARNING_HIGH_RATE"
    return "NOMINAL"


def main():
    init_drivers()
    log_configs = build_log_configs()
    state = {}  # accumulates latest value per variable across all blocks

    print(f"Connecting to {URI}...")
    try:
        with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
            print("Connected! Press Ctrl+C to stop.")
            with SyncLogger(scf, log_configs) as logger:
                for timestamp, data, logconf in logger:
                    state.update(data)  # merge whichever block just arrived
                    status = evaluate_status(state)

                    print(
                        f"[{status}] "
                        f"Battery: {state.get('pm.vbat', float('nan')):.2f} V "
                        f"({state.get('pm.batteryLevel', 0)}%) | "
                        f"Roll: {state.get('stabilizer.roll', float('nan')):.2f}° | "
                        f"Pitch: {state.get('stabilizer.pitch', float('nan')):.2f}° | "
                        f"Yaw: {state.get('stabilizer.yaw', float('nan')):.2f}° | "
                        f"Pos: ({state.get('stateEstimate.x', float('nan')):.2f}, "
                        f"{state.get('stateEstimate.y', float('nan')):.2f}, "
                        f"{state.get('stateEstimate.z', float('nan')):.2f})"
                    )

                    if status.startswith("EMERGENCY"):
                        print(f"!! {status} — landing/stop should trigger here !!")

    except KeyboardInterrupt:
        print("\nTelemetry stopped.")
    except Exception as error:
        print(f"\nCrazyflie error: {error}")


if __name__ == "__main__":
    main()