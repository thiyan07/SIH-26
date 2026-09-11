import { MapContainer, TileLayer, Marker, Circle, Tooltip } from 'react-leaflet'
import L from 'leaflet'
import { useEffect, useState } from 'react'

// Tamil Nadu approximate centroid
const TN_CENTER: [number, number] = [11.1271, 78.6569]
const TN_MARKER: [number, number] = [11.34, 78.0]

// Custom icon for Tamil Nadu marker
const tnIcon = L.divIcon({
  html: `<div style="
    width:14px;height:14px;background:#facc15;border:2px solid #fff;border-radius:50%;
    box-shadow:0 0 0 4px rgba(250,204,21,0.35),0 2px 8px rgba(0,0,0,0.25);
    display:flex;align-items:center;justify-content:center"></div>`,
  className: '',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
})

export function WorldMap({ className = '' }: { className?: string }) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  if (!mounted) return <div className={`animate-pulse bg-white/5 ${className}`} style={{ height: 380 }} />

  return (
    <div className={`overflow-hidden rounded-2xl ${className}`} style={{ height: 380 }}>
      <MapContainer
        center={[20, 20]}
        zoom={1.8}
        minZoom={1.5}
        maxZoom={6}
        scrollWheelZoom={false}
        dragging={true}
        zoomControl={false}
        style={{ height: '100%', width: '100%', background: '#0f172a' }}
        worldCopyJump
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        {/* Subtle emphasis circle around Tamil Nadu */}
        <Circle
          center={TN_CENTER}
          radius={180000}
          pathOptions={{
            color: '#22d3ee',
            fillColor: '#22d3ee',
            fillOpacity: 0.08,
            weight: 1.5,
            dashArray: '6 6',
            opacity: 0.6,
          }}
        />
        <Marker position={TN_MARKER} icon={tnIcon}>
          <Tooltip direction="top" offset={[0, -10]} permanent={false}>
            <div style={{ fontSize: 12, fontWeight: 700 }}>Tamil Nadu — GramBiz operating region</div>
            <div style={{ fontSize: 10, opacity: 0.7 }}>11.34°N, 78.0°E</div>
          </Tooltip>
        </Marker>
        {/* Label overlay */}
        <div className="leaflet-top leaflet-right" style={{ pointerEvents: 'none' }}>
          <div
            style={{
              margin: 12,
              padding: '6px 10px',
              background: 'rgba(15,23,42,0.85)',
              color: '#fff',
              borderRadius: 8,
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: 0.3,
              backdropFilter: 'blur(6px)',
            }}
          >
            ● Tamil Nadu
          </div>
        </div>
      </MapContainer>
      <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-white/10" />
    </div>
  )
}

export default WorldMap
