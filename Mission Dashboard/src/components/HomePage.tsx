import { useEffect, useRef, useState } from "react"
import { journeyMissions } from "../data/journeyMissions"
import Icon from "./Icons"
import MissionJourneyScene from "./journey/MissionJourneyScene"

const MIN_ZOOM = 0.72
const MAX_ZOOM = 6
const ZOOM_STEP = 0.35
const clampZoom = (value: number) =>
  Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, value))

export default function HomePage({ onStart }: { onStart: () => void }) {
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const [arrived, setArrived] = useState(false)
  const [intro, setIntro] = useState(true)
  const [acknowledged, setAcknowledged] = useState(false)
  const [hintVisible, setHintVisible] = useState(true)
  const [reducedMotion, setReducedMotion] = useState(false)
  const [zoom, setZoom] = useState(1)
  const cameraOrbit = useRef({ azimuth: 0, elevation: 0 })
  const pointers = useRef(new Map<number, { x: number y: number }>())
  const pinchDistance = useRef(0)
  const selected = selectedIndex >= 0 ? journeyMissions[selectedIndex] : null

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)")
    const update = () => setReducedMotion(query.matches)
    update()
    query.addEventListener("change", update)
    const introTimer = window.setTimeout(
      () => setIntro(false),
      query.matches ? 250 : 1900,
    )
    return () => {
      query.removeEventListener("change", update)
      window.clearTimeout(introTimer)
    }
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLElement && event.target.closest("button"))
        return
      if (event.key === "ArrowRight") {
        event.preventDefault()
        select(Math.min(journeyMissions.length - 1, selectedIndex + 1))
      } else if (event.key === "ArrowLeft") {
        event.preventDefault()
        select(Math.max(-1, selectedIndex - 1))
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  })

  function select(index: number) {
    if (index === selectedIndex && arrived) return
    setSelectedIndex(index)
    setArrived(false)
    setAcknowledged(false)
    setHintVisible(false)
  }

  function startMission() {
    if (acknowledged) return
    setAcknowledged(true)
    window.setTimeout(onStart, 480)
  }

  function pointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget.querySelector("canvas")) return
    pointers.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    })
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function pointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const previous = pointers.current.get(event.pointerId)
    if (!previous) return
    const dx = event.clientX - previous.x
    const dy = event.clientY - previous.y
    pointers.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY,
    })
    const activePointers = [...pointers.current.values()]
    if (activePointers.length > 1) {
      const distance = Math.hypot(
        activePointers[0].x - activePointers[1].x,
        activePointers[0].y - activePointers[1].y,
      )
      if (pinchDistance.current > 0) {
        const change = (pinchDistance.current - distance) * 0.003
        setZoom((value) => clampZoom(value + change))
      }
      pinchDistance.current = distance
      setHintVisible(false)
      return
    }
    pinchDistance.current = 0
    cameraOrbit.current.azimuth =
      (cameraOrbit.current.azimuth - dx * 0.006) % (Math.PI * 2)
    cameraOrbit.current.elevation = Math.max(
      -Math.PI * 0.42,
      Math.min(Math.PI * 0.42, cameraOrbit.current.elevation + dy * 0.004),
    )
    setHintVisible(false)
  }

  function pointerUp(event: React.PointerEvent<HTMLDivElement>) {
    pointers.current.delete(event.pointerId)
    pinchDistance.current = 0
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  function wheel(event: React.WheelEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget.querySelector("canvas")) return
    event.preventDefault()
    setZoom((value) => clampZoom(value + Math.sign(event.deltaY) * 0.22))
    setHintVisible(false)
  }

  return (
    <main
      className={`journey-page ${intro ? "is-intro" : "is-ready"}`}
      data-theme="dark"
    >
      <div
        aria-label="Interactive 3D mission journey"
        className="journey-canvas"
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerCancel={pointerUp}
        onPointerUp={pointerUp}
        onWheel={wheel}
      >
        <MissionJourneyScene
          arrived={arrived}
          cameraOrbit={cameraOrbit}
          onArrival={() => setArrived(true)}
          onSelect={select}
          reducedMotion={reducedMotion}
          selectedIndex={selectedIndex}
          zoom={zoom}
        />
      </div>

      <header className="journey-header">
          <span>
          </span>
        <div className="journey-progress">
          <small>JOURNEY POSITION</small>
          <strong>{selected ? `${selected.code} / 05` : "LAUNCH"}</strong>
          <div>
            {journeyMissions.map((mission, index) => (
              <i
                className={
                  selectedIndex === index
                    ? "current"
                    : selectedIndex > index
                      ? "complete"
                      : ""
                }
                key={mission.id}
              />
            ))}
          </div>
        </div>
      </header>

      {selected && arrived && (
        <section
          aria-live="polite"
          className={`journey-mission-panel side-${selected.panelSide}`}
        >
          <div className="journey-mission-kicker">
            <span>MISSION {selected.code}</span>
            <b>Current waypoint</b>
          </div>
          <h1>{selected.title}</h1>
          <p>{selected.description}</p>
          <button
            className={acknowledged ? "acknowledged" : ""}
            disabled={acknowledged}
            onClick={startMission}
            type="button"
          >
            <Icon name={acknowledged ? "check" : "play"} size={17} />
            {acknowledged ? "Mission ready" : "Start Mission"}
          </button>
        </section>
      )}

      <nav aria-label="Mission journey controls" className="journey-controls">
        <button
          disabled={selectedIndex < 0}
          onClick={() => select(selectedIndex - 1)}
          type="button"
        >
          <Icon name="arrowLeft" />
          <span>
            <small>PREVIOUS</small>
            {selectedIndex <= 0
              ? "Launch point"
              : journeyMissions[selectedIndex - 1].title}
          </span>
        </button>
        <div>
          <span>{selected ? selected.code : "00"}</span>
          <i />
          <b>05</b>
        </div>
        <button
          disabled={selectedIndex === journeyMissions.length - 1}
          onClick={() => select(selectedIndex + 1)}
          type="button"
        >
          <span>
            <small>NEXT</small>
            {journeyMissions[selectedIndex + 1]
              ? `Waypoint ${journeyMissions[selectedIndex + 1].code}`
              : "Journey complete"}
          </span>
          <Icon name="arrowRight" />
        </button>
      </nav>

      <div aria-label="Journey zoom controls" className="journey-zoom">
        <button
          aria-label="Zoom in"
          disabled={zoom <= MIN_ZOOM}
          onClick={() => setZoom((value) => clampZoom(value - ZOOM_STEP))}
          type="button"
        >
          <Icon name="plus" />
        </button>
        <button
          aria-label="Zoom out"
          disabled={zoom >= MAX_ZOOM}
          onClick={() => setZoom((value) => clampZoom(value + ZOOM_STEP))}
          type="button"
        >
          <Icon name="minus" />
        </button>
      </div>

      <p className={`journey-hint ${hintVisible ? "" : "hidden"}`}>
        <span>← →</span> Select a waypoint <i /> Drag to orbit <i /> Scroll to
        zoom
      </p>

      <p aria-live="polite" className="sr-only">
        {selected
          ? arrived
            ? `Arrived at mission ${selected.order}, ${selected.title}`
            : `Departing for waypoint ${selected.order}`
          : "At Rocky's planet launch point"}
      </p>

      <div aria-hidden="true" className="journey-intro">
        <span className="journey-brand-mark">
          <Icon name="drone" size={24} />
        </span>
        <strong>Plotting the Eridian route</strong>
        <i />
      </div>
    </main>
  )
}
