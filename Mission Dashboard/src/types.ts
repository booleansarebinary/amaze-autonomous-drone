export type ThemeMode = "light" | "dark"
export type Scenario = "normal" | "lowBattery" | "missionFailure" | "telemetryLoss" | "missionComplete"
export type SpeedLevel = "low" | "medium" | "high"
export type FlightControlState = "running" | "paused" | "returning" | "emergency"
export type WarningState = "default" | "active" | "dismissed"

export type ScenarioData = {
  label: string
  battery: number
  voltage: string
  flightTime: string
  altitude: number
  speed: number
  roll: number
  pitch: number
  yaw: number
  progress: number
  eta: string
  warning?: {
    severity: "warning" | "critical"
    title: string
    message: string
    kind: "battery" | "failure" | "telemetry"
  }
}
