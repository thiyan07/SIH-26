import { useEffect, useState } from 'react'
import type { Map as LeafletMap } from 'leaflet'
import { Marker, useMapEvents } from 'react-leaflet'
import { Map } from '../mapcn'

export interface ShopLocationPickerProps {
  /** Admin-area baseline the map and marker start from. */
  latitude: number
  longitude: number
  /** Called whenever the exact proposed coordinates change (before confirm). */
  onProposedChange?: (lat: number, lng: number) => void
  /** Confirmed exact coordinates, if any. */
  confirmedLat?: number | null
  confirmedLng?: number | null
  height?: string
}

function MapClickToMove({ onMove }: { onMove: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onMove(e.latlng.lat, e.latlng.lng)
    },
  })
  return null
}

/**
 * ShopLocationPicker — draggable map marker for pinning the exact proposed
 * shop location. The user drags or clicks to place the pin; the coordinates
 * are surfaced (but not committed) until a later "Confirm location" action.
 */
export function ShopLocationPicker({
  latitude,
  longitude,
  onProposedChange,
  confirmedLat,
  confirmedLng,
  height = '280px',
}: ShopLocationPickerProps) {
  const [pos, setPos] = useState<{ lat: number; lng: number }>({ lat: latitude, lng: longitude })
  const [map, setMap] = useState<LeafletMap | null>(null)
  const confirmed = confirmedLat != null && confirmedLng != null

  useEffect(() => {
    if (confirmedLat != null && confirmedLng != null) return
    setPos({ lat: latitude, lng: longitude })
  }, [latitude, longitude, confirmedLat, confirmedLng])

  const move = (lat: number, lng: number) => {
    setPos({ lat, lng })
    onProposedChange?.(lat, lng)
  }

  return (
    <div>
      <div style={{ height, width: '100%', borderRadius: 12, overflow: 'hidden' }}>
        <Map latitude={latitude} longitude={longitude} zoom={14} onLoad={setMap}>
          <MapClickToMove onMove={move} />
          <Marker
            draggable
            position={[pos.lat, pos.lng]}
            eventHandlers={{
              dragend: (e) => {
                const ll = (e.target as any).getLatLng()
                move(ll.lat, ll.lng)
              },
            }}
          />
        </Map>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-gray-50 p-2 text-xs text-gray-600">
        <span className="font-mono">
          {pos.lat.toFixed(5)}, {pos.lng.toFixed(5)}
        </span>
        <span className={confirmed ? 'text-emerald-600' : 'text-amber-600'}>
          {confirmed ? 'Location confirmed' : map ? 'Drag the pin or click the map' : 'Loading map…'}
        </span>
      </div>
    </div>
  )
}
