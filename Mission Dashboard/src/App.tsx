import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import DroneScene from "./components/DroneScene"
import HomePage from "./components/HomePage"
import Icon, { type IconName } from "./components/Icons"
import { scenarioLabels } from "./data/scenarios"
import useTelemetry from "./telemetry/useTelemetry"
import type { Telemetry } from "./telemetry/types"
import type {
  FlightControlState,
  Scenario,
  SpeedLevel,
  ThemeMode,
} from "./types"

const scenarioOrder: Scenario[] = [
  "normal",
  "lowBattery",
  "missionFailure",
  "telemetryLoss",
  "missionComplete",
]

// ── Formatting ────────────────────────────────────────────────────────────

const pad = (value: number) => String(Math.floor(value)).padStart(2, "0")

function formatClock(seconds: number) {
  const s = Math.max(0, seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h ? `${h}:${pad(m)}:${pad(s % 60)}` : `${pad(m)}:${pad(s % 60)}`
}

function formatMinutesSeconds(seconds: number) {
  const s = Math.max(0, seconds)
  return `${pad(s / 60)}:${pad(s % 60)}`
}

function formatDistance(meters: number) {
  return meters >= 1000
    ? `${(meters / 1000).toFixed(2)} km`
    : `${Math.round(meters)} m`
}

function formatCoordinate(value: number, positive: string, negative: string) {
  return `${Math.abs(value).toFixed(4)}° ${value >= 0 ? positive : negative}`
}

const signed = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(1)}°`

function speedLevel(velocity: number): SpeedLevel {
  return velocity < 8 ? "low" : velocity < 16 ? "medium" : "high"
}

// ── Derived alerts ────────────────────────────────────────────────────────

type Warning = {
  id: string
  severity: "warning" | "critical"
  kind: "battery" | "failure" | "telemetry"
  title: string
  message: string
}

const LOW_BATTERY = 30
const CRITICAL_BATTERY = 15

function deriveWarning(t: Telemetry): Warning | null {
  if (t.mission.status === "failed") {
    return {
      id: "mission-failed",
      severity: "critical",
      kind: "failure",
      title: "Mission interrupted",
      message: `Waypoint ${t.mission.waypointsReached + 1} could not be reached`,
    }
  }
  if (!t.link.connected) {
    return {
      id: "link-lost",
      severity: "critical",
      kind: "telemetry",
      title: "Link lost",
      message: "No data from the aircraft · Failsafe will engage",
    }
  }
  if (t.gps.fix === "none") {
    return {
      id: "gps-lost",
      severity: "critical",
      kind: "telemetry",
      title: "GPS telemetry lost",
      message:
        t.altitude.value === null
          ? "Position and altimeter streams unavailable · Holding last coordinates"
          : "Position stream unavailable · Holding last coordinates",
    }
  }
  if (t.battery.percent < LOW_BATTERY && t.mission.status !== "complete") {
    return {
      id: "battery-low",
      severity: t.battery.percent < CRITICAL_BATTERY ? "critical" : "warning",
      kind: "battery",
      title:
        t.battery.percent < CRITICAL_BATTERY
          ? "Critical battery"
          : "Low battery",
      message: `${t.battery.percent}% remaining · Return flight reserve is approaching`,
    }
  }
  return null
}

function GlassCard({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode
  className?: string
  title?: string
  action?: ReactNode
}) {
  return (
    <section className={`glass-card ${className}`}>
      {title && (
        <div className="card-heading">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

function StatusChip({
  children,
  tone = "neutral",
  dot,
}: {
  children: ReactNode
  tone?: "neutral" | "success" | "warning" | "critical" | "accent"
  dot?: boolean
}) {
  return (
    <span className={`status-chip ${tone}`}>
      {dot && <span className="status-dot" />}
      {children}
    </span>
  )
}

function SignalBars({ signal }: { signal: number }) {
  const active = Math.ceil((signal / 100) * 4)
  return (
    <span
      aria-label={`Radio signal ${signal}%`}
      className="signal-bars"
      role="img"
    >
      {[1, 2, 3, 4].map((bar) => (
        <i key={bar} style={{ opacity: bar <= active ? 1 : 0.25 }} />
      ))}
    </span>
  )
}

function TopBar({
  t,
  clock,
  scenario,
  setScenario,
  dummyEnabled,
  onToggleDummy,
  onHome,
}: {
  t: Telemetry
  clock: string
  scenario: Scenario
  setScenario: (value: Scenario) => void
  dummyEnabled: boolean
  onToggleDummy: () => void
  onHome: () => void
}) {
  return (
    <header className="topbar glass-card">
      <div className="identity">
        <button
          aria-label="Back to mission select"
          className="drone-mark border-0"
          onClick={onHome}
          title="Mission select"
          type="button"
        >
          <Icon name="drone" size={20} />
        </button>
        <div>
          <strong>{t.drone.name}</strong>
          <span>{t.drone.id}</span>
        </div>
      </div>
      <div className="top-statuses">
        <StatusChip dot tone={t.link.connected ? "success" : "critical"}>
          {t.link.connected ? "Connected" : "Disconnected"}
        </StatusChip>
        <span className="top-stat">
          <Icon name="satellite" size={16} />
          GPS <b>{t.gps.fix === "none" ? "--" : t.gps.satellites}</b>
        </span>
        <span className="top-stat">
          <SignalBars signal={t.link.connected ? t.link.signal : 0} />
          <b>{t.link.connected ? `${t.link.signal}%` : "--"}</b>
        </span>
        <StatusChip tone="accent">{t.flightMode}</StatusChip>
      </div>
      <div className="top-actions">
        <button
          aria-pressed={dummyEnabled}
          className={`feed-toggle ${dummyEnabled ? "active" : ""}`}
          onClick={onToggleDummy}
          title={
            dummyEnabled
              ? "Return to the configured telemetry source"
              : "Connect to the dummy telemetry server"
          }
          type="button"
        >
          <span className="feed-toggle-dot" />
          Dummy feed
        </button>
        <label className="scenario-picker">
          <span>View</span>
          <select
            aria-label="Prototype scenario"
            onChange={(event) => setScenario(event.target.value as Scenario)}
            value={scenario}
          >
            {scenarioOrder.map((key) => (
              <option key={key} value={key}>
                {scenarioLabels[key]}
              </option>
            ))}
          </select>
        </label>
        <time>{clock}</time>
      </div>
    </header>
  )
}

function WarningBanner({
  warning,
  dismissed,
  onDismiss,
  onRetry,
  onDetails,
}: {
  warning: Warning | null
  dismissed: boolean
  onDismiss: () => void
  onRetry: () => void
  onDetails: () => void
}) {
  if (!warning) return null

  return (
    <div
      aria-live="assertive"
      className={`warning-banner ${warning.severity} ${
        dismissed ? "dismissed" : "active"
      }`}
      role="alert"
    >
      <span className="warning-icon">
        <Icon
          name={warning.kind === "battery" ? "battery" : "warning"}
          size={20}
        />
      </span>
      <div className="warning-copy">
        <strong>{warning.title}</strong>
        <span>{warning.message}</span>
      </div>
      {warning.kind === "failure" && (
        <div className="banner-actions">
          <button onClick={onDetails} type="button">
            View details
          </button>
          <button onClick={onRetry} type="button">
            Retry
          </button>
        </div>
      )}
      <button
        aria-label="Dismiss warning"
        className="banner-close"
        onClick={onDismiss}
        type="button"
      >
        <Icon name="close" size={16} />
      </button>
    </div>
  )
}

function BatteryGauge({ value }: { value: number }) {
  const tone =
    value < CRITICAL_BATTERY
      ? "critical"
      : value < LOW_BATTERY
        ? "warning"
        : "success"
  const circumference = 2 * Math.PI * 42
  return (
    <div className={`battery-gauge ${tone}`}>
      <svg aria-hidden="true" viewBox="0 0 100 100">
        <circle className="gauge-track" cx="50" cy="50" r="42" />
        <circle
          className="gauge-value"
          cx="50"
          cy="50"
          r="42"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - value / 100)}
        />
      </svg>
      <div>
        <strong>{value}%</strong>
        <span>POWER</span>
      </div>
    </div>
  )
}

function BatteryCard({ battery }: { battery: Telemetry["battery"] }) {
  const cells = battery.cellVoltages
  const average = cells.reduce((sum, cell) => sum + cell, 0) / cells.length
  return (
    <GlassCard
      className={`battery-card ${battery.percent < LOW_BATTERY ? "low" : ""}`}
      title="Battery"
    >
      <div className="battery-content">
        <BatteryGauge value={battery.percent} />
        <div className="battery-details">
          <div>
            <span>VOLTAGE</span>
            <strong>{battery.voltage.toFixed(1)} V</strong>
          </div>
          <div>
            <span>FLIGHT TIME</span>
            <strong>{formatMinutesSeconds(battery.remainingFlightSec)}</strong>
          </div>
          <div className="cell-health">
            <span>CELLS</span>
            {cells.map((cell, index) => (
              <i
                className={cell < average - 0.1 ? "weak" : ""}
                key={index}
                title={`Cell ${index + 1}: ${cell.toFixed(2)} V`}
              />
            ))}
          </div>
        </div>
      </div>
    </GlassCard>
  )
}

function MiniMap({ t }: { t: Telemetry }) {
  const disabled = t.gps.fix === "none"
  const points = t.mission.route.map(({ x, y }) => [x * 248, y * 88])
  const reached = t.mission.waypointsReached
  const current = points[Math.min(reached, points.length - 1)]
  const path = points
    .map(
      ([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`,
    )
    .join(" ")
  return (
    <div className="mini-map">
      <svg aria-hidden="true" viewBox="0 0 248 88">
        <path
          className="map-contour"
          d="M-8 26c32-24 54 7 83-5 36-15 48-1 76 11 35 16 67-15 105-8"
        />
        <path
          className="map-contour faint"
          d="M-12 70c42-23 68 3 100-6 45-12 67 15 103 0 26-11 43 0 67 8"
        />
        <path className="route-line" d={path} />
        {points.map(([x, y], index) => (
          <circle
            className={`route-point ${index > reached ? "upcoming" : ""}`}
            cx={x}
            cy={y}
            key={index}
            r="3.5"
          />
        ))}
        {current && (
          <>
            <circle
              className="route-point current"
              cx={current[0]}
              cy={current[1]}
              r="6"
            />
            <path
              className="map-drone"
              d={`m${current[0]} ${current[1] - 10} 6 14-6-3-6 3 6-14Z`}
              transform={`rotate(${t.attitude.yaw} ${current[0]} ${current[1]})`}
            />
          </>
        )}
      </svg>
      <span className="map-distance">
        {disabled ? "--" : `HOME · ${formatDistance(t.gps.homeDistanceM)}`}
      </span>
    </div>
  )
}

function PositionCard({ t }: { t: Telemetry }) {
  const signalLost = t.gps.fix === "none"
  return (
    <GlassCard
      className={`position-card ${signalLost ? "signal-lost" : ""}`}
      title="Position"
      action={
        <StatusChip tone={signalLost ? "critical" : "success"} dot>
          {signalLost ? "No signal" : `${t.gps.fix.toUpperCase()} FIX`}
        </StatusChip>
      }
    >
      <div className="coordinates">
        <div>
          <span>LATITUDE</span>
          <strong>
            {signalLost ? "--" : formatCoordinate(t.gps.lat, "N", "S")}
          </strong>
        </div>
        <div>
          <span>LONGITUDE</span>
          <strong>
            {signalLost ? "--" : formatCoordinate(t.gps.lon, "E", "W")}
          </strong>
        </div>
        <div>
          <span>SATELLITES</span>
          <strong>{signalLost ? "--" : t.gps.satellites}</strong>
        </div>
      </div>
      <MiniMap t={t} />
      {signalLost && (
        <div className="no-signal">
          <Icon name="satellite" size={24} />
          <strong>No GPS signal</strong>
          <span>Holding last known position</span>
        </div>
      )}
    </GlassCard>
  )
}

function MissionStats({ t }: { t: Telemetry }) {
  const metrics = [
    ["ELAPSED", formatClock(t.mission.elapsedSec)],
    ["DISTANCE", formatDistance(t.mission.distanceM)],
    [
      "WAYPOINTS",
      `${t.mission.waypointsReached} / ${t.mission.waypointsTotal}`,
    ],
    ["AVG SPEED", `${t.mission.avgSpeed.toFixed(1)} m/s`],
    ["MAX ALT.", `${t.mission.maxAltitude.toFixed(1)} ${t.altitude.unit}`],
    ["LINK LATENCY", t.link.connected ? `${t.link.latencyMs} ms` : "--"],
  ]
  return (
    <GlassCard className="stats-card" title="Mission stats">
      <div className="metric-grid">
        {metrics.map(([label, value]) => (
          <div className="metric" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}

function AttitudeArc({
  className,
  label,
  value,
}: {
  className: string
  label: string
  value: string
}) {
  return (
    <div className={`attitude ${className}`}>
      <svg aria-hidden="true" viewBox="0 0 200 100">
        <path d="M10 88C26 24 161 2 191 71" />
        <path
          className="arc-active"
          d="M10 88C26 24 161 2 191 71"
          pathLength="100"
        />
      </svg>
      <span>
        {label} <b>{value}</b>
      </span>
    </div>
  )
}

function useHistory(value: number, length = 40) {
  const [history, setHistory] = useState<number[]>([value])
  useEffect(() => {
    setHistory((current) => [...current.slice(-(length - 1)), value])
  }, [value, length])
  return history
}

function Sparkline({ values }: { values: number[] }) {
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = max - min || 1
  const points = values
    .map((value, index) => {
      const x = (index / Math.max(1, values.length - 1)) * 96
      const y = 26 - ((value - min) / range) * 22
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(" ")
  return (
    <svg aria-hidden="true" className="h-7 w-24" viewBox="0 0 96 28">
      <polyline
        fill="none"
        points={points}
        stroke="var(--secondary)"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.6"
      />
    </svg>
  )
}

function Hero({ t, paused }: { t: Telemetry paused: boolean }) {
  const { roll, pitch, yaw } = t.attitude
  const speed = speedLevel(t.velocity)
  const history = useHistory(t.velocity)
  return (
    <main className={`hero speed-${speed}`}>
      <div className="hero-glow" />
      <div className="speed-streaks" aria-hidden="true">
        {Array.from({ length: 13 }).map((_, index) => (
          <i key={index} />
        ))}
      </div>
      <div className="model-stage">
        <DroneScene
          paused={paused}
          pitch={pitch}
          roll={roll}
          speed={speed}
          yaw={yaw}
        />
      </div>
      <AttitudeArc className="roll" label="ROLL" value={signed(roll)} />
      <AttitudeArc className="pitch" label="PITCH" value={signed(pitch)} />
      <AttitudeArc className="yaw" label="YAW" value={`${Math.round(yaw)}°`} />
      <div className="axis-gizmo" aria-label="Orientation axes">
        <i className="axis-x" />
        <i className="axis-y" />
        <i className="axis-z" />
        <span>X</span>
        <span>Y</span>
        <span>Z</span>
      </div>
      <div className="speed-control pr-4">
        <div className="speed-readout">
          <span>VELOCITY</span>
          <strong>{t.velocity.toFixed(1)}</strong>
          <em>m/s</em>
        </div>
        <Sparkline values={history} />
      </div>
    </main>
  )
}

function AltitudeVisualizer({ altitude }: { altitude: Telemetry["altitude"] }) {
  const { value, unit, scaleMax } = altitude
  const signalLost = value === null
  const ratio = Math.max(0, Math.min(1, (value ?? 0) / scaleMax))
  const markerBottom = 13 + ratio * 70
  const ticks = Array.from({ length: 9 }, (_, index) =>
    Math.round((scaleMax / 8) * (8 - index)),
  )
  return (
    <GlassCard
      className={`altitude-card ${signalLost ? "signal-lost" : ""}`}
      title="Altitude"
      action={<StatusChip tone="accent">AGL</StatusChip>}
    >
      <div className="altitude-readout">
        <strong>{signalLost ? "--" : value.toFixed(1)}</strong>
        <span>{unit}</span>
      </div>
      <div className="altitude-scene">
        <div className="cloud cloud-one" />
        <div className="cloud cloud-two" />
        <div className="ruler">
          {ticks.map((tick) => (
            <span key={tick}>
              <i />
              <b>{tick}</b>
            </span>
          ))}
        </div>
        <div
          className="altitude-trail"
          style={{ height: `${Math.max(8, markerBottom - 10)}%` }}
        />
        <div className="altitude-drone" style={{ bottom: `${markerBottom}%` }}>
          <i className="rotor left" />
          <i className="rotor right" />
          <span />
        </div>
        <div className="ground-line">
          <i />
          <i />
          <i />
        </div>
      </div>
    </GlassCard>
  )
}

const missions = [
  { name: "Perimeter", path: "M3 17 7 5l13 2-3 12-14-2Z" },
  { name: "Survey", path: "M3 18 7 6h4l3 12 4-12h3" },
  { name: "Return", path: "M4 18c0-8 14-8 14-2M15 12l3 4 3-4" },
]

function MissionPanel({
  t,
  detailsOpen,
  onRetry,
}: {
  t: Telemetry
  detailsOpen: boolean
  onRetry: () => void
}) {
  const m = t.mission
  const failed = m.status === "failed"
  const complete = m.status === "complete"
  const [mission, setMission] = useState(0)

  return (
    <GlassCard
      className={`mission-card ${failed ? "failed" : ""} ${
        complete ? "complete" : ""
      }`}
      title="Mission"
      action={
        <StatusChip
          tone={failed ? "critical" : complete ? "success" : "accent"}
        >
          {failed
            ? "FAILED"
            : complete
              ? "COMPLETE"
              : m.status === "paused"
                ? "PAUSED"
                : "IN FLIGHT"}
        </StatusChip>
      }
    >
      {!failed && !complete && (
        <>
          <div className="mission-picker">
            {missions.map((item, index) => (
              <button
                aria-pressed={mission === index}
                className={mission === index ? "active" : ""}
                key={item.name}
                onClick={() => setMission(index)}
                type="button"
              >
                <svg aria-hidden="true" viewBox="0 0 24 24">
                  <path d={item.path} />
                </svg>
                <span>{item.name}</span>
              </button>
            ))}
          </div>
          <div className="progress-label">
            <span>{m.name}</span>
            <strong>{Math.round(m.progress)}%</strong>
          </div>
          <div className="progress-track">
            <i style={{ width: `${m.progress}%` }} />
          </div>
          <div className="waypoints">
            {Array.from({ length: m.waypointsTotal }, (_, i) => i + 1).map(
              (waypoint) => (
                <i
                  className={
                    waypoint <= m.waypointsReached
                      ? "done"
                      : waypoint === m.waypointsReached + 1
                        ? "current"
                        : ""
                  }
                  key={waypoint}
                >
                  {waypoint <= m.waypointsReached ? "✓" : waypoint}
                </i>
              ),
            )}
          </div>
          <div className="mission-footer">
            <span>
              {m.waypointsReached} of {m.waypointsTotal} reached
            </span>
            <span>
              ETA <b>{m.etaSec === null ? "--:--" : formatClock(m.etaSec)}</b>
            </span>
          </div>
        </>
      )}
      {complete && (
        <div className="result-state">
          <span className="result-icon">
            <Icon name="check" size={25} />
          </span>
          <div>
            <strong>{m.name} complete</strong>
            <span>All {m.waypointsTotal} waypoints reached</span>
          </div>
          <div className="result-metrics">
            <span>
              DURATION <b>{formatClock(m.elapsedSec)}</b>
            </span>
            <span>
              DISTANCE <b>{formatDistance(m.distanceM)}</b>
            </span>
            <span>
              BATTERY USED <b>{m.batteryUsed}%</b>
            </span>
          </div>
        </div>
      )}
      {failed && (
        <div className="result-state failed-result">
          <span className="result-icon">
            <Icon name="close" size={25} />
          </span>
          <div>
            <strong>Waypoint unreachable</strong>
            <span>
              Mission stopped at waypoint {m.waypointsReached + 1} of{" "}
              {m.waypointsTotal}
            </span>
          </div>
          {detailsOpen && m.failureReason && <p>{m.failureReason}</p>}
          <div className="result-metrics">
            <span>
              DURATION <b>{formatClock(m.elapsedSec)}</b>
            </span>
            <span>
              DISTANCE <b>{formatDistance(m.distanceM)}</b>
            </span>
          </div>
          <button className="retry-button" onClick={onRetry} type="button">
            <Icon name="retry" size={16} />
            Retry mission
          </button>
        </div>
      )}
    </GlassCard>
  )
}

function DockButton({
  icon,
  label,
  active,
  critical,
  onClick,
}: {
  icon: IconName
  label: string
  active?: boolean
  critical?: boolean
  onClick: () => void
}) {
  return (
    <button
      className={`dock-button ${active ? "active" : ""} ${
        critical ? "critical" : ""
      }`}
      onClick={onClick}
      type="button"
    >
      <span>
        <Icon name={icon} size={19} />
      </span>
      <b>{label}</b>
    </button>
  )
}

function ControlDock({
  control,
  setControl,
}: {
  control: FlightControlState
  setControl: (control: FlightControlState) => void
}) {
  const [emergencyArmed, setEmergencyArmed] = useState(false)

  useEffect(() => {
    if (!emergencyArmed) return
    const timeout = window.setTimeout(() => setEmergencyArmed(false), 3000)
    return () => window.clearTimeout(timeout)
  }, [emergencyArmed])

  function emergency() {
    if (emergencyArmed) {
      setControl("emergency")
      setEmergencyArmed(false)
    } else {
      setEmergencyArmed(true)
    }
  }

  return (
    <nav aria-label="Flight controls" className="control-dock glass-card">
      <DockButton
        active={control === "running"}
        icon="play"
        label="Start"
        onClick={() => setControl("running")}
      />
      <DockButton
        active={control === "paused"}
        icon="pause"
        label="Pause"
        onClick={() => setControl("paused")}
      />
      <span className="dock-divider" />
      <DockButton
        active={control === "returning"}
        icon="home"
        label="Return home"
        onClick={() => setControl("returning")}
      />
      <DockButton
        active={control === "emergency" || emergencyArmed}
        critical
        icon="stop"
        label={emergencyArmed ? "Confirm stop" : "Emergency"}
        onClick={emergency}
      />
    </nav>
  )
}

export default function App() {
  const [view, setView] = useState<"home" | "dashboard">("home")
  const theme: ThemeMode = "dark"
  const [scenario, setScenario] = useState<Scenario>("normal")
  const [control, setControl] = useState<FlightControlState>("running")
  const [dismissedWarning, setDismissedWarning] = useState<string | null>(null)
  const [clock, setClock] = useState("")
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [dummyEnabled, setDummyEnabled] = useState(false)

  const flying =
    view === "dashboard" && (control === "running" || control === "returning")
  const { telemetry: t, sendCommand } = useTelemetry(
    scenario,
    flying,
    dummyEnabled,
  )
  const warning = deriveWarning(t)
  const paused = !flying || t.mission.status === "complete"

  useEffect(() => {
    const update = () =>
      setClock(
        new Intl.DateTimeFormat("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }).format(new Date(t.timestamp)),
      )
    update()
    const timer = window.setInterval(update, 1000)
    return () => window.clearInterval(timer)
  }, [t.timestamp])

  // Reset per-mission UI state when a new mission/scenario starts
  const lastStatus = useRef(t.mission.status)
  useEffect(() => {
    setDetailsOpen(false)
    setDismissedWarning(null)
  }, [scenario])
  useEffect(() => {
    if (lastStatus.current === t.mission.status) return
    lastStatus.current = t.mission.status
    if (t.mission.status === "complete") setControl("paused")
  }, [t.mission.status])

  const appStatus = useMemo(() => {
    if (control === "emergency") return "Emergency stop engaged"
    if (control === "returning") return "Returning to home"
    if (control === "paused") return "Flight paused"
    if (t.mission.status === "complete") return "Mission complete"
    if (t.mission.status === "failed") return "Mission failed"
    return "Mission running"
  }, [control, t.mission.status])

  function changeControl(next: FlightControlState) {
    setControl(next)
    sendCommand(
      next === "running"
        ? "start"
        : next === "paused"
          ? "pause"
          : next === "returning"
            ? "returnHome"
            : "emergencyStop",
    )
  }

  function startScenario(next: Scenario) {
    setScenario(next)
    setControl(next === "missionComplete" ? "paused" : "running")
  }

  function retryMission() {
    startScenario("normal")
    sendCommand("start")
  }

  if (view === "home") {
    return (
      <HomePage
        onStart={() => {
          startScenario("normal")
          setView("dashboard")
        }}
      />
    )
  }

  return (
    <div className="app-shell" data-theme={theme}>
      <div aria-hidden="true" className="background-grid" />
      <TopBar
        clock={clock}
        dummyEnabled={dummyEnabled}
        onHome={() => setView("home")}
        onToggleDummy={() => setDummyEnabled((enabled) => !enabled)}
        scenario={scenario}
        setScenario={startScenario}
        t={t}
      />
      <div className="banner-stack">
        <WarningBanner
          dismissed={warning?.id === dismissedWarning}
          onDetails={() => setDetailsOpen(true)}
          onDismiss={() => setDismissedWarning(warning?.id ?? null)}
          onRetry={retryMission}
          warning={warning}
        />
      </div>
      <aside aria-label="Flight telemetry" className="left-column">
        <BatteryCard battery={t.battery} />
        <PositionCard t={t} />
        <MissionStats t={t} />
      </aside>
      <Hero paused={paused} t={t} />
      <aside aria-label="Altitude and mission" className="right-column">
        <AltitudeVisualizer altitude={t.altitude} />
        <MissionPanel detailsOpen={detailsOpen} onRetry={retryMission} t={t} />
      </aside>
      <ControlDock control={control} setControl={changeControl} />
      <p aria-live="polite" className="sr-only">
        {appStatus}
      </p>
      <div className={`flight-state state-${control}`} aria-hidden="true">
        {appStatus}
      </div>
    </div>
  )
}
