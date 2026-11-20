import { Html, Line, Sparkles, useGLTF, useProgress } from "@react-three/drei"
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber"
import {
  Suspense,
  useEffect,
  useMemo,
  useRef,
  type MutableRefObject,
} from "react"
import * as THREE from "three"
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js"
import {
  journeyMissions,
  LAUNCH_PROGRESS,
  type JourneyWaypointState,
} from "../../data/journeyMissions"
import SpaceScenery from "./SpaceScenery"

type FlightState = {
  progress: number
  target: number
  speed: number
  direction: number
  traveling: boolean
  arrivalTime: number
}

type SceneProps = {
  arrived: boolean
  selectedIndex: number
  reducedMotion: boolean
  cameraOrbit: MutableRefObject<{ azimuth: number; elevation: number }>
  zoom: number
  onSelect: (index: number) => void
  onArrival: () => void
}

// How far apart the waypoints are. Every route point (and so every waypoint,
// the star, the planet, the comet trench...) is multiplied by this.
const ROUTE_SCALE = 2.5
// Ship speed in the world, relative to the original route. Travel time grows
// by ROUTE_SCALE / TRAVEL_SPEED (about 1.9x). Raise it for quicker trips.
const TRAVEL_SPEED = 1.3
// Route progress per second is divided by the route's growth so world speed
// stays steady and the camera can keep up.
const SPEED_SCALE = TRAVEL_SPEED / ROUTE_SCALE

const routePoints = [
  new THREE.Vector3(-24, -5, 0),
  new THREE.Vector3(-20, 1, -3),
  new THREE.Vector3(-13, 8, -5),
  new THREE.Vector3(-5, 7, -9),
  new THREE.Vector3(2, 2, -8),
  new THREE.Vector3(10, -3, -6),
  new THREE.Vector3(16, -4, -2),
  new THREE.Vector3(19, 4, 3),
  new THREE.Vector3(8, 10, 6),
  new THREE.Vector3(-7, 4, 5),
  new THREE.Vector3(-23, -4, 1),
].map((point) => point.multiplyScalar(ROUTE_SCALE))

const routeCurve = new THREE.CatmullRomCurve3(
  routePoints,
  false,
  "catmullrom",
  0.32,
)
// More samples keep constant-speed motion along the longer curve smooth.
routeCurve.arcLengthDivisions = 1000

const routePoint = (progress: number, target?: THREE.Vector3) =>
  routeCurve.getPointAt(THREE.MathUtils.clamp(progress, 0, 1), target)

const routeTangent = (progress: number, target?: THREE.Vector3) =>
  routeCurve.getTangentAt(THREE.MathUtils.clamp(progress, 0, 1), target)

const TAU_PROGRESS = journeyMissions[0].progress
const RENDEZVOUS_PROGRESS = journeyMissions[1].progress
const TRENCH_PROGRESS = journeyMissions[3].progress
const PLANET_PROGRESS = journeyMissions[4].progress
const WORLD_UP = new THREE.Vector3(0, 1, 0)

// ---- Body sizes: the star (Tau Ceti) must be larger than the planet ----
// Tau Ceti. Core sphere, glow shells and ring all scale with TAU_RADIUS.
const TAU_RADIUS = 4.2 // was 1.85
const TAU_SCALE = TAU_RADIUS / 1.85
const TAU_OFFSET_Y = -(TAU_RADIUS + 0.85) // route passes just above the surface
// Rocky stays outside a sphere of radius RADIUS * SQUASH around the star,
// which is larger than the ring (4.2 * TAU_SCALE), so it never touches it.
const TAU_ORBIT_RADIUS = 5 * TAU_SCALE
const TAU_ORBIT_SQUASH = 0.9
const TAU_ORBIT_LIFT = 1.5
const TAU_CAMERA_SCALE = TAU_SCALE * 1.2

// Planet. Mesh radius, atmosphere and wireframe shell scale with PLANET_RADIUS.
const PLANET_RADIUS = 2.4 // was 6.1
const PLANET_SCALE = PLANET_RADIUS / 6.1
const PLANET_OFFSET_Y = -(PLANET_RADIUS + 0.2)
// The orbit's narrowest reach (RADIUS * SQUASH) must stay above the
// atmosphere (PLANET_RADIUS * 1.075).
const PLANET_ORBIT_RADIUS = PLANET_RADIUS * 1.75
const PLANET_ORBIT_SQUASH = 0.92
const PLANET_CAMERA_SCALE = PLANET_ORBIT_RADIUS / 7.1

const TAU_CENTER = routePoint(TAU_PROGRESS).add(
  new THREE.Vector3(0, TAU_OFFSET_Y, 0),
)
const PLANET_CENTER = routePoint(PLANET_PROGRESS).add(
  new THREE.Vector3(0, PLANET_OFFSET_Y, 0),
)
const RENDEZVOUS_POINT = routePoint(RENDEZVOUS_PROGRESS)
const RENDEZVOUS_TANGENT = routeTangent(RENDEZVOUS_PROGRESS).normalize()
const RENDEZVOUS_SIDE = new THREE.Vector3()
  .crossVectors(RENDEZVOUS_TANGENT, WORLD_UP)
  .normalize()
const RENDEZVOUS_ROCKY = RENDEZVOUS_POINT.clone().addScaledVector(
  RENDEZVOUS_SIDE,
  -2.25,
)
const RENDEZVOUS_HAIL = RENDEZVOUS_POINT.clone().addScaledVector(
  RENDEZVOUS_SIDE,
  2.25,
)
const ROUTE_SPHERE = new THREE.Sphere()
new THREE.Box3()
  .setFromPoints([
    ...Array.from({ length: 181 }, (_, index) => routePoint(index / 180)),
    TAU_CENTER.clone().addScalar(TAU_ORBIT_RADIUS * 0.8),
    TAU_CENTER.clone().addScalar(-TAU_ORBIT_RADIUS * 0.8),
    PLANET_CENTER.clone().addScalar(PLANET_ORBIT_RADIUS),
    PLANET_CENTER.clone().addScalar(-PLANET_ORBIT_RADIUS),
  ])
  .getBoundingSphere(ROUTE_SPHERE)

// Points the background scenery must stay away from: the route plus the
// star and planet.
const SCENERY_ANCHORS = [
  ...Array.from({ length: 241 }, (_, index) => routePoint(index / 240)),
  TAU_CENTER,
  PLANET_CENTER,
]

function orbitPosition(
  center: THREE.Vector3,
  angle: number,
  radius: number,
  target: THREE.Vector3,
  squash = 0.72,
) {
  return target.set(
    center.x + Math.cos(angle) * radius,
    center.y + Math.sin(angle * 0.7) * radius * 0.18,
    center.z + Math.sin(angle) * radius * squash,
  )
}

const sceneColors = {
  background: "#02050A",
  fog: "#07131B",
  route: "#42D9FF",
  routeDim: "#E96A5B",
  planet: "#1D8D91",
  atmosphere: "#63E6D1",
}

function SceneLoader() {
  const { progress } = useProgress()
  return (
    <Html center>
      <div className="journey-loader">
        <span />
        <b>{Math.round(progress)}%</b>
      </div>
    </Html>
  )
}

function Starfield() {
  const points = useRef<THREE.Points>(null)
  const geometry = useMemo(() => {
    const count = 1500
    const positions = new Float32Array(count * 3)
    const random = (() => {
      let seed = 9182
      return () => {
        seed = (seed * 16807) % 2147483647
        return (seed - 1) / 2147483646
      }
    })()
    for (let index = 0; index < count; index += 1) {
      const radius = ROUTE_SPHERE.radius * (1.8 + random() * 2.6)
      const theta = random() * Math.PI * 2
      const phi = Math.acos(2 * random() - 1)
      positions[index * 3] = radius * Math.sin(phi) * Math.cos(theta)
      positions[index * 3 + 1] = radius * Math.cos(phi)
      positions[index * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta)
    }
    const value = new THREE.BufferGeometry()
    value.setAttribute("position", new THREE.BufferAttribute(positions, 3))
    return value
  }, [])

  useFrame((state, delta) => {
    if (!points.current) return
    points.current.rotation.y += delta * 0.004
    points.current.rotation.x =
      Math.sin(state.clock.elapsedTime * 0.025) * 0.025
  })

  return (
    <points geometry={geometry} position={ROUTE_SPHERE.center} ref={points}>
      <pointsMaterial
        color="#D9F7FF"
        depthWrite={false}
        opacity={0.78}
        size={0.11 * ROUTE_SCALE}
        sizeAttenuation
        transparent
      />
    </points>
  )
}

function RockyPlanet() {
  const planet = useRef<THREE.Group>(null)
  const checkpoint = routePoint(PLANET_PROGRESS)

  useFrame((_, delta) => {
    if (planet.current) planet.current.rotation.y += delta * 0.025
  })

  return (
    <group position={checkpoint} ref={planet}>
      <mesh position={[0, PLANET_OFFSET_Y, 0]}>
        <sphereGeometry args={[PLANET_RADIUS, 64, 64]} />
        <meshStandardMaterial
          color={sceneColors.planet}
          metalness={0.08}
          roughness={0.78}
        />
      </mesh>
      <mesh position={[0, PLANET_OFFSET_Y, 0]} rotation={[0.2, 0, -0.1]}>
        <sphereGeometry args={[PLANET_RADIUS * 1.01, 48, 48]} />
        <meshStandardMaterial
          color="#F4C95D"
          emissive="#E96A5B"
          emissiveIntensity={0.18}
          opacity={0.18}
          transparent
          wireframe
        />
      </mesh>
      <mesh position={[0, PLANET_OFFSET_Y, 0]}>
        <sphereGeometry args={[PLANET_RADIUS * 1.075, 48, 48]} />
        <meshBasicMaterial
          blending={THREE.AdditiveBlending}
          color={sceneColors.atmosphere}
          opacity={0.16}
          side={THREE.BackSide}
          transparent
        />
      </mesh>
      <pointLight
        color="#F4C95D"
        intensity={45}
        position={[
          3 * PLANET_SCALE,
          PLANET_OFFSET_Y + 5 * PLANET_SCALE,
          5 * PLANET_SCALE,
        ]}
      />
    </group>
  )
}

function TauCeti() {
  const star = useRef<THREE.Group>(null)
  useFrame((_, delta) => {
    if (star.current) star.current.rotation.z += delta * 0.04
  })
  return (
    <group position={routePoint(TAU_PROGRESS)}>
      <group position={[0, TAU_OFFSET_Y, 0]} ref={star}>
        <mesh>
          <sphereGeometry args={[TAU_RADIUS, 48, 48]} />
          <meshBasicMaterial color="#FFF2B2" />
        </mesh>
        {[2.5, 3, 3.7].map((radius, index) => (
          <mesh key={radius} rotation={[index * 0.7, 0.2, index]}>
            <sphereGeometry args={[radius * 0.88 * TAU_SCALE, 32, 32]} />
            <meshBasicMaterial
              blending={THREE.AdditiveBlending}
              color={index === 2 ? "#E96A5B" : "#F4C95D"}
              opacity={0.1 / (index + 0.4)}
              transparent
              wireframe={index === 1}
            />
          </mesh>
        ))}
        <mesh rotation={[1.12, 0.2, 0.3]}>
          <torusGeometry
            args={[4.2 * TAU_SCALE, 0.025 * TAU_SCALE, 8, 128]}
          />
          <meshBasicMaterial
            blending={THREE.AdditiveBlending}
            color="#F4C95D"
            opacity={0.68}
            transparent
          />
        </mesh>
        <pointLight
          color="#FFF0A4"
          intensity={160 * TAU_SCALE ** 2}
          distance={24 * TAU_SCALE}
        />
      </group>
    </group>
  )
}

function AstrophageField({ active }: { active: boolean }) {
  const points = useRef<THREE.Points>(null)
  const center = routePoint(0.575)
  const geometry = useMemo(() => {
    const count = 600
    const positions = new Float32Array(count * 3)
    let seed = 773
    const random = () => {
      seed = (seed * 48271) % 2147483647
      return seed / 2147483647
    }
    for (let index = 0; index < count; index += 1) {
      positions[index * 3] = (random() - 0.5) * 12
      positions[index * 3 + 1] = (random() - 0.5) * 8
      positions[index * 3 + 2] = (random() - 0.5) * 10
    }
    const value = new THREE.BufferGeometry()
    value.setAttribute("position", new THREE.BufferAttribute(positions, 3))
    return value
  }, [])

  useFrame((state, delta) => {
    if (!points.current) return
    points.current.rotation.y += delta * (active ? 0.12 : 0.025)
    points.current.rotation.z =
      Math.sin(state.clock.elapsedTime * 0.22) * (active ? 0.18 : 0.04)
  })

  return (
    <group position={center}>
      <points geometry={geometry} ref={points}>
        <pointsMaterial
          blending={THREE.AdditiveBlending}
          color="#FF6B4A"
          depthWrite={false}
          opacity={active ? 0.92 : 0.52}
          size={active ? 0.13 : 0.08}
          transparent
        />
      </points>
      <Sparkles
        color="#F4C95D"
        count={60}
        opacity={active ? 0.8 : 0.25}
        scale={[9, 6, 7]}
        size={2}
        speed={active ? 1.2 : 0.2}
      />
    </group>
  )
}

function CometTrench({
  active,
  reducedMotion,
}: {
  active: boolean
  reducedMotion: boolean
}) {
  const group = useRef<THREE.Group>(null)
  const center = routePoint(TRENCH_PROGRESS)
  const comets = useMemo(
    () =>
      Array.from({ length: 42 }, (_, index) => {
        const angle = index * 2.399
        const radius = 3.4 + (index % 7) * 0.72
        return {
          x: Math.cos(angle) * radius,
          y: Math.sin(angle * 1.3) * radius * 0.55,
          phase: (index * 0.137) % 1,
          speed: 0.8 + (index % 5) * 0.11,
          scale: 0.12 + (index % 5) * 0.035,
        }
      }),
    [],
  )

  useFrame((state, delta) => {
    if (!group.current) return
    group.current.rotation.z +=
      delta * (active && !reducedMotion ? 0.025 : 0.006)
    group.current.children.forEach((child, index) => {
      const comet = comets[index]
      const pace = active ? (reducedMotion ? 0.035 : 0.18) : 0.018
      const phase =
        (state.clock.elapsedTime * pace * comet.speed + comet.phase) % 1
      if (active && index < 3) {
        const direction = index % 2 ? -1 : 1
        child.position.set(
          (phase - 0.5) * 7 * direction,
          (index - 1) * 0.65 + Math.sin(phase * Math.PI) * 0.8,
          7 - phase * 14,
        )
      } else {
        child.position.set(
          comet.x + Math.sin(phase * Math.PI * 2) * 0.35,
          comet.y,
          8 - phase * 16,
        )
      }
    })
  })

  return (
    <group position={center} ref={group}>
      {comets.map((comet, index) => (
        <group key={index}>
          <mesh scale={comet.scale}>
            <dodecahedronGeometry args={[1, 0]} />
            <meshStandardMaterial color="#6C7A86" roughness={0.9} />
          </mesh>
          <mesh position={[0, 0, 0.75]} rotation={[Math.PI / 2, 0, 0]}>
            <coneGeometry
              args={[comet.scale * 0.7, comet.scale * 9, 6, 1, true]}
            />
            <meshBasicMaterial
              blending={THREE.AdditiveBlending}
              color={index % 3 ? "#42D9FF" : "#F4C95D"}
              opacity={active ? 0.42 : 0.13}
              side={THREE.DoubleSide}
              transparent
            />
          </mesh>
        </group>
      ))}
    </group>
  )
}

function HailMaryModel() {
  const { scene } = useGLTF("/models/journey/hail-mary.glb")
  const model = useMemo(() => {
    const value = scene.clone(true)
    value.updateMatrixWorld(true)
    const box = new THREE.Box3().setFromObject(value)
    const size = box.getSize(new THREE.Vector3())
    const center = box.getCenter(new THREE.Vector3())
    const scale = 3.1 / Math.max(size.x, size.y, size.z)
    value.scale.setScalar(scale)
    value.position.copy(center).multiplyScalar(-scale)
    value.rotation.set(0, Math.PI / 2, 0)
    value.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.castShadow = true
        child.material = child.material.clone()
      }
    })
    return value
  }, [scene])
  return <primitive object={model} />
}

function RockyShipModel() {
  const [centerSource, connectorSource, wingSource] = useLoader(STLLoader, [
    "/models/journey/rocky-center.stl",
    "/models/journey/rocky-connectors.stl",
    "/models/journey/rocky-wings.stl",
  ])
  const { center, connector, wing } = useMemo(() => {
    const prepare = (source: THREE.BufferGeometry) => {
      const geometry = source.clone()
      geometry.center()
      geometry.computeVertexNormals()
      return geometry
    }
    const preparedWing = prepare(wingSource)
    preparedWing.rotateY(Math.PI / 2)
    return {
      center: prepare(centerSource),
      connector: prepare(connectorSource),
      wing: preparedWing,
    }
  }, [centerSource, connectorSource, wingSource])

  return (
    <group rotation={[0, Math.PI / 2, 0]} scale={0.72}>
      {[-1, 1].map((deck) => (
        <group key={deck} position={[0, deck * 0.42, 0]}>
          {[-1, 1].map((side) => (
            <mesh
              castShadow
              geometry={wing}
              key={side}
              position={[side * 2.15, 0, 0]}
              rotation={[0, side < 0 ? Math.PI : 0, 0]}
              scale={[0.018, 0.018, 0.018]}
            >
              <meshStandardMaterial
                color={deck > 0 ? "#B88725" : "#6E4B16"}
                emissive="#513106"
                emissiveIntensity={0.06}
                metalness={0.9}
                roughness={0.22}
              />
            </mesh>
          ))}
          <mesh geometry={connector} scale={0.018}>
            <meshStandardMaterial
              color="#D5A637"
              metalness={0.9}
              roughness={0.2}
            />
          </mesh>
        </group>
      ))}
      <mesh geometry={center} rotation={[Math.PI / 2, 0, 0]} scale={0.014}>
        <meshStandardMaterial
          color="#100E0B"
          metalness={0.84}
          roughness={0.24}
        />
      </mesh>
      <mesh position={[0, 0.05, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.86, 0.75, 0.5, 6]} />
        <meshStandardMaterial
          color="#17130D"
          emissive="#543306"
          emissiveIntensity={0.06}
          metalness={0.9}
          roughness={0.24}
        />
      </mesh>
      {Array.from({ length: 7 }, (_, index) => {
        const z = (index - 3) * 0.2
        return (
          <group key={index}>
            <mesh position={[0, 0.92, z]}>
              <boxGeometry args={[0.1, 1.42, 0.13]} />
              <meshStandardMaterial
                color={index % 2 ? "#E3B64B" : "#332515"}
                metalness={0.9}
                roughness={0.2}
              />
            </mesh>
            <mesh position={[0, -0.86, z]}>
              <boxGeometry args={[0.09, 1.2, 0.11]} />
              <meshStandardMaterial
                color={index % 2 ? "#A87920" : "#19130D"}
                metalness={0.88}
                roughness={0.24}
              />
            </mesh>
          </group>
        )
      })}
      <pointLight color="#FFB52E" intensity={6} position={[-0.8, 0, 0]} />
    </group>
  )
}

function ShipFallback() {
  return (
    <mesh rotation={[0, 0, -Math.PI / 2]}>
      <coneGeometry args={[0.5, 2.3, 6]} />
      <meshStandardMaterial color="#D8A637" metalness={0.7} />
    </mesh>
  )
}

function JourneyShips({
  arrived,
  flight,
  reducedMotion,
  selectedIndex,
}: {
  arrived: boolean
  flight: MutableRefObject<FlightState>
  reducedMotion: boolean
  selectedIndex: number
}) {
  const rocky = useRef<THREE.Group>(null)
  const hail = useRef<THREE.Group>(null)
  const rockyOrbitBlend = useRef(0)
  const hailOrbitBlend = useRef(0)
  const tangent = useMemo(() => new THREE.Vector3(), [])
  const position = useMemo(() => new THREE.Vector3(), [])
  const side = useMemo(() => new THREE.Vector3(), [])
  const rockyPosition = useMemo(() => new THREE.Vector3(), [])
  const hailPosition = useMemo(() => new THREE.Vector3(), [])
  const orbitTarget = useMemo(() => new THREE.Vector3(), [])
  const orbitNext = useMemo(() => new THREE.Vector3(), [])
  const rockyDirection = useMemo(() => new THREE.Vector3(), [])
  const hailDirection = useMemo(() => new THREE.Vector3(), [])
  const lookTarget = useMemo(() => new THREE.Vector3(), [])
  const rockyQuaternion = useMemo(() => new THREE.Quaternion(), [])
  const hailQuaternion = useMemo(() => new THREE.Quaternion(), [])
  const matrix = useMemo(() => new THREE.Matrix4(), [])
  const bankEuler = useMemo(() => new THREE.Euler(), [])
  const bankQuaternion = useMemo(() => new THREE.Quaternion(), [])
  const modelCorrection = useMemo(
    () =>
      new THREE.Quaternion().setFromEuler(new THREE.Euler(0, -Math.PI / 2, 0)),
    [],
  )

  useFrame((state, delta) => {
    const progress = flight.current.progress
    routePoint(progress, position)
    routeTangent(progress, tangent).normalize()
    side.crossVectors(tangent, WORLD_UP).normalize()
    const bank =
      reducedMotion || !flight.current.traveling
        ? 0
        : Math.sin(progress * 44) *
          Math.min(0.48, Math.abs(flight.current.speed) * 0.05)
    const beforeHandoff = progress <= RENDEZVOUS_PROGRESS
    const approach = THREE.MathUtils.smoothstep(
      progress,
      0.32,
      RENDEZVOUS_PROGRESS,
    )
    const departure = THREE.MathUtils.smoothstep(
      progress,
      RENDEZVOUS_PROGRESS,
      0.455,
    )

    if (beforeHandoff) {
      rockyPosition
        .copy(position)
        .addScaledVector(RENDEZVOUS_SIDE, -2.25 * approach)
      hailPosition.copy(RENDEZVOUS_HAIL)
    } else {
      rockyPosition.copy(RENDEZVOUS_ROCKY)
      hailPosition
        .copy(position)
        .addScaledVector(RENDEZVOUS_SIDE, 2.25 * (1 - departure))
    }

    const synchronized =
      selectedIndex === 1 && arrived && !flight.current.traveling
    if (synchronized) {
      const drift = reducedMotion
        ? Math.sin(state.clock.elapsedTime * 0.35) * 0.025
        : Math.sin(state.clock.elapsedTime * 0.72) * 0.12
      rockyPosition.y += drift
      hailPosition.y += drift
    }

    const rockyHoldingOrbit =
      !flight.current.traveling &&
      (selectedIndex < 0 || (selectedIndex === 0 && arrived))
    const hailHoldingOrbit =
      !flight.current.traveling && selectedIndex === 4 && arrived
    rockyOrbitBlend.current = THREE.MathUtils.damp(
      rockyOrbitBlend.current,
      rockyHoldingOrbit ? 1 : 0,
      2.6,
      delta,
    )
    hailOrbitBlend.current = THREE.MathUtils.damp(
      hailOrbitBlend.current,
      hailHoldingOrbit ? 1 : 0,
      2.6,
      delta,
    )

    const rockyOrbitCenter =
      selectedIndex < 0 || progress < 0.1 ? PLANET_CENTER : TAU_CENTER
    const rockyOnPlanet = rockyOrbitCenter === PLANET_CENTER
    const rockyRadius = rockyOnPlanet ? PLANET_ORBIT_RADIUS : TAU_ORBIT_RADIUS
    const rockySquash = rockyOnPlanet ? PLANET_ORBIT_SQUASH : TAU_ORBIT_SQUASH
    const rockyAngle =
      state.clock.elapsedTime * (reducedMotion ? 0.035 : 0.16) + 0.45
    orbitPosition(
      rockyOrbitCenter,
      rockyAngle,
      rockyRadius,
      orbitTarget,
      rockySquash,
    )
    orbitPosition(
      rockyOrbitCenter,
      rockyAngle + 0.015,
      rockyRadius,
      orbitNext,
      rockySquash,
    )
    // Raise Rocky's orbit around Tau Ceti (planet orbit is unchanged).
    // Tune TAU_ORBIT_LIFT to taste.
    const rockyLift = rockyOnPlanet ? 0 : TAU_ORBIT_LIFT
    orbitTarget.y += rockyLift
    orbitNext.y += rockyLift
    rockyDirection.copy(orbitNext).sub(orbitTarget).normalize()
    rockyPosition.lerp(orbitTarget, rockyOrbitBlend.current)

    const hailAngle =
      state.clock.elapsedTime * (reducedMotion ? 0.028 : 0.12) + 1.1
    orbitPosition(
      PLANET_CENTER,
      hailAngle,
      PLANET_ORBIT_RADIUS,
      orbitTarget,
      PLANET_ORBIT_SQUASH,
    )
    orbitPosition(
      PLANET_CENTER,
      hailAngle + 0.015,
      PLANET_ORBIT_RADIUS,
      orbitNext,
      PLANET_ORBIT_SQUASH,
    )
    hailDirection.copy(orbitNext).sub(orbitTarget).normalize()
    hailPosition.lerp(orbitTarget, hailOrbitBlend.current)

    if (rockyOrbitBlend.current < 0.5) {
      rockyDirection.copy(beforeHandoff ? tangent : RENDEZVOUS_TANGENT)
    }
    if (hailOrbitBlend.current < 0.5) {
      hailDirection.copy(beforeHandoff ? RENDEZVOUS_TANGENT : tangent)
    }

    let dodgeBank = 0
    if (
      selectedIndex === 3 &&
      (arrived || progress > RENDEZVOUS_PROGRESS + 0.22)
    ) {
      const phase = state.clock.elapsedTime * (reducedMotion ? 0.25 : 0.6)
      const lateral = Math.sin(phase * 1.7)
      const vertical = Math.sin(phase * 2.65 + 0.8)
      hailPosition.addScaledVector(side, lateral * (reducedMotion ? 0.1 : 0.45))
      hailPosition.y += vertical * (reducedMotion ? 0.04 : 0.2)
      dodgeBank = reducedMotion ? 0.02 : -lateral * 0.1
    }

    lookTarget.copy(rockyPosition).add(rockyDirection)
    matrix.lookAt(rockyPosition, lookTarget, WORLD_UP)
    rockyQuaternion.setFromRotationMatrix(matrix).multiply(modelCorrection)
    lookTarget.copy(hailPosition).add(hailDirection)
    matrix.lookAt(hailPosition, lookTarget, WORLD_UP)
    hailQuaternion.setFromRotationMatrix(matrix).multiply(modelCorrection)

    // Bank/roll is added to the TARGET orientation before smoothing.
    // (Applying rotateX/rotateZ after slerp accumulated every frame.)
    const wobble =
      Math.sin(state.clock.elapsedTime * 0.72) * (reducedMotion ? 0.01 : 0.045)

    if (rocky.current) {
      rocky.current.position.copy(rockyPosition)
      bankEuler.set(
        bank * (beforeHandoff ? 1 : 0.15),
        0,
        synchronized ? wobble : 0,
      )
      rockyQuaternion.multiply(bankQuaternion.setFromEuler(bankEuler))
      rocky.current.quaternion.slerp(rockyQuaternion, 1 - Math.exp(-delta * 6))
      rocky.current.scale.setScalar(1)
      rocky.current.visible = true
    }
    if (hail.current) {
      hail.current.position.copy(hailPosition)
      bankEuler.set(
        bank * (beforeHandoff ? 0.1 : 0.78),
        0,
        dodgeBank + (synchronized ? wobble : 0),
      )
      hailQuaternion.multiply(bankQuaternion.setFromEuler(bankEuler))
      hail.current.quaternion.slerp(hailQuaternion, 1 - Math.exp(-delta * 5))
      hail.current.scale.setScalar(1)
      hail.current.visible = progress > 0.275 || selectedIndex >= 1
    }
  })

  return (
    <>
      <group ref={rocky}>
        <Suspense fallback={<ShipFallback />}>
          <RockyShipModel />
        </Suspense>
        <pointLight color="#FFB52E" intensity={8} position={[-1.5, 0, 0]} />
      </group>
      <group ref={hail}>
        <Suspense fallback={<ShipFallback />}>
          <HailMaryModel />
        </Suspense>
        <pointLight color="#42D9FF" intensity={10} position={[-2, 0, 0]} />
      </group>
    </>
  )
}

function JourneyRoute({
  arrived,
  selectedIndex,
  onSelect,
}: {
  arrived: boolean
  selectedIndex: number
  onSelect: (index: number) => void
}) {
  const points = useMemo(
    () => Array.from({ length: 721 }, (_, index) => routePoint(index / 720)),
    [],
  )
  const activeEnd =
    selectedIndex < 0
      ? LAUNCH_PROGRESS
      : journeyMissions[selectedIndex].progress
  const activePoints = useMemo(
    () =>
      Array.from({ length: 360 }, (_, index) =>
        routePoint((index / 359) * activeEnd),
      ),
    [activeEnd],
  )

  return (
    <>
      <Line
        color={sceneColors.routeDim}
        lineWidth={1.1}
        opacity={0.32}
        points={points}
        transparent
      />
      <Line
        color={sceneColors.route}
        lineWidth={2.2}
        opacity={0.88}
        points={activePoints}
        transparent
      />
      {journeyMissions.map((mission, index) => {
        const state: JourneyWaypointState =
          selectedIndex === index
            ? "current"
            : selectedIndex > index
              ? "completed"
              : "upcoming"
        const position = routePoint(mission.progress)
        const revealed =
          index < selectedIndex || (index === selectedIndex && arrived)
        return (
          <group key={mission.id} position={position}>
            <mesh>
              <sphereGeometry
                args={[state === "current" ? 0.24 : 0.16, 24, 24]}
              />
              <meshBasicMaterial
                color={
                  state === "completed"
                    ? "#9BD6C0"
                    : state === "current"
                      ? "#F4C95D"
                      : "#42D9FF"
                }
              />
            </mesh>
            <mesh>
              <ringGeometry args={[0.34, 0.38, 48]} />
              <meshBasicMaterial
                color={
                  state === "completed"
                    ? "#9BD6C0"
                    : state === "current"
                      ? "#F4C95D"
                      : "#42D9FF"
                }
                opacity={state === "upcoming" ? 0.3 : 0.72}
                side={THREE.DoubleSide}
                transparent
              />
            </mesh>
            <pointLight
              color={
                state === "completed"
                  ? "#9BD6C0"
                  : state === "current"
                    ? "#F4C95D"
                    : "#42D9FF"
              }
              distance={5}
              intensity={state === "current" ? 14 : 4}
            />
            <Html
              center
              className="journey-node-html"
              distanceFactor={10}
              position={[0, 0.85, 0]}
              sprite
              transform
            >
              <button
                aria-label={
                  revealed
                    ? `Select mission ${mission.order}: ${mission.title}. ${state}`
                    : `Select waypoint ${mission.order}. ${state}`
                }
                className={`journey-node-label ${state}`}
                onClick={() => onSelect(index)}
                type="button"
              >
                <span>WAYPOINT {mission.code}</span>
                <b>{revealed ? mission.title : "Identity classified"}</b>
                <i>{state}</i>
              </button>
            </Html>
          </group>
        )
      })}
    </>
  )
}

function CameraRig({
  cameraOrbit,
  flight,
  reducedMotion,
  selectedIndex,
  zoom,
}: {
  cameraOrbit: MutableRefObject<{ azimuth: number; elevation: number }>
  flight: MutableRefObject<FlightState>
  reducedMotion: boolean
  selectedIndex: number
  zoom: number
}) {
  const { camera } = useThree()
  const targetPosition = useMemo(() => new THREE.Vector3(), [])
  const shipPosition = useMemo(() => new THREE.Vector3(), [])
  const localFocus = useMemo(() => new THREE.Vector3(), [])
  const targetFocus = useMemo(() => new THREE.Vector3(), [])
  const look = useMemo(() => ROUTE_SPHERE.center.clone(), [])

  useFrame((state, delta) => {
    const progress = flight.current.progress
    routePoint(progress, shipPosition)
    const preset =
      selectedIndex >= 0 ? journeyMissions[selectedIndex].camera : "planetOrbit"
    if (selectedIndex < 0 || selectedIndex === 4) {
      localFocus.copy(PLANET_CENTER)
    } else if (selectedIndex === 0) {
      localFocus.copy(TAU_CENTER)
    } else if (selectedIndex === 1) {
      localFocus.copy(RENDEZVOUS_POINT)
    } else {
      localFocus.copy(shipPosition)
    }

    const overviewBlend = THREE.MathUtils.smoothstep(zoom, 2.2, 6)
    targetFocus.copy(localFocus).lerp(ROUTE_SPHERE.center, overviewBlend)
    const baseDistance =
      preset === "close"
        ? 6.2
        : preset === "chase"
          ? 8.2
          : preset === "orbit"
            ? 10.5
            : preset === "planetOrbit"
              ? 17.5
              : 9.6
    // Frame the star and planet at their new sizes.
    const focusScale =
      selectedIndex === 0
        ? TAU_CAMERA_SCALE
        : selectedIndex < 0 || selectedIndex === 4
          ? PLANET_CAMERA_SCALE
          : 1
    const localDistance = baseDistance * focusScale * Math.min(zoom, 2.2)
    const overviewDistance =
      (ROUTE_SPHERE.radius / Math.tan(THREE.MathUtils.degToRad(21))) * 1.3
    const distance = THREE.MathUtils.lerp(
      localDistance,
      overviewDistance,
      overviewBlend,
    )
    const presetAzimuth =
      preset === "flyby"
        ? 1.12
        : preset === "orbit"
          ? 0.7
          : preset === "planetOrbit"
            ? 0.55
            : preset === "chase"
              ? 0.25
              : 0.82
    const azimuth = presetAzimuth + cameraOrbit.current.azimuth
    const elevation = THREE.MathUtils.clamp(
      0.28 + cameraOrbit.current.elevation,
      -Math.PI * 0.46,
      Math.PI * 0.46,
    )
    const horizontalDistance = Math.cos(elevation) * distance
    targetPosition.set(
      targetFocus.x + Math.sin(azimuth) * horizontalDistance,
      targetFocus.y + Math.sin(elevation) * distance,
      targetFocus.z + Math.cos(azimuth) * horizontalDistance,
    )

    if (!reducedMotion && selectedIndex === 3) {
      const nearMiss = Math.pow(
        Math.max(0, Math.sin(state.clock.elapsedTime * 3.9)),
        12,
      )
      const shake = Math.sin(state.clock.elapsedTime * 37) * 0.09 * nearMiss
      targetPosition.x += shake
      targetPosition.y -= shake * 0.7
    }

    // Follow rates scale with ship speed so the camera doesn't fall behind.
    camera.position.lerp(
      targetPosition,
      1 - Math.exp(-delta * (reducedMotion ? 8 : 2.8 * TRAVEL_SPEED)),
    )
    look.lerp(
      targetFocus,
      1 - Math.exp(-delta * (reducedMotion ? 9 : 4.2 * TRAVEL_SPEED)),
    )
    camera.lookAt(look)
    if (camera instanceof THREE.PerspectiveCamera) {
      const targetFov =
        !reducedMotion && selectedIndex === 3 && overviewBlend < 0.2 ? 47 : 42
      camera.fov = THREE.MathUtils.damp(camera.fov, targetFov, 3, delta)
      camera.updateProjectionMatrix()
    }
  })
  return null
}

function FlightController({
  flight,
  onArrival,
  reducedMotion,
  target,
}: {
  flight: MutableRefObject<FlightState>
  onArrival: () => void
  reducedMotion: boolean
  target: number
}) {
  const arrivalSent = useRef(true)

  useEffect(() => {
    flight.current.target = target
    const distance = Math.abs(target - flight.current.progress)
    if (distance > 0.001) {
      flight.current.traveling = true
      flight.current.direction = Math.sign(target - flight.current.progress)
      arrivalSent.current = false
    }
  }, [flight, target])

  useFrame((state, delta) => {
    const value = flight.current
    const remaining = Math.abs(value.target - value.progress)
    if (remaining < 0.0007) {
      value.progress = value.target
      value.speed = THREE.MathUtils.damp(value.speed, 0, 8, delta)
      if (value.traveling) {
        value.traveling = false
        value.arrivalTime = state.clock.elapsedTime
      }
      if (!arrivalSent.current) {
        arrivalSent.current = true
        onArrival()
      }
      return
    }

    const acceleration = THREE.MathUtils.smoothstep(remaining, 0.004, 0.08)
    const maxSpeed =
      (reducedMotion ? 0.24 : remaining > 0.22 ? 0.13 : 0.1) * SPEED_SCALE
    const targetSpeed = Math.max(0.018 * SPEED_SCALE, maxSpeed * acceleration)
    value.speed = THREE.MathUtils.damp(value.speed, targetSpeed, 4.5, delta)
    value.direction = Math.sign(value.target - value.progress)
    value.progress += value.direction * Math.min(remaining, value.speed * delta)
  })
  return null
}

function SceneContent(props: SceneProps) {
  const { scene } = useThree()
  const flight = useRef<FlightState>({
    progress: LAUNCH_PROGRESS,
    target: LAUNCH_PROGRESS,
    speed: 0,
    direction: 1,
    traveling: false,
    arrivalTime: 0,
  })
  const target =
    props.selectedIndex < 0
      ? LAUNCH_PROGRESS
      : journeyMissions[props.selectedIndex].progress

  useEffect(() => {
    scene.background = new THREE.Color(sceneColors.background)
    scene.fog = new THREE.FogExp2(sceneColors.fog, 0.012 / ROUTE_SCALE)
  }, [scene])

  return (
    <>
      <ambientLight intensity={0.52} />
      <directionalLight
        color="#FFF1C7"
        intensity={2.1}
        position={[8, 14, 12]}
      />
      <Starfield />
      <SpaceScenery
        anchors={SCENERY_ANCHORS}
        center={ROUTE_SPHERE.center}
        radius={ROUTE_SPHERE.radius}
        reducedMotion={props.reducedMotion}
      />
      <RockyPlanet />
      <TauCeti />
      <AstrophageField active={props.selectedIndex === 2} />
      <CometTrench
        active={props.selectedIndex === 3}
        reducedMotion={props.reducedMotion}
      />
      <JourneyRoute
        arrived={props.arrived}
        onSelect={props.onSelect}
        selectedIndex={props.selectedIndex}
      />
      <JourneyShips
        arrived={props.arrived}
        flight={flight}
        reducedMotion={props.reducedMotion}
        selectedIndex={props.selectedIndex}
      />
      <FlightController
        flight={flight}
        onArrival={props.onArrival}
        reducedMotion={props.reducedMotion}
        target={target}
      />
      <CameraRig
        cameraOrbit={props.cameraOrbit}
        flight={flight}
        reducedMotion={props.reducedMotion}
        selectedIndex={props.selectedIndex}
        zoom={props.zoom}
      />
    </>
  )
}

export default function MissionJourneyScene(props: SceneProps) {
  return (
    <Canvas
      camera={{
        far: Math.ceil(ROUTE_SPHERE.radius * 16),
        fov: 42,
        near: 0.1,
        position: [-18 * ROUTE_SCALE, 1 * ROUTE_SCALE, 9 * ROUTE_SCALE],
      }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, powerPreference: "high-performance" }}
    >
      <Suspense fallback={<SceneLoader />}>
        <SceneContent {...props} />
      </Suspense>
    </Canvas>
  )
}

useGLTF.preload("/models/journey/hail-mary.glb")
useLoader.preload(STLLoader, "/models/journey/rocky-center.stl")
useLoader.preload(STLLoader, "/models/journey/rocky-connectors.stl")
useLoader.preload(STLLoader, "/models/journey/rocky-wings.stl")