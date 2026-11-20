import { useEffect, useRef, useState } from "react"
import { scenarios } from "../data/scenarios"
import type { Scenario } from "../types"
import type { FlightCommand, Telemetry, TelemetryPatch } from "./types"

/**
 * Backend endpoint. When `VITE_TELEMETRY_URL` is set (e.g. ws://host/telemetry)
 * the dashboard streams JSON `Telemetry` snapshots or partial patches from it
 * and sends `{ command }` messages back. Otherwise it runs the local mock.
 */
const TELEMETRY_URL = import.meta.env.VITE_TELEMETRY_URL as string | undefined
const DUMMY_TELEMETRY_URL =
  import.meta.env.VITE_DUMMY_TELEMETRY_URL as string | undefined ??
  "ws://localhost:8765"

type JsonObject = Record<string, unknown>

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value)
}

function finiteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined
}

function batteryPercentFromVoltage(voltage: number): number {
  const emptyVoltage = 3.0
  const fullVoltage = 4.2
  return Math.round(
    Math.min(
      100,
      Math.max(
        0,
        ((voltage - emptyVoltage) / (fullVoltage - emptyVoltage)) * 100,
      ),
    ),
  )
}

/**
 * Converts the Crazyflie bridge payload into the dashboard contract. Other
 * backends can continue to send Telemetry snapshots or TelemetryPatch objects.
 */
export function parseTelemetryFrame(frame: string): TelemetryPatch | null {
  const payload: unknown = JSON.parse(frame)
  if (!isObject(payload)) return null

  if (isObject(payload.values)) {
    const voltage = finiteNumber(payload.values["drone.battery.voltage"])
    const roll = finiteNumber(payload.values["drone.attitude.roll"])
    const pitch = finiteNumber(payload.values["drone.attitude.pitch"])
    const yaw = finiteNumber(payload.values["drone.attitude.yaw"])

    if (
      voltage === undefined &&
      roll === undefined &&
      pitch === undefined &&
      yaw === undefined
    ) {
      return null
    }

    const timestamp = finiteNumber(payload.utc) ?? Date.now()
    const patch: TelemetryPatch = {
      timestamp,
      link: { connected: true },
    }

    if (voltage !== undefined) {
      patch.battery = {
        percent: batteryPercentFromVoltage(voltage),
        voltage,
        cellVoltages: [voltage],
      }
    }

    if (roll !== undefined || pitch !== undefined || yaw !== undefined) {
      patch.attitude = {
        ...(roll !== undefined ? { roll } : {}),
        ...(pitch !== undefined ? { pitch } : {}),
        ...(yaw !== undefined ? { yaw } : {}),
      }
    }

    return patch
  }

  return payload as TelemetryPatch
}

export function mergeTelemetry(
  current: Telemetry,
  patch: TelemetryPatch,
): Telemetry {
  const next = { ...current } as Record<string, unknown>
  for (const [key, value] of Object.entries(patch)) {
    const prev = next[key]
    next[key] =
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      prev &&
      typeof prev === "object"
        ? { ...prev, ...value }
        : value
  }
  return next as Telemetry
}

// Local stand-in for the backend: drifts the scenario snapshot over time.
function simulate(
  base: Telemetry,
  seconds: number,
  flying: boolean,
): Telemetry {
  if (!flying) return base
  const t = seconds
  const drain = Math.min(base.battery.percent, t / 90)
  const percent = Math.max(0, base.battery.percent - drain)
  const voltage = base.battery.voltage - drain * 0.035
  const progressRate = base.mission.status === "inFlight" ? t / 18 : 0
  const progress = Math.min(99, base.mission.progress + progressRate)
  return mergeTelemetry(base, {
    timestamp: Date.now(),
    link: {
      signal: Math.round(base.link.signal + Math.sin(t * 0.4) * 4),
      latencyMs: Math.round(base.link.latencyMs + Math.sin(t * 1.3) * 6),
    },
    battery: {
      percent: Math.round(percent),
      voltage,
      cellVoltages: base.battery.cellVoltages.map(
        (cell) => cell - drain * 0.009,
      ),
      remainingFlightSec: Math.max(
        0,
        base.battery.remainingFlightSec - t * 1.4,
      ),
    },
    attitude: {
      roll:
        base.attitude.roll + Math.sin(t * 0.9) * 9 + Math.sin(t * 2.3) * 1.5,
      pitch: base.attitude.pitch + Math.sin(t * 0.6 + 1) * 6,
      yaw: (base.attitude.yaw + Math.sin(t * 0.25) * 22 + 360) % 360,
    },
    velocity: Math.max(
      0,
      base.velocity + Math.sin(t * 0.5) * 1.8 + Math.sin(t * 1.7) * 0.6,
    ),
    altitude: {
      value:
        base.altitude.value === null
          ? null
          : Math.max(0, base.altitude.value + Math.sin(t / 1.8) * 1.6),
    },
    gps:
      base.gps.fix === "none"
        ? {}
        : {
            lat: base.gps.lat + Math.sin(t * 0.05) * 0.0004,
            lon: base.gps.lon + Math.cos(t * 0.05) * 0.0004,
            homeDistanceM: Math.round(base.gps.homeDistanceM + t * 1.2),
          },
    mission: {
      elapsedSec: base.mission.elapsedSec + t,
      progress,
      waypointsReached: Math.min(
        base.mission.waypointsTotal - 1,
        Math.floor((progress / 100) * base.mission.waypointsTotal),
      ),
      etaSec:
        base.mission.etaSec === null
          ? null
          : Math.max(0, base.mission.etaSec - t),
      distanceM: base.mission.distanceM + t * base.velocity,
    },
  })
}

export default function useTelemetry(
  scenario: Scenario,
  flying: boolean,
  useDummy = false,
) {
  const [telemetry, setTelemetry] = useState<Telemetry>(() =>
    scenarios[scenario](),
  )
  const socket = useRef<WebSocket | null>(null)
  const flyingRef = useRef(flying)
  const telemetryUrl = useDummy ? DUMMY_TELEMETRY_URL : TELEMETRY_URL
  flyingRef.current = flying

  // Live backend stream
  useEffect(() => {
    if (!telemetryUrl) return
    let active = true
    const ws = new WebSocket(telemetryUrl)
    socket.current = ws
    setTelemetry((current) =>
      mergeTelemetry(current, { link: { connected: false } }),
    )
    ws.onopen = () =>
      active &&
      setTelemetry((current) => {
        return mergeTelemetry(current, { link: { connected: true } })
      })
    ws.onmessage = (event) => {
      if (!active) return
      try {
        if (typeof event.data !== "string") return
        const patch = parseTelemetryFrame(event.data)
        if (patch) setTelemetry((current) => mergeTelemetry(current, patch))
      } catch {
        // Ignore malformed frames
      }
    }
    ws.onclose = () => {
      if (!active) return
      socket.current = null
      setTelemetry((current) =>
        mergeTelemetry(current, { link: { connected: false } }),
      )
    }
    return () => {
      active = false
      if (socket.current === ws) socket.current = null
      ws.close()
    }
  }, [telemetryUrl])

  // Mock stream: flight time only advances while flying, so pausing holds values
  useEffect(() => {
    if (telemetryUrl) return
    const base = scenarios[scenario]()
    setTelemetry(base)
    let elapsed = 0
    let last = Date.now()
    const interval = window.setInterval(() => {
      const now = Date.now()
      if (flyingRef.current) elapsed += (now - last) / 1000
      last = now
      setTelemetry((current) =>
        flyingRef.current || elapsed === 0
          ? simulate(base, elapsed, elapsed > 0)
          : current,
      )
    }, 120)
    return () => window.clearInterval(interval)
  }, [scenario, telemetryUrl])

  function sendCommand(command: FlightCommand) {
    if (socket.current?.readyState === WebSocket.OPEN) {
      socket.current.send(JSON.stringify({ command }))
    }
  }

  return { telemetry, sendCommand }
}
