'use client'

import { useMemo, useRef } from 'react'
import { Canvas, useFrame, type ThreeElements } from '@react-three/fiber'
import * as THREE from 'three'

// --- Palette (kept identical to the site) ------------------------------------
const TERRACOTTA = new THREE.Color('#E05240')
const CORAL = new THREE.Color('#FF8C7A')
const ESPRESSO = new THREE.Color('#3C2F2A')

const NODE_COUNT = 130
const NEIGHBOR_LINKS = 2 // edges drawn from each node to its nearest neighbours

/** A soft round sprite so points render as glowing dots, not hard squares. */
function useDotTexture() {
  return useMemo(() => {
    const size = 64
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = size
    const ctx = canvas.getContext('2d')!
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
    g.addColorStop(0, 'rgba(255,255,255,1)')
    g.addColorStop(0.35, 'rgba(255,255,255,0.9)')
    g.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)
    const tex = new THREE.CanvasTexture(canvas)
    tex.needsUpdate = true
    return tex
  }, [])
}

/** Build node positions (a soft blob) + colours + nearest-neighbour edges. */
function useGraphGeometry() {
  return useMemo(() => {
    const positions = new Float32Array(NODE_COUNT * 3)
    const colors = new Float32Array(NODE_COUNT * 3)
    const pts: THREE.Vector3[] = []

    for (let i = 0; i < NODE_COUNT; i++) {
      // Fibonacci sphere for even spread, then jitter the radius for organic depth.
      const t = i / NODE_COUNT
      const inclination = Math.acos(1 - 2 * t)
      const azimuth = Math.PI * (1 + Math.sqrt(5)) * i
      const r = 2.2 + (Math.random() - 0.5) * 1.1
      const x = r * Math.sin(inclination) * Math.cos(azimuth)
      const y = r * Math.sin(inclination) * Math.sin(azimuth) * 0.72 // flatten a touch
      const z = r * Math.cos(inclination)
      positions.set([x, y, z], i * 3)
      pts.push(new THREE.Vector3(x, y, z))

      const c = TERRACOTTA.clone().lerp(CORAL, Math.random())
      colors.set([c.r, c.g, c.b], i * 3)
    }

    // Nearest-neighbour edges → the "citation graph" look.
    const edge: number[] = []
    for (let i = 0; i < NODE_COUNT; i++) {
      const dists = pts
        .map((p, j) => ({ j, d: pts[i].distanceTo(p) }))
        .filter((o) => o.j !== i)
        .sort((a, b) => a.d - b.d)
        .slice(0, NEIGHBOR_LINKS)
      for (const { j } of dists) {
        edge.push(pts[i].x, pts[i].y, pts[i].z, pts[j].x, pts[j].y, pts[j].z)
      }
    }

    return { positions, colors, edges: new Float32Array(edge) }
  }, [])
}

function Constellation(props: ThreeElements['group']) {
  const group = useRef<THREE.Group>(null)
  const dot = useDotTexture()
  const { positions, colors, edges } = useGraphGeometry()
  const reduced =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  useFrame((state, delta) => {
    if (!group.current) return
    // Ambient slow spin (paused for reduced-motion users).
    if (!reduced) group.current.rotation.y += delta * 0.12
    // Parallax tilt toward the pointer — gives the field real depth.
    const targetX = -state.pointer.y * 0.25
    const targetZ = state.pointer.x * 0.18
    group.current.rotation.x += (targetX - group.current.rotation.x) * 0.05
    group.current.rotation.z += (targetZ - group.current.rotation.z) * 0.05
  })

  return (
    <group ref={group} {...props}>
      {/* Edges — faint espresso "pencil" lines, matching the paper aesthetic. */}
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[edges, 3]} />
        </bufferGeometry>
        <lineBasicMaterial
          color={ESPRESSO}
          transparent
          opacity={0.16}
          depthWrite={false}
        />
      </lineSegments>

      {/* Nodes — glowing terracotta→coral dots. */}
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-color" args={[colors, 3]} />
        </bufferGeometry>
        <pointsMaterial
          size={0.16}
          map={dot}
          vertexColors
          transparent
          alphaTest={0.02}
          depthWrite={false}
          sizeAttenuation
          blending={THREE.NormalBlending}
        />
      </points>
    </group>
  )
}

export default function KnowledgeField() {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 0, 7], fov: 50 }}
      gl={{ antialias: true, alpha: true }}
      style={{ background: 'transparent' }}
    >
      <Constellation />
    </Canvas>
  )
}
