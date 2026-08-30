import { forwardRef, useEffect, type ForwardedRef, type ReactNode } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import type { Map as LeafletMap } from 'leaflet'

/**
 * India viewport bounds in Leaflet order [[south, west], [north, east]].
 * Keeps the map locked to India (no panning into the world map).
 */
export const INDIA_BOUNDS: [[number, number], [number, number]] = [
  [6.46, 68.18], // south-west (lat, lng)
  [37.06, 97.4], // north-east (lat, lng)
]

export interface MapProps {
  latitude?: number
  longitude?: number
  zoom?: number
  minZoom?: number
  maxBounds?: [[number, number], [number, number]] | null
  /** Legacy prop kept for call-site compatibility; Leaflet always uses OSM tiles. */
  styleUrl?: string
  attribution?: string
  className?: string
  children?: ReactNode
  onLoad?: (map: LeafletMap) => void
}

function MapController({ onLoad, forwardedRef }: { onLoad?: (map: LeafletMap) => void; forwardedRef?: ForwardedRef<LeafletMap | null> }) {
  const map = useMap()
  useEffect(() => {
    if (forwardedRef) {
      if (typeof forwardedRef === 'function') forwardedRef(map)
      // eslint-disable-next-line react-hooks/immutability -- legal ref mutation through a child
      else forwardedRef.current = map
    }
    if (onLoad) onLoad(map)
    return () => {
      if (forwardedRef) {
        if (typeof forwardedRef === 'function') forwardedRef(null)
        else forwardedRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map])
  return null
}

/**
 * MapCN <Map> — Leaflet map container rendering the OpenStreetMap raster
 * basemap. Uses DOM-based (Leaflet) rendering so it works in every browser,
 * including software-rendered / GPU-restricted environments where WebGL maps
 * (MapLibre) paint blank.
 */
export const Map = forwardRef<LeafletMap | null, MapProps>(
  ({ latitude = 11.446, longitude = 77.682, zoom = 10, minZoom = 4.75, maxBounds = INDIA_BOUNDS, attribution = '© OpenStreetMap contributors', className, children, onLoad }, ref) => {
    return (
      <MapContainer
        center={[latitude, longitude]}
        zoom={zoom}
        minZoom={minZoom}
        maxBounds={maxBounds ?? undefined}
        zoomControl={false}
        attributionControl={false}
        className={className}
        style={{ width: '100%', height: '100%', position: 'relative' }}
      >
        <TileLayer
          attribution={attribution}
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
          tileSize={256}
        />
        <MapController onLoad={onLoad} forwardedRef={ref} />
        {children}
      </MapContainer>
    )
  },
)
Map.displayName = 'Map'
