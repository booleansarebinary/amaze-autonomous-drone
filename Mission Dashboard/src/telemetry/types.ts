// Backend telemetry contract. Every value shown on the dashboard is read from
// this shape; the backend may send full snapshots or partial updates.

export type GpsFix = "none" | "2d" | "3d"
export type FlightMode = "AUTO" | "MANUAL" | "HOLD" | "RTH" | "LAND"
export type MissionStatus = "idle" | "inFlight" | "paused" | "failed" | "complete"
export type FlightCommand = "start" | "pause" | "returnHome" | "emergencyStop"

export type Telemetry = {
  timestamp: number
  drone: { name: string; id: string }
  link: {
    connected: boolean
    /** 0–100 */
    signal: number
    latencyMs: number
  }
  flightMode: FlightMode
  battery: {
    /** 0–100 */
    percent: number
    voltage: number
    cellVoltages: number[]
    remainingFlightSec: number
  }
  gps: {
    fix: GpsFix
    satellites: number
    lat: number
    lon: number
    homeDistanceM: number
  }
  attitude: { roll: number; pitch: number; yaw: number }
  /** m/s */
  velocity: number
  altitude: {
    /** null when the altimeter stream is unavailable */
    value: number | null
    unit: "m" | "cm"
    scaleMax: number
  }
  mission: {
    name: string
    status: MissionStatus
    /** 0–100 */
    progress: number
    waypointsTotal: number
    waypointsReached: number
    etaSec: number | null
    elapsedSec: number
    distanceM: number
    avgSpeed: number
    maxAltitude: number
    batteryUsed: number
    failureReason?: string
    /** Route in normalized map coordinates (0–1) */
    route: { x: number; y: number }[]
  }
}

export type TelemetryPatch = {
  [K in keyof Telemetry]?: Telemetry[K] extends object[] | number | string | boolean
    ? Telemetry[K]
    : Partial<Telemetry[K]>
}
