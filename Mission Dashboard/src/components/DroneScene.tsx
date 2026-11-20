import { ContactShadows, useGLTF } from "@react-three/drei"
import { Canvas, useFrame } from "@react-three/fiber"
import { Suspense, useEffect, useMemo, useRef } from "react"
import * as THREE from "three"
import type { SpeedLevel } from "../types"

type ModelProps = {
  roll: number
  pitch: number
  yaw: number
  speed: SpeedLevel
  paused: boolean
}

// The GLB merges all four propellers into one mesh ("Object_2"). Split it by
// quadrant into separate geometries, each re-centred on its hub, so every
// blade can spin around its own axis.
function extractPropellers(model: THREE.Object3D) {
  const source = model.getObjectByName("Object_2")
  if (!(source instanceof THREE.Mesh) || !source.parent) return []
  const geometry = source.geometry.index
    ? source.geometry.toNonIndexed()
    : source.geometry
  const position = geometry.getAttribute("position")
  const buckets: number[][] = [[], [], [], []]

  for (let tri = 0; tri < position.count; tri += 3) {
    let cx = 0
    let cy = 0
    for (let k = 0; k < 3; k++) {
      cx += position.getX(tri + k)
      cy += position.getY(tri + k)
    }
    const bucket = (cx > 0 ? 1 : 0) + (cy / 3 > 0.2 ? 2 : 0)
    for (let k = 0; k < 3; k++) buckets[bucket].push(tri + k)
  }

  const pivots = buckets
    .filter((indices) => indices.length)
    .map((indices, index) => {
      const part = new THREE.BufferGeometry()
      for (const [name, attribute] of Object.entries(geometry.attributes)) {
        const attr = attribute as THREE.BufferAttribute
        const array = new Float32Array(indices.length * attr.itemSize)
        indices.forEach((vertex, i) => {
          for (let c = 0; c < attr.itemSize; c++) {
            array[i * attr.itemSize + c] = attr.getComponent(vertex, c)
          }
        })
        part.setAttribute(name, new THREE.BufferAttribute(array, attr.itemSize))
      }
      part.computeBoundingBox()
      const hub = part.boundingBox!.getCenter(new THREE.Vector3())
      part.translate(-hub.x, -hub.y, 0)
      const pivot = new THREE.Group()
      pivot.position.set(hub.x, hub.y, 0)
      pivot.userData.direction = index % 3 === 0 ? 1 : -1
      pivot.add(new THREE.Mesh(part, source.material))
      source.parent!.add(pivot)
      return pivot
    })

  source.parent.remove(source)
  return pivots
}

function DroneModel({ roll, pitch, yaw, speed, paused }: ModelProps) {
  const { scene } = useGLTF("/models/drone.glb")
  const group = useRef<THREE.Group>(null)
  const spin = useRef(0)
  const model = useMemo(() => scene.clone(true), [scene])
  const propellers = useMemo(() => extractPropellers(model), [model])

  const normalized = useMemo(() => {
    // The GLB root node already converts the Sketchfab Z-up mesh to Y-up, so
    // the model sits level as-is; no extra rotation is needed.
    model.updateMatrixWorld(true)
    const box = new THREE.Box3().setFromObject(model)
    const size = box.getSize(new THREE.Vector3())
    const center = box.getCenter(new THREE.Vector3())
    const scale = 4.3 / Math.max(size.x, size.y, size.z)
    model.scale.setScalar(scale)
    model.position.copy(center).multiplyScalar(-scale)
    return { model, scale }
  }, [model])

  useEffect(() => {
    model.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.castShadow = true
        child.receiveShadow = true
        const wasArray = Array.isArray(child.material)
        const materials = wasArray ? child.material : [child.material]
        const tintedMaterials = materials.map((source) => {
          const material = source.clone() as THREE.MeshStandardMaterial
          const name = material.name.toLowerCase()
          if (name.includes("chrome")) {
            material.color.set("#7F8FD4")
            material.metalness = 0.88
            material.roughness = 0.2
          } else if (name.includes("glass")) {
            material.color.set("#B8A7E8")
            material.transparent = true
            material.opacity = 0.58
            material.metalness = 0.1
            material.roughness = 0.12
          } else if (name.includes("grey")) {
            material.color.set("#F1F0F5")
            material.metalness = 0.45
            material.roughness = 0.32
          } else {
            material.color.set("#5D3BC3")
            material.metalness = 0.6
            material.roughness = 0.28
          }
          material.needsUpdate = true
          return material
        })
        child.material = wasArray ? tintedMaterials : tintedMaterials[0]
      }
    })
  }, [model])

  useFrame((_, delta) => {
    if (!group.current) return
    // Apply heading, then pitch, then roll (aerospace order). Heading 128° is
    // the camera's reference so the default view stays at a three-quarter angle.
    group.current.rotation.order = "YXZ"
    const targetX = THREE.MathUtils.degToRad(pitch)
    const targetY = -THREE.MathUtils.degToRad(yaw - 128) - 0.34
    const targetZ = THREE.MathUtils.degToRad(-roll)
    group.current.rotation.x = THREE.MathUtils.damp(
      group.current.rotation.x,
      targetX,
      4,
      delta,
    )
    group.current.rotation.y = THREE.MathUtils.damp(
      group.current.rotation.y,
      targetY,
      3,
      delta,
    )
    group.current.rotation.z = THREE.MathUtils.damp(
      group.current.rotation.z,
      targetZ,
      4,
      delta,
    )
    // Spin up while flying, spool down smoothly when paused or stopped.
    const targetSpin = paused
      ? 0
      : speed === "high"
        ? 34
        : speed === "medium"
          ? 26
          : 18
    spin.current = THREE.MathUtils.damp(spin.current, targetSpin, 1.6, delta)
    propellers.forEach((pivot) => {
      pivot.rotation.z += delta * spin.current * pivot.userData.direction
    })
  })

  return (
    <group ref={group} position={[0, 0.1, 0]}>
      <primitive object={normalized.model} />
    </group>
  )
}

function Loader() {
  return (
    <mesh>
      <torusGeometry args={[0.8, 0.025, 12, 80]} />
      <meshBasicMaterial color="#B8A7E8" transparent opacity={0.7} />
    </mesh>
  )
}

export default function DroneScene(props: ModelProps) {
  return (
    <Canvas
      camera={{ fov: 32, position: [7.2, 4.5, 8.5] }}
      dpr={[1, 1.6]}
      gl={{ alpha: true, antialias: true }}
      shadows="percentage"
    >
      <ambientLight intensity={0.9} />
      <directionalLight
        castShadow
        color="#F1F0F5"
        intensity={3.2}
        position={[4, 8, 6]}
      />
      <pointLight color="#B8A7E8" intensity={18} position={[-4, 2, 3]} />
      <pointLight color="#5D3BC3" intensity={12} position={[4, 1, -4]} />
      <Suspense fallback={<Loader />}>
        <DroneModel {...props} />
      </Suspense>
      <ContactShadows
        color="#5D3BC3"
        far={8}
        opacity={0.25}
        position={[0, -1.45, 0]}
        scale={8}
      />
    </Canvas>
  )
}

useGLTF.preload("/models/drone.glb")
