import { useRef } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import { OrbitControls, Stars } from "@react-three/drei"
import * as THREE from "three"

function Earth({ businesses = [] as { lat: number; lon: number }[] }) {
  const meshRef = useRef<THREE.Mesh>(null!)
  useFrame(() => { if (meshRef.current) meshRef.current.rotation.y += 0.0015 })

  // Convert lat/lon to 3D position on sphere r=1.02
  const toPos = (lat: number, lon: number, r = 1.02) => {
    const phi = (90 - lat) * (Math.PI / 180)
    const theta = (lon + 180) * (Math.PI / 180)
    return new THREE.Vector3(-r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta))
  }

  return (
    <>
      <mesh ref={meshRef}>
        <sphereGeometry args={[1, 64, 64]} />
        <meshStandardMaterial color="#0e7490" roughness={0.7} metalness={0.2} />
      </mesh>
      <mesh>
        <sphereGeometry args={[1.015, 64, 64]} />
        <meshStandardMaterial color="#134e4a" wireframe transparent opacity={0.08} />
      </mesh>
      {businesses.slice(0, 80).map((b, i) => {
        const p = toPos(b.lat, b.lon)
        return (
          <mesh key={i} position={p}>
            <sphereGeometry args={[0.012, 8, 8]} />
            <meshStandardMaterial color="#f59e0b" emissive="#f59e0b" emissiveIntensity={0.8} />
          </mesh>
        )
      })}
    </>
  )
}

export function Globe({ businesses, className = "" }: { businesses?: { lat: number; lon: number }[]; className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-xl bg-slate-950 ${className}`}>
      <Canvas camera={{ position: [0, 0, 2.2], fov: 50 }} className="h-full w-full">
        <ambientLight intensity={0.6} />
        <directionalLight position={[2, 2, 2]} intensity={1.2} />
        <pointLight position={[-2, -2, -2]} intensity={0.5} color="#06b6d4" />
        <Earth businesses={businesses} />
        <Stars radius={10} depth={50} count={2000} factor={4} fade speed={0.5} />
        <OrbitControls enableZoom={false} enablePan={false} autoRotate autoRotateSpeed={0.4} minPolarAngle={Math.PI / 3} maxPolarAngle={Math.PI / 1.5} />
      </Canvas>
      <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-black/40 px-2 py-1 text-xs text-white/70">Erode • 295 villages • 5012 businesses</div>
    </div>
  )
}

// Fallback without Three.js (if WebGL unavailable)
export function GlobeFallback({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center rounded-xl bg-gradient-to-br from-teal-900 to-slate-900 p-8 text-white ${className}`}>
      <div className="text-center">
        <div className="text-5xl">🌍</div>
        <div className="mt-2 text-sm opacity-80">Erode District • Interactive 3D</div>
      </div>
    </div>
  )
}

export default Globe
