import { useFrame, useThree } from "@react-three/fiber"
import { useEffect, useMemo, useRef, type MutableRefObject } from "react"
import * as THREE from "three"

/**
 * Everything that fills the empty space around the mission route:
 * twinkling stars, a Milky Way band, spiral galaxies, nebulae, bright stars,
 * gas/rocky/ice/lava planets (with rings and moons), asteroid belts, a black
 * hole, binary stars, small star systems, free-flying comets and drifting dust.
 *
 * Placement is seeded (the same every load) and keeps clear of the route.
 */

type Random = () => number
type RGB = [number, number, number]
type Tilt = [number, number, number]

type SpaceSceneryProps = {
  /** Points the scenery must keep away from (route samples, star, planet...). */
  anchors: THREE.Vector3[]
  /** Center and radius of the sphere that contains the whole journey. */
  center: THREE.Vector3
  radius: number
  reducedMotion: boolean
}

/* -------------------------------------------------------------------------- */
/* Shared uniforms, random, placement                                         */
/* -------------------------------------------------------------------------- */

const shared = {
  uTime: { value: 0 },
  uPixelRatio: { value: 1 },
}

function createRandom(seed: number): Random {
  let value = seed >>> 0
  return () => {
    value = (value + 0x6d2b79f5) >>> 0
    let t = value
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function randomDirection(random: Random) {
  const theta = random() * Math.PI * 2
  const z = random() * 2 - 1
  const ring = Math.sqrt(1 - z * z)
  return new THREE.Vector3(ring * Math.cos(theta), z, ring * Math.sin(theta))
}

/** Roughly normal, range about -2..2. */
function gaussian(random: Random) {
  return random() + random() + random() + random() - 2
}

function pick<T>(random: Random, items: T[]): T {
  return items[Math.floor(random() * items.length)]
}

function distanceToAnchors(point: THREE.Vector3, anchors: THREE.Vector3[]) {
  let min = Infinity
  for (const anchor of anchors) {
    const distance = point.distanceToSquared(anchor)
    if (distance < min) min = distance
  }
  return Math.sqrt(min)
}

function segmentClearance(
  start: THREE.Vector3,
  end: THREE.Vector3,
  anchors: THREE.Vector3[],
) {
  const point = new THREE.Vector3()
  let min = Infinity
  for (let index = 0; index <= 24; index += 1) {
    point.lerpVectors(start, end, index / 24)
    min = Math.min(min, distanceToAnchors(point, anchors))
  }
  return min
}

function createPlacer(
  random: Random,
  center: THREE.Vector3,
  anchors: THREE.Vector3[],
) {
  const occupied: { position: THREE.Vector3; radius: number }[] = []
  return (
    minRadius: number,
    maxRadius: number,
    bodyRadius: number,
    clearance: number,
  ) => {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const distance = Math.cbrt(
        minRadius ** 3 + random() * (maxRadius ** 3 - minRadius ** 3),
      )
      const position = randomDirection(random).multiplyScalar(distance)
      position.add(center)
      if (distanceToAnchors(position, anchors) < clearance + bodyRadius) {
        continue
      }
      if (
        occupied.some(
          (other) =>
            other.position.distanceTo(position) < other.radius + bodyRadius,
        )
      ) {
        continue
      }
      occupied.push({ position, radius: bodyRadius })
      return position
    }
    return null
  }
}

/* -------------------------------------------------------------------------- */
/* Textures (generated once on canvases)                                      */
/* -------------------------------------------------------------------------- */

function makeCanvas(width: number, height: number) {
  const canvas = document.createElement("canvas")
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext("2d")!
  return { canvas, context }
}

function toTexture(canvas: HTMLCanvasElement) {
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

let glowTexture: THREE.CanvasTexture | null = null
function getGlowTexture() {
  if (!glowTexture) {
    const { canvas, context } = makeCanvas(128, 128)
    const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64)
    gradient.addColorStop(0, "rgba(255,255,255,1)")
    gradient.addColorStop(0.2, "rgba(255,255,255,0.55)")
    gradient.addColorStop(0.5, "rgba(255,255,255,0.14)")
    gradient.addColorStop(1, "rgba(255,255,255,0)")
    context.fillStyle = gradient
    context.fillRect(0, 0, 128, 128)
    glowTexture = toTexture(canvas)
  }
  return glowTexture
}

let spikeTexture: THREE.CanvasTexture | null = null
function getSpikeTexture() {
  if (!spikeTexture) {
    const { canvas, context } = makeCanvas(256, 256)
    const horizontal = context.createLinearGradient(0, 0, 256, 0)
    horizontal.addColorStop(0, "rgba(255,255,255,0)")
    horizontal.addColorStop(0.5, "rgba(255,255,255,0.9)")
    horizontal.addColorStop(1, "rgba(255,255,255,0)")
    context.fillStyle = horizontal
    context.fillRect(0, 126, 256, 4)
    const vertical = context.createLinearGradient(0, 0, 0, 256)
    vertical.addColorStop(0, "rgba(255,255,255,0)")
    vertical.addColorStop(0.5, "rgba(255,255,255,0.9)")
    vertical.addColorStop(1, "rgba(255,255,255,0)")
    context.fillStyle = vertical
    context.fillRect(126, 0, 4, 256)
    spikeTexture = toTexture(canvas)
  }
  return spikeTexture
}

let ringGlowTexture: THREE.CanvasTexture | null = null
/** Thin bright ring (photon ring). The ring sits at 0.62 of the half width. */
function getRingGlowTexture() {
  if (!ringGlowTexture) {
    const { canvas, context } = makeCanvas(256, 256)
    const gradient = context.createRadialGradient(128, 128, 0, 128, 128, 128)
    gradient.addColorStop(0, "rgba(255,200,120,0)")
    gradient.addColorStop(0.5, "rgba(255,190,110,0)")
    gradient.addColorStop(0.62, "rgba(255,238,205,0.95)")
    gradient.addColorStop(0.7, "rgba(255,150,70,0.35)")
    gradient.addColorStop(1, "rgba(255,120,60,0)")
    context.fillStyle = gradient
    context.fillRect(0, 0, 256, 256)
    ringGlowTexture = toTexture(canvas)
  }
  return ringGlowTexture
}

const cloudTextures: (THREE.CanvasTexture | undefined)[] = []
function getCloudTexture(index: number) {
  const cached = cloudTextures[index]
  if (cached) return cached
  const random = createRandom(1000 + index * 77)
  const size = 256
  const { canvas, context } = makeCanvas(size, size)
  for (let blob = 0; blob < 60; blob += 1) {
    const x = size * (0.2 + 0.6 * random())
    const y = size * (0.2 + 0.6 * random())
    const radius = size * (0.08 + 0.18 * random())
    const alpha = 0.05 + random() * 0.12
    const gradient = context.createRadialGradient(x, y, 0, x, y, radius)
    gradient.addColorStop(0, `rgba(255,255,255,${alpha})`)
    gradient.addColorStop(1, "rgba(255,255,255,0)")
    context.fillStyle = gradient
    context.fillRect(0, 0, size, size)
  }
  context.globalCompositeOperation = "destination-in"
  const mask = context.createRadialGradient(
    size / 2,
    size / 2,
    0,
    size / 2,
    size / 2,
    size / 2,
  )
  mask.addColorStop(0, "rgba(0,0,0,1)")
  mask.addColorStop(0.7, "rgba(0,0,0,0.6)")
  mask.addColorStop(1, "rgba(0,0,0,0)")
  context.fillStyle = mask
  context.fillRect(0, 0, size, size)
  const texture = toTexture(canvas)
  cloudTextures[index] = texture
  return texture
}

type PlanetKind = "gas" | "rocky" | "ice" | "lava"

const PLANET_PALETTES: Record<PlanetKind, string[][]> = {
  gas: [
    ["#E8C58A", "#C98B52", "#F4E3C1", "#A5653A"],
    ["#8FB8E8", "#5E86C4", "#D2E4F7", "#3F5F9E"],
    ["#D88FD0", "#9C5BB5", "#F1C9EA", "#6D3F8F"],
    ["#E9A36B", "#C76A3A", "#F6D3A8", "#8F3F22"],
  ],
  rocky: [
    ["#9C5B3E", "#74402B", "#BD815F", "#4C2A1E"],
    ["#8A8A86", "#5E5E5B", "#B5B3AC", "#3C3C3A"],
    ["#7B8F5A", "#566B3D", "#A0AF7E", "#394A2A"],
  ],
  ice: [["#CFE9F7", "#9CCBE6", "#F2FAFF", "#6FA8CC"]],
  lava: [["#2A1410", "#1A0B08", "#3D1F18", "#120705"]],
}

function makePlanetTexture(kind: PlanetKind, seed: number) {
  const random = createRandom(seed)
  const palette = pick(random, PLANET_PALETTES[kind])
  const width = 256
  const height = 128
  const { canvas, context } = makeCanvas(width, height)
  context.fillStyle = palette[0]
  context.fillRect(0, 0, width, height)

  if (kind === "gas") {
    let y = 0
    while (y < height) {
      const band = 3 + random() * 14
      context.fillStyle = pick(random, palette)
      context.globalAlpha = 0.65 + random() * 0.35
      context.fillRect(0, y, width, band)
      y += band
    }
    for (let storm = 0; storm < 5; storm += 1) {
      context.fillStyle = pick(random, palette)
      context.globalAlpha = 0.5
      context.beginPath()
      context.ellipse(
        random() * width,
        random() * height,
        6 + random() * 14,
        3 + random() * 6,
        0,
        0,
        Math.PI * 2,
      )
      context.fill()
    }
  } else {
    for (let spot = 0; spot < 220; spot += 1) {
      const x = random() * width
      const y = random() * height
      const radius = 2 + random() * 10
      context.fillStyle = palette[1 + Math.floor(random() * (palette.length - 1))]
      context.globalAlpha = 0.15 + random() * 0.3
      for (const offset of [-width, 0, width]) {
        context.beginPath()
        context.arc(x + offset, y, radius, 0, Math.PI * 2)
        context.fill()
      }
    }
    if (kind === "ice") {
      context.globalAlpha = 0.8
      context.fillStyle = "#FFFFFF"
      context.fillRect(0, 0, width, 6)
      context.fillRect(0, height - 6, width, 6)
    }
    if (kind === "lava") {
      context.globalAlpha = 0.75
      context.lineWidth = 1.2
      for (let crack = 0; crack < 70; crack += 1) {
        context.strokeStyle = random() < 0.5 ? "#FF6A1F" : "#FFB04A"
        let x = random() * width
        let y = random() * height
        context.beginPath()
        context.moveTo(x, y)
        for (let step = 0; step < 6; step += 1) {
          x += (random() - 0.5) * 22
          y += (random() - 0.5) * 12
          context.lineTo(x, y)
        }
        context.stroke()
      }
    }
  }
  context.globalAlpha = 1
  return toTexture(canvas)
}

/** 1D radial banding for planetary rings and accretion-style discs. */
function makeRingTexture(seed: number, tint: RGB) {
  const random = createRandom(seed)
  const bands = Array.from({ length: 64 }, () => 0.15 + random() * 0.85)
  const width = 256
  const { canvas, context } = makeCanvas(width, 2)
  for (let x = 0; x < width; x += 1) {
    const t = x / (width - 1)
    const edge = Math.min(1, t * 8) * Math.min(1, (1 - t) * 6)
    const alpha = bands[Math.floor(t * 63)] * edge * 0.75
    const shade = 0.75 + 0.25 * Math.sin(t * 90)
    context.fillStyle = `rgba(${Math.round(tint[0] * 255 * shade)},${Math.round(
      tint[1] * 255 * shade,
    )},${Math.round(tint[2] * 255 * shade)},${alpha})`
    context.fillRect(x, 0, 1, 2)
  }
  return toTexture(canvas)
}

function makeRingGeometry(inner: number, outer: number) {
  const geometry = new THREE.RingGeometry(inner, outer, 96, 1)
  const position = geometry.attributes.position
  const uv = geometry.attributes.uv
  const vertex = new THREE.Vector3()
  for (let index = 0; index < position.count; index += 1) {
    vertex.fromBufferAttribute(position, index)
    uv.setXY(index, (vertex.length() - inner) / (outer - inner), 0.5)
  }
  return geometry
}

/* -------------------------------------------------------------------------- */
/* GlowPoints: soft, twinkling, additive point sprites (custom shader)        */
/* -------------------------------------------------------------------------- */

const glowVertexShader = /* glsl */ `
  attribute float aSize;
  attribute float aPhase;
  attribute vec3 aColor;
  uniform float uTime;
  uniform float uPixelRatio;
  uniform float uTwinkle;
  uniform float uRef;
  uniform float uDrift;
  varying vec3 vColor;
  void main() {
    vColor = aColor;
    vec3 p = position + uDrift * vec3(
      sin(uTime * 0.35 + aPhase * 37.0),
      cos(uTime * 0.29 + aPhase * 53.0),
      sin(uTime * 0.23 + aPhase * 71.0)
    );
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    float pulse = 1.0 - uTwinkle + uTwinkle * (0.5 + 0.5 * sin(uTime * (0.8 + aPhase * 2.2) + aPhase * 90.0));
    float attenuation = uRef > 0.0 ? clamp(uRef / max(-mv.z, 0.001), 0.35, 2.5) : 1.0;
    gl_PointSize = aSize * pulse * attenuation * uPixelRatio;
  }
`

const glowFragmentShader = /* glsl */ `
  uniform float uOpacity;
  varying vec3 vColor;
  void main() {
    float d = length(gl_PointCoord - 0.5) * 2.0;
    if (d > 1.0) discard;
    float a = pow(1.0 - d, 2.0);
    gl_FragColor = vec4(vColor * a * uOpacity, 1.0);
  }
`

type GlowData = {
  positions: Float32Array
  colors: Float32Array
  sizes: Float32Array
  phases: Float32Array
}

function allocGlow(count: number): GlowData {
  return {
    positions: new Float32Array(count * 3),
    colors: new Float32Array(count * 3),
    sizes: new Float32Array(count),
    phases: new Float32Array(count),
  }
}

function setGlow(
  data: GlowData,
  index: number,
  position: [number, number, number],
  color: RGB,
  brightness: number,
  size: number,
  phase: number,
) {
  data.positions[index * 3] = position[0]
  data.positions[index * 3 + 1] = position[1]
  data.positions[index * 3 + 2] = position[2]
  data.colors[index * 3] = color[0] * brightness
  data.colors[index * 3 + 1] = color[1] * brightness
  data.colors[index * 3 + 2] = color[2] * brightness
  data.sizes[index] = size
  data.phases[index] = phase
}

function createGlowMaterial(
  twinkle: number,
  opacity: number,
  refDistance: number,
  drift: number,
) {
  return new THREE.ShaderMaterial({
    uniforms: {
      uTime: shared.uTime,
      uPixelRatio: shared.uPixelRatio,
      uTwinkle: { value: twinkle },
      uOpacity: { value: opacity },
      uRef: { value: refDistance },
      uDrift: { value: drift },
    },
    vertexShader: glowVertexShader,
    fragmentShader: glowFragmentShader,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  })
}

type GlowPointsProps = {
  data: GlowData
  twinkle?: number
  opacity?: number
  /** Distance at which sizes are exact; 0 = constant pixel size. */
  refDistance?: number
  drift?: number
  materialRef?: MutableRefObject<THREE.ShaderMaterial | null>
}

function GlowPoints({
  data,
  twinkle = 0.4,
  opacity = 1,
  refDistance = 0,
  drift = 0,
  materialRef,
}: GlowPointsProps) {
  const geometry = useMemo(() => {
    const value = new THREE.BufferGeometry()
    value.setAttribute("position", new THREE.BufferAttribute(data.positions, 3))
    value.setAttribute("aColor", new THREE.BufferAttribute(data.colors, 3))
    value.setAttribute("aSize", new THREE.BufferAttribute(data.sizes, 1))
    value.setAttribute("aPhase", new THREE.BufferAttribute(data.phases, 1))
    value.computeBoundingSphere()
    return value
  }, [data])
  const material = useMemo(
    () => createGlowMaterial(twinkle, opacity, refDistance, drift),
    [twinkle, opacity, refDistance, drift],
  )

  useEffect(() => {
    if (materialRef) materialRef.current = material
  }, [material, materialRef])
  useEffect(() => () => geometry.dispose(), [geometry])
  useEffect(() => () => material.dispose(), [material])

  return <points geometry={geometry} material={material} />
}

/* -------------------------------------------------------------------------- */
/* Backdrop: twinkling stars + Milky Way band                                 */
/* -------------------------------------------------------------------------- */

const STAR_COLORS: RGB[] = [
  [0.62, 0.72, 1],
  [0.8, 0.85, 1],
  [1, 1, 1],
  [1, 0.94, 0.78],
  [1, 0.82, 0.54],
  [1, 0.62, 0.48],
]

function Backdrop({
  center,
  radius,
  motion,
}: {
  center: THREE.Vector3
  radius: number
  motion: number
}) {
  const group = useRef<THREE.Group>(null)
  const stars = useMemo(() => {
    const random = createRandom(4242)
    const count = 5000
    const data = allocGlow(count)
    for (let index = 0; index < count; index += 1) {
      const direction = randomDirection(random)
      const distance = radius * (7 + random() * 2)
      setGlow(
        data,
        index,
        [direction.x * distance, direction.y * distance, direction.z * distance],
        pick(random, STAR_COLORS),
        0.55 + random() * 0.45,
        0.9 + Math.pow(random(), 6) * 3.2,
        random(),
      )
    }
    return data
  }, [radius])
  const band = useMemo(() => {
    const random = createRandom(777)
    const count = 6000
    const data = allocGlow(count)
    for (let index = 0; index < count; index += 1) {
      const angle = random() * Math.PI * 2
      const lift = gaussian(random) * 0.1
      const direction = new THREE.Vector3(
        Math.cos(angle),
        lift,
        Math.sin(angle),
      ).normalize()
      const distance = radius * (7.5 + random() * 1.2)
      const warm = 0.5 + 0.5 * Math.sin(angle * 3)
      setGlow(
        data,
        index,
        [direction.x * distance, direction.y * distance, direction.z * distance],
        [0.7 + warm * 0.3, 0.75 + warm * 0.1, 1 - warm * 0.3],
        0.3 + random() * 0.5,
        0.8 + random() * 1.4,
        random(),
      )
    }
    return data
  }, [radius])

  useFrame((_, delta) => {
    if (group.current) group.current.rotation.y += delta * 0.0025 * motion
  })

  return (
    <group position={center} ref={group}>
      <GlowPoints data={stars} twinkle={0.65} />
      <group rotation={[0.9, 0.4, 0.2]}>
        <GlowPoints data={band} opacity={0.55} twinkle={0.3} />
      </group>
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Galaxies                                                                   */
/* -------------------------------------------------------------------------- */

type GalaxySpec = {
  position: THREE.Vector3
  size: number
  seed: number
  tilt: Tilt
  speed: number
  arms: number
  warm: RGB
  cool: RGB
  coreColor: string
  hazeColor: string
}

const GALAXY_LOOKS = [
  {
    warm: [1, 0.82, 0.55] as RGB,
    cool: [0.5, 0.7, 1] as RGB,
    core: "#FFD9A0",
    haze: "#7FA8FF",
  },
  {
    warm: [1, 0.7, 0.8] as RGB,
    cool: [0.7, 0.55, 1] as RGB,
    core: "#FFC1DA",
    haze: "#A98BFF",
  },
  {
    warm: [0.9, 1, 0.8] as RGB,
    cool: [0.4, 0.9, 0.9] as RGB,
    core: "#D8FFE0",
    haze: "#5FE0D0",
  },
  {
    warm: [1, 0.8, 0.5] as RGB,
    cool: [1, 0.5, 0.4] as RGB,
    core: "#FFCF9A",
    haze: "#FF8A6A",
  },
]

function buildGalaxyData(spec: GalaxySpec) {
  const random = createRandom(spec.seed)
  const count = 3200
  const data = allocGlow(count)
  const spin = 3.4
  for (let index = 0; index < count; index += 1) {
    let distance: number
    let angle: number
    let height: number
    if (random() < 0.28) {
      distance = spec.size * 0.22 * Math.pow(random(), 1.7)
      angle = random() * Math.PI * 2
      height = gaussian(random) * spec.size * 0.06
    } else {
      const t = 0.08 + 0.92 * Math.pow(random(), 0.75)
      distance = spec.size * t
      const arm = Math.floor(random() * spec.arms)
      angle =
        (arm / spec.arms) * Math.PI * 2 +
        t * spin +
        gaussian(random) * 0.28 * (1 - t * 0.5)
      height = gaussian(random) * spec.size * 0.025 * (1 - t)
    }
    const t = Math.min(1, distance / spec.size)
    const color: RGB = [
      spec.warm[0] + (spec.cool[0] - spec.warm[0]) * t,
      spec.warm[1] + (spec.cool[1] - spec.warm[1]) * t,
      spec.warm[2] + (spec.cool[2] - spec.warm[2]) * t,
    ]
    const youngStar = random() < 0.08
    setGlow(
      data,
      index,
      [Math.cos(angle) * distance, height, Math.sin(angle) * distance],
      youngStar ? [0.85, 0.92, 1] : color,
      (0.35 + 0.65 * (1 - t)) * (0.6 + random() * 0.4),
      youngStar ? 2.6 + random() : 1.1 + random() * 1.4,
      random(),
    )
  }
  return data
}

function Galaxy({ spec, motion }: { spec: GalaxySpec; motion: number }) {
  const spin = useRef<THREE.Group>(null)
  const data = useMemo(() => buildGalaxyData(spec), [spec])

  useFrame((_, delta) => {
    if (spin.current) spin.current.rotation.y += delta * spec.speed * motion
  })

  return (
    <group position={spec.position}>
      <group rotation={spec.tilt}>
        <group ref={spin}>
          <GlowPoints data={data} opacity={0.9} twinkle={0.25} />
        </group>
      </group>
      <sprite scale={[spec.size * 0.7, spec.size * 0.7, 1]}>
        <spriteMaterial
          blending={THREE.AdditiveBlending}
          color={spec.coreColor}
          depthWrite={false}
          fog={false}
          map={getGlowTexture()}
          opacity={0.5}
          transparent
        />
      </sprite>
      <sprite scale={[spec.size * 1.6, spec.size * 1.6, 1]}>
        <spriteMaterial
          blending={THREE.AdditiveBlending}
          color={spec.hazeColor}
          depthWrite={false}
          fog={false}
          map={getGlowTexture()}
          opacity={0.1}
          transparent
        />
      </sprite>
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Nebulae                                                                    */
/* -------------------------------------------------------------------------- */

type NebulaSpec = {
  position: THREE.Vector3
  size: number
  seed: number
  colors: string[]
  opacity: number
}

const NEBULA_PALETTES = [
  ["#7B4DFF", "#FF4DA6", "#3D6BFF"],
  ["#FF7A3D", "#FFB14D", "#C23D5A"],
  ["#2FD6C0", "#2F8DFF", "#7A5CFF"],
  ["#FF4D8D", "#B04DFF", "#4D6BFF"],
]

function Nebula({ spec, motion }: { spec: NebulaSpec; motion: number }) {
  const group = useRef<THREE.Group>(null)
  const time = useRef(0)
  const puffs = useMemo(() => {
    const random = createRandom(spec.seed)
    return Array.from({ length: 6 }, () => ({
      offset: [
        gaussian(random) * spec.size * 0.22,
        gaussian(random) * spec.size * 0.14,
        gaussian(random) * spec.size * 0.22,
      ] as [number, number, number],
      scale: spec.size * (0.5 + random() * 0.55),
      color: pick(random, spec.colors),
      texture: Math.floor(random() * 3),
      rotation: random() * Math.PI * 2,
      spin: (random() - 0.5) * 0.06,
      opacity: spec.opacity * (0.6 + random() * 0.6),
      rate: 0.15 + random() * 0.25,
      phase: random() * Math.PI * 2,
    }))
  }, [spec])

  useFrame((_, delta) => {
    time.current += delta * motion
    group.current?.children.forEach((child, index) => {
      const puff = puffs[index]
      const material = (child as THREE.Sprite).material
      material.rotation += delta * puff.spin * motion
      material.opacity =
        puff.opacity * (0.75 + 0.25 * Math.sin(time.current * puff.rate + puff.phase))
    })
  })

  return (
    <group position={spec.position} ref={group}>
      {puffs.map((puff, index) => (
        <sprite
          key={index}
          position={puff.offset}
          scale={[puff.scale, puff.scale, 1]}
        >
          <spriteMaterial
            blending={THREE.AdditiveBlending}
            color={puff.color}
            depthWrite={false}
            fog={false}
            map={getCloudTexture(puff.texture)}
            opacity={puff.opacity}
            rotation={puff.rotation}
            transparent
          />
        </sprite>
      ))}
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Bright stars (pulsing glow + rotating diffraction spikes)                  */
/* -------------------------------------------------------------------------- */

type BrightStarSpec = {
  position: THREE.Vector3
  size: number
  color: string
  phase: number
  rate: number
}

function BrightStar({
  spec,
  motion,
}: {
  spec: BrightStarSpec
  motion: number
}) {
  const glow = useRef<THREE.Sprite>(null)
  const spikes = useRef<THREE.Sprite>(null)
  const time = useRef(spec.phase)

  useFrame((_, delta) => {
    time.current += delta * motion
    const pulse = 0.85 + 0.15 * Math.sin(time.current * spec.rate)
    if (glow.current) {
      glow.current.scale.setScalar(spec.size * pulse)
    }
    if (spikes.current) {
      spikes.current.scale.setScalar(spec.size * 2.4 * pulse)
      spikes.current.material.rotation += delta * 0.03 * motion
    }
  })

  return (
    <group position={spec.position}>
      <sprite ref={glow} scale={[spec.size, spec.size, 1]}>
        <spriteMaterial
          blending={THREE.AdditiveBlending}
          color={spec.color}
          depthWrite={false}
          fog={false}
          map={getGlowTexture()}
          transparent
        />
      </sprite>
      <sprite ref={spikes} scale={[spec.size * 2.4, spec.size * 2.4, 1]}>
        <spriteMaterial
          blending={THREE.AdditiveBlending}
          color={spec.color}
          depthWrite={false}
          fog={false}
          map={getSpikeTexture()}
          opacity={0.55}
          transparent
        />
      </sprite>
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Background planets (rotating, with rings and orbiting moons)               */
/* -------------------------------------------------------------------------- */

type MoonSpec = {
  distance: number
  radius: number
  speed: number
  phase: number
  color: string
}

type PlanetSpec = {
  position: THREE.Vector3
  radius: number
  kind: PlanetKind
  seed: number
  ring: boolean
  ringTint: RGB
  moons: MoonSpec[]
  spin: number
  tilt: number
  atmosphere: string | null
}

function BackgroundPlanet({
  planet,
  motion,
}: {
  planet: PlanetSpec
  motion: number
}) {
  const body = useRef<THREE.Mesh>(null)
  const moons = useRef<THREE.Group>(null)
  const texture = useMemo(
    () => makePlanetTexture(planet.kind, planet.seed),
    [planet],
  )
  const ringTexture = useMemo(
    () =>
      planet.ring ? makeRingTexture(planet.seed + 5, planet.ringTint) : null,
    [planet],
  )
  const ringGeometry = useMemo(
    () =>
      planet.ring
        ? makeRingGeometry(planet.radius * 1.45, planet.radius * 2.3)
        : null,
    [planet],
  )

  useEffect(
    () => () => {
      texture.dispose()
      ringTexture?.dispose()
      ringGeometry?.dispose()
    },
    [texture, ringTexture, ringGeometry],
  )

  useFrame((_, delta) => {
    if (body.current) body.current.rotation.y += delta * planet.spin * motion
    moons.current?.children.forEach((moon, index) => {
      moon.rotation.y += delta * planet.moons[index].speed * motion
    })
  })

  return (
    <group position={planet.position} rotation={[0, 0, planet.tilt]}>
      <mesh ref={body}>
        <sphereGeometry args={[planet.radius, 48, 48]} />
        <meshStandardMaterial
          emissive="#FFFFFF"
          emissiveIntensity={planet.kind === "lava" ? 0.9 : 0.14}
          emissiveMap={texture}
          map={texture}
          metalness={0.02}
          roughness={0.88}
        />
      </mesh>
      {planet.atmosphere ? (
        <mesh>
          <sphereGeometry args={[planet.radius * 1.07, 32, 32]} />
          <meshBasicMaterial
            blending={THREE.AdditiveBlending}
            color={planet.atmosphere}
            depthWrite={false}
            fog={false}
            opacity={0.18}
            side={THREE.BackSide}
            transparent
          />
        </mesh>
      ) : null}
      {ringGeometry && ringTexture ? (
        <mesh geometry={ringGeometry} rotation={[-Math.PI / 2, 0, 0]}>
          <meshStandardMaterial
            depthWrite={false}
            map={ringTexture}
            roughness={1}
            side={THREE.DoubleSide}
            transparent
          />
        </mesh>
      ) : null}
      <group ref={moons}>
        {planet.moons.map((moon, index) => (
          <group key={index} rotation={[0, moon.phase, 0]}>
            <mesh position={[moon.distance, 0, 0]}>
              <icosahedronGeometry args={[moon.radius, 1]} />
              <meshStandardMaterial
                color={moon.color}
                flatShading
                roughness={1}
              />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Asteroid belts (instanced, tumbling, orbiting)                             */
/* -------------------------------------------------------------------------- */

type BeltSpec = {
  position: THREE.Vector3
  inner: number
  outer: number
  thickness: number
  count: number
  rockSize: number
  tilt: Tilt
  seed: number
}

function AsteroidBelt({
  belt,
  motion,
}: {
  belt: BeltSpec
  motion: number
}) {
  const mesh = useRef<THREE.InstancedMesh>(null)
  const time = useRef(0)
  const dummy = useMemo(() => new THREE.Object3D(), [])
  const rocks = useMemo(() => {
    const random = createRandom(belt.seed)
    return Array.from({ length: belt.count }, () => {
      const distance =
        belt.inner + (belt.outer - belt.inner) * Math.pow(random(), 0.8)
      return {
        angle: random() * Math.PI * 2,
        distance,
        height: gaussian(random) * belt.thickness * 0.35,
        scale: 0.3 + Math.pow(random(), 3) * 1.4,
        spin: [random() - 0.5, random() - 0.5, random() - 0.5].map(
          (value) => value * 0.8,
        ),
        phase: [random() * 6.28, random() * 6.28, random() * 6.28],
        orbit: 0.07 / Math.sqrt(distance / belt.inner),
        hue: 0.05 + random() * 0.06,
        lightness: 0.2 + random() * 0.28,
      }
    })
  }, [belt])

  useEffect(() => {
    const instanced = mesh.current
    if (!instanced) return
    const color = new THREE.Color()
    rocks.forEach((rock, index) => {
      color.setHSL(rock.hue, 0.18, rock.lightness)
      instanced.setColorAt(index, color)
    })
    if (instanced.instanceColor) instanced.instanceColor.needsUpdate = true
  }, [rocks])

  useFrame((_, delta) => {
    const instanced = mesh.current
    if (!instanced) return
    time.current += delta * motion
    const t = time.current
    rocks.forEach((rock, index) => {
      const angle = rock.angle + t * rock.orbit
      dummy.position.set(
        Math.cos(angle) * rock.distance,
        rock.height,
        Math.sin(angle) * rock.distance,
      )
      dummy.rotation.set(
        rock.phase[0] + t * rock.spin[0],
        rock.phase[1] + t * rock.spin[1],
        rock.phase[2] + t * rock.spin[2],
      )
      dummy.scale.setScalar(rock.scale)
      dummy.updateMatrix()
      instanced.setMatrixAt(index, dummy.matrix)
    })
    instanced.instanceMatrix.needsUpdate = true
  })

  return (
    <group position={belt.position} rotation={belt.tilt}>
      <instancedMesh
        args={[undefined, undefined, belt.count]}
        frustumCulled={false}
        ref={mesh}
      >
        <icosahedronGeometry args={[belt.rockSize, 0]} />
        <meshStandardMaterial flatShading roughness={1} />
      </instancedMesh>
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Black hole (dark core, photon ring, orbiting differential disc)            */
/* -------------------------------------------------------------------------- */

type BlackHoleSpec = {
  position: THREE.Vector3
  size: number
  tilt: Tilt
}

function buildDiskData(
  random: Random,
  count: number,
  inner: number,
  outer: number,
  thickness: number,
  hot: RGB,
  cool: RGB,
) {
  const data = allocGlow(count)
  for (let index = 0; index < count; index += 1) {
    const t = random()
    const distance = inner + (outer - inner) * t
    const angle = random() * Math.PI * 2
    setGlow(
      data,
      index,
      [
        Math.cos(angle) * distance,
        gaussian(random) * thickness,
        Math.sin(angle) * distance,
      ],
      [
        hot[0] + (cool[0] - hot[0]) * t,
        hot[1] + (cool[1] - hot[1]) * t,
        hot[2] + (cool[2] - hot[2]) * t,
      ],
      0.6 + random() * 0.4,
      1.4 + random() * 2,
      random(),
    )
  }
  return data
}

function BlackHole({
  spec,
  motion,
}: {
  spec: BlackHoleSpec
  motion: number
}) {
  const layers = useRef<(THREE.Group | null)[]>([])
  const disks = useMemo(() => {
    const random = createRandom(31337)
    const s = spec.size
    return [
      {
        speed: 0.7,
        data: buildDiskData(random, 800, 1.6 * s, 2.3 * s, 0.04 * s, [1, 0.95, 0.8], [1, 0.7, 0.35]),
      },
      {
        speed: 0.42,
        data: buildDiskData(random, 900, 2.3 * s, 3.2 * s, 0.06 * s, [1, 0.7, 0.35], [0.95, 0.4, 0.2]),
      },
      {
        speed: 0.25,
        data: buildDiskData(random, 900, 3.2 * s, 4.4 * s, 0.09 * s, [0.95, 0.4, 0.2], [0.6, 0.2, 0.25]),
      },
    ]
  }, [spec.size])

  useFrame((_, delta) => {
    layers.current.forEach((layer, index) => {
      if (layer) layer.rotation.y += delta * disks[index].speed * motion
    })
  })

  const s = spec.size
  return (
    <group position={spec.position}>
      <mesh>
        <sphereGeometry args={[s, 48, 48]} />
        <meshBasicMaterial color="#000000" fog={false} />
      </mesh>
      <sprite scale={[s * 4.68, s * 4.68, 1]}>
        <spriteMaterial
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          fog={false}
          map={getRingGlowTexture()}
          transparent
        />
      </sprite>
      <sprite scale={[s * 10, s * 10, 1]}>
        <spriteMaterial
          blending={THREE.AdditiveBlending}
          color="#FF8A3D"
          depthWrite={false}
          fog={false}
          map={getGlowTexture()}
          opacity={0.28}
          transparent
        />
      </sprite>
      <group rotation={spec.tilt}>
        {disks.map((disk, index) => (
          <group
            key={index}
            ref={(node) => {
              layers.current[index] = node
            }}
          >
            <GlowPoints data={disk.data} twinkle={0.2} />
          </group>
        ))}
      </group>
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Binary stars                                                               */
/* -------------------------------------------------------------------------- */

type BinarySpec = {
  position: THREE.Vector3
  separation: number
  speed: number
  tilt: number
  colors: [string, string]
  radii: [number, number]
}

function Star({ color, radius }: { color: string; radius: number }) {
  return (
    <group>
      <mesh>
        <sphereGeometry args={[radius, 24, 24]} />
        <meshBasicMaterial color={color} fog={false} />
      </mesh>
      <sprite scale={[radius * 7, radius * 7, 1]}>
        <spriteMaterial
          blending={THREE.AdditiveBlending}
          color={color}
          depthWrite={false}
          fog={false}
          map={getGlowTexture()}
          opacity={0.85}
          transparent
        />
      </sprite>
    </group>
  )
}

function BinaryStar({
  spec,
  motion,
}: {
  spec: BinarySpec
  motion: number
}) {
  const orbit = useRef<THREE.Group>(null)

  useFrame((_, delta) => {
    if (orbit.current) orbit.current.rotation.y += delta * spec.speed * motion
  })

  return (
    <group position={spec.position} rotation={[spec.tilt, 0, 0]}>
      <group ref={orbit}>
        <group position={[spec.separation * 0.35, 0, 0]}>
          <Star color={spec.colors[0]} radius={spec.radii[0]} />
        </group>
        <group position={[-spec.separation * 0.65, 0, 0]}>
          <Star color={spec.colors[1]} radius={spec.radii[1]} />
        </group>
      </group>
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Small star systems (star + orbiting planets)                               */
/* -------------------------------------------------------------------------- */

type SystemPlanet = {
  orbit: number
  radius: number
  speed: number
  phase: number
  color: string
}

type SystemSpec = {
  position: THREE.Vector3
  starRadius: number
  starColor: string
  tilt: Tilt
  planets: SystemPlanet[]
}

function StarSystem({
  spec,
  motion,
}: {
  spec: SystemSpec
  motion: number
}) {
  const planets = useRef<THREE.Group>(null)

  useFrame((_, delta) => {
    planets.current?.children.forEach((child, index) => {
      child.rotation.y += delta * spec.planets[index].speed * motion
    })
  })

  return (
    <group position={spec.position} rotation={spec.tilt}>
      <Star color={spec.starColor} radius={spec.starRadius} />
      {spec.planets.map((planet, index) => (
        <mesh key={index} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[planet.orbit - 0.05, planet.orbit + 0.05, 96]} />
          <meshBasicMaterial
            color="#9FD8FF"
            depthWrite={false}
            fog={false}
            opacity={0.16}
            side={THREE.DoubleSide}
            transparent
          />
        </mesh>
      ))}
      <group ref={planets}>
        {spec.planets.map((planet, index) => (
          <group key={index} rotation={[0, planet.phase, 0]}>
            <mesh position={[planet.orbit, 0, 0]}>
              <sphereGeometry args={[planet.radius, 24, 24]} />
              <meshStandardMaterial
                color={planet.color}
                emissive={planet.color}
                emissiveIntensity={0.15}
                roughness={0.85}
              />
            </mesh>
          </group>
        ))}
      </group>
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Free-flying comets                                                         */
/* -------------------------------------------------------------------------- */

type CometSpec = {
  start: THREE.Vector3
  end: THREE.Vector3
  period: number
  length: number
  size: number
  phase: number
  seed: number
  ion: RGB
  dust: RGB
}

function buildCometData(spec: CometSpec) {
  const random = createRandom(spec.seed)
  const ionCount = 70
  const dustCount = 60
  const data = allocGlow(2 + ionCount + dustCount)
  setGlow(data, 0, [0, 0, 0], [1, 1, 1], 1, 18 * spec.size, 0.1)
  setGlow(data, 1, [0, 0, 0], spec.ion, 0.5, 34 * spec.size, 0.6)
  for (let index = 0; index < ionCount; index += 1) {
    const t = index / (ionCount - 1)
    const spread = t * spec.length * 0.012
    setGlow(
      data,
      2 + index,
      [
        gaussian(random) * spread,
        gaussian(random) * spread,
        -t * spec.length,
      ],
      spec.ion,
      Math.pow(1 - t, 1.4) * 0.9,
      (1 - t) * 7 * spec.size + 1.5,
      random(),
    )
  }
  for (let index = 0; index < dustCount; index += 1) {
    const t = index / (dustCount - 1)
    const spread = t * spec.length * 0.02
    setGlow(
      data,
      2 + ionCount + index,
      [
        t * t * spec.length * 0.16 + gaussian(random) * spread,
        gaussian(random) * spread,
        -t * spec.length * 0.7,
      ],
      spec.dust,
      Math.pow(1 - t, 1.3) * 0.75,
      (1 - t) * 8 * spec.size + 1.5,
      random(),
    )
  }
  return data
}

function FreeComet({
  spec,
  motion,
}: {
  spec: CometSpec
  motion: number
}) {
  const group = useRef<THREE.Group>(null)
  const materialRef = useRef<THREE.ShaderMaterial | null>(null)
  const progress = useRef(spec.phase)
  const data = useMemo(() => buildCometData(spec), [spec])
  const quaternion = useMemo(
    () =>
      new THREE.Quaternion().setFromUnitVectors(
        new THREE.Vector3(0, 0, 1),
        spec.end.clone().sub(spec.start).normalize(),
      ),
    [spec],
  )

  useFrame((_, delta) => {
    const comet = group.current
    if (!comet) return
    progress.current = (progress.current + (delta * motion) / spec.period) % 1
    const phase = progress.current
    comet.position.lerpVectors(spec.start, spec.end, phase)
    const fade =
      THREE.MathUtils.smoothstep(phase, 0, 0.1) *
      (1 - THREE.MathUtils.smoothstep(phase, 0.9, 1))
    if (materialRef.current) materialRef.current.uniforms.uOpacity.value = fade
    comet.visible = fade > 0.01
  })

  return (
    <group quaternion={quaternion} ref={group} visible={false}>
      <GlowPoints
        data={data}
        materialRef={materialRef}
        refDistance={90}
        twinkle={0.2}
      />
    </group>
  )
}

/* -------------------------------------------------------------------------- */
/* Drifting dust along the route (gives parallax and a sense of speed)        */
/* -------------------------------------------------------------------------- */

function DustField({ anchors }: { anchors: THREE.Vector3[] }) {
  const data = useMemo(() => {
    const random = createRandom(9001)
    const count = 3200
    const result = allocGlow(count)
    const palette: RGB[] = [
      [0.7, 0.9, 1],
      [1, 1, 1],
      [1, 0.85, 0.6],
    ]
    for (let index = 0; index < count; index += 1) {
      const anchor = anchors[Math.floor(random() * anchors.length)]
      setGlow(
        result,
        index,
        [
          anchor.x + gaussian(random) * 18,
          anchor.y + gaussian(random) * 14,
          anchor.z + gaussian(random) * 18,
        ],
        pick(random, palette),
        0.35 + random() * 0.5,
        1.2 + Math.pow(random(), 4) * 2.5,
        random(),
      )
    }
    return result
  }, [anchors])

  return <GlowPoints data={data} drift={1.2} refDistance={45} twinkle={0.5} />
}

/* -------------------------------------------------------------------------- */
/* Layout: where everything goes                                              */
/* -------------------------------------------------------------------------- */

function buildLayout(
  center: THREE.Vector3,
  radius: number,
  anchors: THREE.Vector3[],
) {
  const random = createRandom(20261011)
  const place = createPlacer(random, center, anchors)

  const galaxies: GalaxySpec[] = []
  for (let index = 0; index < 7; index += 1) {
    const size = radius * (0.7 + random() * 0.6)
    const position = place(radius * 5.5, radius * 7, size, 0)
    if (!position) continue
    const look = GALAXY_LOOKS[index % GALAXY_LOOKS.length]
    galaxies.push({
      position,
      size,
      seed: 500 + index * 31,
      tilt: [
        (random() - 0.5) * 2.2,
        random() * Math.PI,
        (random() - 0.5) * 1.6,
      ],
      speed: (0.02 + random() * 0.03) * (random() < 0.5 ? -1 : 1),
      arms: 2 + Math.floor(random() * 3),
      warm: look.warm,
      cool: look.cool,
      coreColor: look.core,
      hazeColor: look.haze,
    })
  }

  const nebulae: NebulaSpec[] = []
  for (let index = 0; index < 6; index += 1) {
    const size = radius * (1 + random() * 0.8)
    const position = place(radius * 5, radius * 7, size * 0.9, 0)
    if (!position) continue
    nebulae.push({
      position,
      size,
      seed: 900 + index * 17,
      colors: NEBULA_PALETTES[index % NEBULA_PALETTES.length],
      opacity: 0.14,
    })
  }
  for (let index = 0; index < 6; index += 1) {
    const size = radius * (0.3 + random() * 0.25)
    const position = place(radius * 0.25, radius * 1.3, size * 0.5, 12 + size * 0.3)
    if (!position) continue
    nebulae.push({
      position,
      size,
      seed: 1300 + index * 19,
      colors: NEBULA_PALETTES[(index + 2) % NEBULA_PALETTES.length],
      opacity: 0.1,
    })
  }

  const brightStars: BrightStarSpec[] = []
  for (let index = 0; index < 16; index += 1) {
    const position = place(radius * 4, radius * 7, 1, 0)
    if (!position) continue
    brightStars.push({
      position,
      size: radius * (0.05 + random() * 0.06),
      color: pick(random, ["#CFE0FF", "#FFFFFF", "#FFE9B8", "#FFC9A0", "#FFB3B3"]),
      phase: random() * 10,
      rate: 0.4 + random() * 0.9,
    })
  }

  const planets: PlanetSpec[] = []
  const kinds: PlanetKind[] = ["gas", "gas", "rocky", "ice", "lava", "rocky", "gas", "ice"]
  for (let index = 0; index < 14; index += 1) {
    const kind = pick(random, kinds)
    const planetRadius = kind === "gas" ? 3.5 + random() * 4.5 : 1.6 + random() * 2.6
    const ring = (kind === "gas" && random() < 0.55) || (kind === "ice" && random() < 0.25)
    const position = place(
      radius * 0.12,
      radius * 1.7,
      planetRadius * (ring ? 3 : 2) + 6,
      18,
    )
    if (!position) continue
    const palette = pick(random, PLANET_PALETTES[kind])
    const ringColor = new THREE.Color(palette[2])
    const moonCount = kind === "gas" ? 1 + Math.floor(random() * 3) : Math.floor(random() * 2)
    planets.push({
      position,
      radius: planetRadius,
      kind,
      seed: 3000 + index * 13,
      ring,
      ringTint: [ringColor.r, ringColor.g, ringColor.b],
      moons: Array.from({ length: moonCount }, (_, moonIndex) => ({
        distance: planetRadius * (ring ? 2.8 : 1.9) + moonIndex * planetRadius * 0.7,
        radius: planetRadius * (0.1 + random() * 0.12),
        speed: (0.25 + random() * 0.35) / (moonIndex + 1),
        phase: random() * Math.PI * 2,
        color: pick(random, ["#9A948B", "#B5ADA0", "#7C7770", "#A89886"]),
      })),
      spin: 0.03 + random() * 0.09,
      tilt: (random() - 0.5) * 0.6,
      atmosphere:
        kind === "gas"
          ? palette[1]
          : kind === "ice"
            ? "#9CCBE6"
            : kind === "lava"
              ? "#FF6A1F"
              : null,
    })
  }

  const belts: BeltSpec[] = []
  for (let index = 0; index < 3; index += 1) {
    const inner = 14 + random() * 8
    const outer = inner + 8 + random() * 10
    const position = place(radius * 0.3, radius * 1.5, outer + 4, 14)
    if (!position) continue
    belts.push({
      position,
      inner,
      outer,
      thickness: 2.5 + random() * 3,
      count: 650,
      rockSize: 0.35 + random() * 0.25,
      tilt: [(random() - 0.5) * 0.9, 0, (random() - 0.5) * 0.9],
      seed: 6000 + index * 11,
    })
  }

  const blackHolePosition = place(radius * 0.5, radius * 1.5, 26, 40)
  const blackHole: BlackHoleSpec | null = blackHolePosition
    ? { position: blackHolePosition, size: 5, tilt: [1.15, 0.3, 0.2] }
    : null

  const binaries: BinarySpec[] = []
  for (let index = 0; index < 4; index += 1) {
    const position = place(radius * 0.3, radius * 1.6, 14, 25)
    if (!position) continue
    binaries.push({
      position,
      separation: 4 + random() * 3,
      speed: 0.25 + random() * 0.3,
      tilt: (random() - 0.5) * 1.2,
      colors: pick<[string, string]>(random, [
        ["#FFB45E", "#7FB4FF"],
        ["#FF8A6A", "#FFE9B8"],
        ["#9FD0FF", "#FFD27A"],
      ]),
      radii: [1.3 + random() * 0.5, 0.8 + random() * 0.4],
    })
  }

  const systems: SystemSpec[] = []
  for (let index = 0; index < 4; index += 1) {
    const position = place(radius * 0.3, radius * 1.6, 24, 20)
    if (!position) continue
    const planetCount = 2 + Math.floor(random() * 2)
    systems.push({
      position,
      starRadius: 1.6 + random() * 1,
      starColor: pick(random, ["#FFE9B8", "#FFC27A", "#FF9A7A", "#CFE0FF"]),
      tilt: [(random() - 0.5) * 0.6, 0, (random() - 0.5) * 0.6],
      planets: Array.from({ length: planetCount }, (_, planetIndex) => ({
        orbit: 6 + planetIndex * 5 + random() * 2,
        radius: 0.5 + random() * 0.9,
        speed: 0.5 / (planetIndex + 1) + random() * 0.15,
        phase: random() * Math.PI * 2,
        color: pick(random, ["#6FA8CC", "#C98B52", "#8FB58A", "#B5707A"]),
      })),
    })
  }

  const comets: CometSpec[] = []
  for (let index = 0; index < 10; index += 1) {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      const startDirection = randomDirection(random)
      const endDirection = randomDirection(random)
      if (startDirection.dot(endDirection) > -0.2) continue
      const start = startDirection.multiplyScalar(radius * (1.5 + random() * 0.5)).add(center)
      const end = endDirection.multiplyScalar(radius * (1.5 + random() * 0.5)).add(center)
      if (segmentClearance(start, end, anchors) < 14) continue
      const speed = 6 + random() * 8
      comets.push({
        start,
        end,
        period: start.distanceTo(end) / speed,
        length: radius * (0.32 + random() * 0.25),
        size: 0.8 + random() * 0.8,
        phase: random(),
        seed: 8000 + index * 7,
        ion: [0.45, 0.8, 1],
        dust: pick<RGB>(random, [
          [1, 0.85, 0.55],
          [1, 0.7, 0.5],
          [0.9, 0.9, 1],
        ]),
      })
      break
    }
  }

  return {
    galaxies,
    nebulae,
    brightStars,
    planets,
    belts,
    blackHole,
    binaries,
    systems,
    comets,
  }
}

/* -------------------------------------------------------------------------- */
/* Entry point                                                                */
/* -------------------------------------------------------------------------- */

export default function SpaceScenery({
  anchors,
  center,
  radius,
  reducedMotion,
}: SpaceSceneryProps) {
  const dpr = useThree((state) => state.viewport.dpr)
  const motion = reducedMotion ? 0.25 : 1
  const layout = useMemo(
    () => buildLayout(center, radius, anchors),
    [center, radius, anchors],
  )

  useEffect(() => {
    shared.uPixelRatio.value = dpr
  }, [dpr])

  useFrame((_, delta) => {
    shared.uTime.value += delta * motion
  })

  return (
    <group>
      <Backdrop center={center} motion={motion} radius={radius} />
      {layout.galaxies.map((spec, index) => (
        <Galaxy key={`galaxy-${index}`} motion={motion} spec={spec} />
      ))}
      {layout.nebulae.map((spec, index) => (
        <Nebula key={`nebula-${index}`} motion={motion} spec={spec} />
      ))}
      {layout.brightStars.map((spec, index) => (
        <BrightStar key={`bright-${index}`} motion={motion} spec={spec} />
      ))}
      {layout.planets.map((planet, index) => (
        <BackgroundPlanet key={`planet-${index}`} motion={motion} planet={planet} />
      ))}
      {layout.belts.map((belt, index) => (
        <AsteroidBelt key={`belt-${index}`} belt={belt} motion={motion} />
      ))}
      {layout.blackHole ? (
        <BlackHole motion={motion} spec={layout.blackHole} />
      ) : null}
      {layout.binaries.map((spec, index) => (
        <BinaryStar key={`binary-${index}`} motion={motion} spec={spec} />
      ))}
      {layout.systems.map((spec, index) => (
        <StarSystem key={`system-${index}`} motion={motion} spec={spec} />
      ))}
      {layout.comets.map((spec, index) => (
        <FreeComet key={`comet-${index}`} motion={motion} spec={spec} />
      ))}
      <DustField anchors={anchors} />
    </group>
  )
}
