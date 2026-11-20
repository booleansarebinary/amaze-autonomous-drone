import type { Scenario } from "../types"
import type { Telemetry } from "../telemetry/types"

// Mock backend snapshots used for the prototype scenarios. A real backend
// replaces these via the telemetry source in `telemetry/useTelemetry.ts`.

export const scenarioLabels: Record<Scenario, string> = {
  normal: "Normal flight",
  lowBattery: "Low battery",
  missionFailure: "Mission failure",
  telemetryLoss: "Telemetry loss",
  missionComplete: "Mission complete",
}

const route = [
  { x: 0.09, y: 0.76 },
  { x: 0.22, y: 0.5 },
  { x: 0.37, y: 0.43 },
  { x: 0.5, y: 0.6 },
  { x: 0.61, y: 0.74 },
  { x: 0.72, y: 0.55 },
  { x: 0.82, y: 0.36 },
  { x: 0.91, y: 0.28 },
]

const cells = (voltage: number, weakDrop = 0) => [
  voltage / 4,
  voltage / 4,
  voltage / 4,
  voltage / 4 - weakDrop,
]

function snapshot(overrides: {
  battery: number
  voltage: number
  remainingFlightSec: number
  altitude: number | null
  velocity: number
  attitude: Telemetry["attitude"]
  mission: Partial<Telemetry["mission"]>
  gps?: Partial<Telemetry["gps"]>
  flightMode?: Telemetry["flightMode"]
}): Telemetry {
  return {
    timestamp: Date.now(),
    drone: { name: "AEGIS ONE", id: "DRN–A17" },
    link: { connected: true, signal: 92, latencyMs: 42 },
    flightMode: overrides.flightMode ?? "AUTO",
    battery: {
      percent: overrides.battery,
      voltage: overrides.voltage,
      cellVoltages: cells(overrides.voltage, overrides.battery < 30 ? 0.18 : 0),
      remainingFlightSec: overrides.remainingFlightSec,
    },
    gps: {
      fix: "3d",
      satellites: 14,
      lat: 37.7749,
      lon: -122.4194,
      homeDistanceM: 183,
      ...overrides.gps,
    },
    attitude: overrides.attitude,
    velocity: overrides.velocity,
    altitude: { value: overrides.altitude, unit: "m", scaleMax: 40 },
    mission: {
      name: "Waypoint survey",
      status: "inFlight",
      progress: 68,
      waypointsTotal: 8,
      waypointsReached: 5,
      etaSec: 402,
      elapsedSec: 1116,
      distanceM: 2840,
      avgSpeed: 10.6,
      maxAltitude: 38.2,
      batteryUsed: 22,
      route,
      ...overrides.mission,
    },
  }
}

export const scenarios: Record<Scenario, () => Telemetry> = {
  normal: () =>
    snapshot({
      battery: 78,
      voltage: 15.8,
      remainingFlightSec: 1440,
      altitude: 34,
      velocity: 12.4,
      attitude: { roll: 4.2, pitch: -1.8, yaw: 128 },
      mission: {},
    }),
  lowBattery: () =>
    snapshot({
      battery: 24,
      voltage: 13.2,
      remainingFlightSec: 360,
      altitude: 31,
      velocity: 8.7,
      attitude: { roll: 2.8, pitch: -0.9, yaw: 133 },
      mission: { progress: 76, waypointsReached: 6, etaSec: 318, batteryUsed: 54 },
    }),
  missionFailure: () =>
    snapshot({
      battery: 51,
      voltage: 14.7,
      remainingFlightSec: 900,
      altitude: 26,
      velocity: 3.2,
      flightMode: "HOLD",
      attitude: { roll: -1.1, pitch: 1.4, yaw: 118 },
      mission: {
        status: "failed",
        progress: 72,
        etaSec: null,
        elapsedSec: 1182,
        distanceM: 2910,
        failureReason:
          "Obstacle avoidance reported an unsafe approach corridor. Re-plan or retry.",
      },
    }),
  telemetryLoss: () =>
    snapshot({
      battery: 64,
      voltage: 15.1,
      remainingFlightSec: 1140,
      altitude: null,
      velocity: 6.1,
      attitude: { roll: 0, pitch: 0, yaw: 121 },
      gps: { fix: "none", satellites: 0 },
      mission: { progress: 54, waypointsReached: 4, etaSec: 564 },
    }),
  missionComplete: () =>
    snapshot({
      battery: 43,
      voltage: 14.3,
      remainingFlightSec: 720,
      altitude: 8,
      velocity: 1.2,
      flightMode: "LAND",
      attitude: { roll: 0.4, pitch: 0.2, yaw: 142 },
      mission: {
        status: "complete",
        progress: 100,
        waypointsReached: 8,
        etaSec: 0,
        elapsedSec: 1458,
        distanceM: 3620,
        batteryUsed: 35,
      },
    }),
}
