import { useRef, useMemo, useState } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import { OrbitControls, Stars } from "@react-three/drei"
import * as THREE from "three"

const toPos = (lat: number, lon: number, r = 1.02) => {
  const phi = (90 - lat) * (Math.PI / 180)
  const theta = (lon + 180) * (Math.PI / 180)
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta)
  )
}

const INDIA_BORDER: [number, number][] = [
  [35, 74], [33, 78], [28, 80], [24, 82], [21, 80], [18, 82],
  [15, 79], [11, 78], [8, 77], [8, 79], [10, 82], [13, 85],
  [16, 88], [20, 89], [24, 88], [27, 85], [30, 80], [34, 74],
]

const FOCUS = { lat: 11.33, lon: 77.73 }

// Lightweight graticule: only equator + tropics + prime meridian (4 lines) — was 11 lines × ~90 pts
function Graticule({ radius = 1.005 }: { radius?: number }) {
  const lines = useMemo(() => {
    const pts: THREE.Vector3[][] = []
    for (const lat of [0, 23.5, -23.5]) {
      const arr: THREE.Vector3[] = []
      for (let lon = -180; lon <= 180; lon += 6) arr.push(toPos(lat, lon, radius))
      pts.push(arr)
    }
    for (const lon of [0]) {
      const arr: THREE.Vector3[] = []
      for (let lat = -80; lat <= 80; lat += 4) arr.push(toPos(lat, lon, radius))
      pts.push(arr)
    }
    return pts
  }, [radius])
  return (
    <>
      {lines.map((p, i) => (
        <line key={i}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              args={[new Float32Array(p.flatMap(v => [v.x, v.y, v.z])), 3]}
            />
          </bufferGeometry>
          <lineBasicMaterial color="#ffffff" transparent opacity={0.05} />
        </line>
      ))}
    </>
  )
}

function IndiaBorder({ radius = 1.008 }: { radius?: number }) {
  const pts = useMemo(() => INDIA_BORDER.map(([lat, lon]) => toPos(lat, lon, radius)), [radius])
  const pos = useMemo(() => new Float32Array(pts.flatMap(p => [p.x, p.y, p.z])), [pts])
  return (
    <line>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[pos, 3]} />
      </bufferGeometry>
      <lineBasicMaterial color="#f59e0b" transparent opacity={0.95} />
    </line>
  )
}

function Atmosphere() {
  return (
    <mesh>
      <sphereGeometry args={[1.08, 32, 32]} />
      <meshStandardMaterial color="#06b6d4" transparent opacity={0.06} side={THREE.BackSide} />
    </mesh>
  )
}

function BusinessPoints({ businesses }: { businesses: { lat: number; lon: number }[] }) {
  // Static — no group rotation per-frame (prev rotated entire group every frame)
  const points = businesses.length ? businesses.slice(0, 60) : [
    { lat: 11.34, lon: 77.72 }, { lat: 11.28, lon: 77.58 }, { lat: 11.45, lon: 77.43 },
    { lat: 11.0, lon: 77.9 }, { lat: 12.9, lon: 80.2 }, { lat: 28.6, lon: 77.2 },
  ]
  return (
    <group>
      {points.map((b, i) => {
        const p = toPos(b.lat, b.lon, 1.015)
        const isFocus = Math.abs(b.lat - FOCUS.lat) < 1.2 && Math.abs(b.lon - FOCUS.lon) < 1.2
        return (
          <mesh key={i} position={p}>
            <sphereGeometry args={[isFocus ? 0.016 : 0.009, 6, 6]} />
            <meshStandardMaterial
              color={isFocus ? "#facc15" : "#f59e0b"}
              emissive={isFocus ? "#facc15" : "#f59e0b"}
              emissiveIntensity={isFocus ? 1.2 : 0.75}
            />
          </mesh>
        )
      })}
    </group>
  )
}

function WorldCountryBorders({ radius = 1.006 }: { radius?: number }) {
  // Simplified world country outlines (major countries + India focus) — visible borders while spinning
  const WORLD_BORDERS: [number, number][][] = [
    // India (detailed)
    INDIA_BORDER,
    // Pakistan
    [[37, 67], [35, 72], [31, 74], [28, 73], [24, 68], [30, 65], [35, 67]],
    // Bangladesh
    [[26, 88], [24, 90], [22, 90], [22, 88], [26, 88]],
    // China (approx)
    [[42, 75], [42, 92], [38, 105], [32, 110], [28, 108], [22, 100], [28, 90], [32, 80], [38, 75], [42, 75]],
    // USA (approx)
    [[49, -125], [49, -66], [25, -80], [25, -125], [49, -125]],
    // Russia (approx)
    [[60, 30], [70, 60], [68, 120], [60, 170], [50, 30], [60, 30]],
    // Brazil
    [[5, -60], [0, -50], [-10, -48], [-20, -45], [-25, -55], [-15, -65], [5, -60]],
    // Africa outline (approx)
    [[35, -15], [30, 30], [-30, 35], [-35, 15], [-10, -10], [35, -15]],
    // Australia
    [[-12, 113], [-12, 154], [-28, 154], [-28, 113], [-12, 113]],
    // Europe (approx)
    [[45, -10], [55, 10], [50, 30], [40, 20], [35, 0], [45, -10]],
  ]
  return (
    <>
      {WORLD_BORDERS.map((border, idx) => {
        const pts = border.map(([lat, lon]) => toPos(lat, lon, radius))
        const pos = new Float32Array(pts.flatMap(p => [p.x, p.y, p.z]))
        const isIndia = idx === 0
        return (
          <line key={idx}>
            <bufferGeometry>
              <bufferAttribute attach="attributes-position" args={[pos, 3]} />
            </bufferGeometry>
            <lineBasicMaterial color={isIndia ? "#facc15" : "#93c5fd"} transparent opacity={isIndia ? 0.95 : 0.35} linewidth={isIndia ? 1.5 : 1} />
          </line>
        )
      })}
    </>
  )
}

function TamilNaduMarker() {
  const p = toPos(FOCUS.lat, FOCUS.lon, 1.03)
  return (
    <group position={p}>
      <mesh>
        <sphereGeometry args={[0.022, 12, 12]} />
        <meshStandardMaterial color="#facc15" emissive="#facc15" emissiveIntensity={1.4} />
      </mesh>
      <mesh>
        <ringGeometry args={[0.03, 0.05, 24]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.65} side={THREE.DoubleSide} />
      </mesh>
      {/* Label billboard - always faces camera via text handled by overlay */}
    </group>
  )
}

function Earth({ businesses = [] as { lat: number; lon: number }[], paused = false }) {
  const groupRef = useRef<THREE.Group>(null!)
  let tick = 0
  useFrame(() => {
    if (paused) return
    tick++
    if (tick % 2 === 0 && groupRef.current) groupRef.current.rotation.y += 0.0012
  })

  return (
    <group ref={groupRef}>
      <mesh>
        <sphereGeometry args={[1, 40, 40]} />
        <meshStandardMaterial color="#0e4266" roughness={0.68} metalness={0.18} />
      </mesh>

      <mesh>
        <sphereGeometry args={[1.001, 32, 32]} />
        <meshStandardMaterial color="#0ea5a5" wireframe transparent opacity={0.02} />
      </mesh>

      <Graticule />
      <WorldCountryBorders />
      <IndiaBorder />
      <Atmosphere />
      <TamilNaduMarker />
      <BusinessPoints businesses={businesses} />
    </group>
  )
}

export function Globe({ businesses, className = "" }: { businesses?: { lat: number; lon: number }[]; className?: string }) {
  const [isVisible, setIsVisible] = useState(true)
  // lightweight observer via ref callback — pauses globe when scrolled out of view
  const setRef = (el: HTMLDivElement | null) => {
    if (!el) return
    const io = new IntersectionObserver(([e]) => setIsVisible(e.isIntersecting), { threshold: 0.06 })
    io.observe(el)
  }
  return (
    <div ref={setRef as any} className={`relative overflow-hidden rounded-xl bg-gradient-to-br from-slate-950 via-[#0a2233] to-slate-950 [contain:layout_paint] ${className}`}>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_58%,_rgba(0,0,0,0.42)_100%)]" />
      <Canvas
        camera={{ position: [0, 0.18, 2.35], fov: 45 }}
        className="h-full w-full"
        dpr={[1, 1.45]}
        gl={{ antialias: true, powerPreference: "high-performance", stencil: false, depth: true }}
        performance={{ min: 0.5 }}
        frameloop={isVisible ? "always" : "demand"}
      >
        <ambientLight intensity={0.55} />
        <directionalLight position={[2.5, 2, 1.5]} intensity={1.02} />
        <directionalLight position={[-2, -1.5, -2]} intensity={0.28} color="#38bdf8" />
        <Earth businesses={businesses} paused={!isVisible} />
        <Stars radius={12} depth={30} count={650} factor={3.2} fade speed={0} />
        <OrbitControls
          enableZoom={false}
          enablePan={false}
          autoRotate={isVisible}
          autoRotateSpeed={0.22}
          minPolarAngle={Math.PI / 3}
          maxPolarAngle={Math.PI / 1.6}
          enableDamping
          dampingFactor={0.08}
        />
      </Canvas>
    </div>
  )
}

export function GlobeFallback({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center rounded-xl bg-gradient-to-br from-teal-900 via-slate-900 to-slate-950 p-8 text-white ${className}`}>
      <div className="text-center">
        <div className="text-5xl">🌍</div>
        <div className="mt-2 text-sm opacity-80">Tamil Nadu • Evidence Coverage Map</div>
        <div className="mt-1 text-[11px] opacity-60">Strongest evidence in Tamil Nadu; global view is illustrative</div>
      </div>
    </div>
  )
}

export default Globe
