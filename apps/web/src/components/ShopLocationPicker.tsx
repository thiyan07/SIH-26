import { useEffect, useRef, useState } from 'react'
import type { Map as LeafletMap } from 'leaflet'
import { Marker, useMapEvents } from 'react-leaflet'
import { Map } from '../mapcn'
import { api } from '../lib/api'
import { geolocationMessage, getCurrentPosition } from '../lib/geo'
import type { GeocodeResult } from '../types'

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
 * shop location.
 *
 * Three ways to place the pin:
 *  1. drag the marker or click the map (manual),
 *  2. "Use my location" (browser GPS),
 *  3. place/address search (backend geocoder proxy).
 *
 * Coordinates are surfaced (but not committed) via onProposedChange until a
 * later "Confirm location" action; any new placement marks the pin as
 * unconfirmed (the parent clears the previous confirmation).
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

  const [gpsState, setGpsState] = useState<'idle' | 'locating' | 'detected'>('idle')
  const [gpsError, setGpsError] = useState<string | null>(null)

  const [searchQ, setSearchQ] = useState('')
  const [places, setPlaces] = useState<GeocodeResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [searchedFor, setSearchedFor] = useState('')
  const [selectedPlace, setSelectedPlace] = useState<string | null>(null)

  // Reset the marker (and recentre) only when the admin-area baseline changes,
  // never when a confirmation is cleared by a marker move.
  const prevAdmin = useRef({ lat: latitude, lng: longitude })
  useEffect(() => {
    if (prevAdmin.current.lat === latitude && prevAdmin.current.lng === longitude) return
    prevAdmin.current = { lat: latitude, lng: longitude }
    setPos({ lat: latitude, lng: longitude })
    map?.setView([latitude, longitude], Math.max(map.getZoom() ?? 14, 14))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latitude, longitude])

  const centerMap = (lat: number, lng: number) => {
    if (!map) return
    map.setView([lat, lng], Math.max(map.getZoom() ?? 14, 14))
  }

  const move = (lat: number, lng: number) => {
    setPos({ lat, lng })
    onProposedChange?.(lat, lng)
  }

  // Manual: drag or click. Marker stays where it is placed (no recentre).
  const handleManualMove = (lat: number, lng: number) => {
    setGpsState('idle')
    setGpsError(null)
    move(lat, lng)
    if (selectedPlace !== null) setSelectedPlace(null)
  }

  // GPS: locate, then move the marker + centre the map. Never auto-confirms.
  const handleUseMyLocation = () => {
    setGpsError(null)
    setGpsState('locating')
    getCurrentPosition()
      .then((c) => {
        setGpsState('detected')
        if (selectedPlace !== null) setSelectedPlace(null)
        move(c.latitude, c.longitude)
        centerMap(c.latitude, c.longitude)
      })
      .catch((fail: unknown) => {
        setGpsState('idle')
        setGpsError(
          typeof fail === 'object' && fail !== null && 'code' in fail
            ? geolocationMessage(fail as Parameters<typeof geolocationMessage>[0])
            : 'Unable to determine your location. Please choose the location manually.',
        )
      })
  }

  // Debounced place/address search through the backend geocoder (proxy keeps
  // provider keys server-side). Biased towards the selected admin area.
  useEffect(() => {
    const q = searchQ.trim()
    if (q.length < 3) {
      setPlaces([])
      setSearching(false)
      setSearchError(null)
      return
    }
    setSearching(true)
    setSearchError(null)
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ q, limit: '6' })
      if (latitude) params.set('lat', String(latitude))
      if (longitude) params.set('lng', String(longitude))
      api
        .get<GeocodeResult[]>(`/geocode/search?${params.toString()}`)
        .then((r) => {
          setPlaces(r)
          setSearchedFor(q)
        })
        .catch(() => {
          setPlaces([])
          setSearchedFor(q)
          setSearchError('Search failed. Please try again or pick the location on the map.')
        })
        .finally(() => setSearching(false))
    }, 400)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQ])

  const showNoPlaces =
    !searching && !searchError && searchedFor !== '' && searchedFor === searchQ.trim() && places.length === 0

  const selectPlace = (p: GeocodeResult) => {
    setPlaces([])
    setSearchQ('')
    setSelectedPlace(p.display_name || p.name)
    setGpsState('idle')
    setGpsError(null)
    move(p.latitude, p.longitude)
    centerMap(p.latitude, p.longitude)
  }

  const statusText = confirmed
    ? '✓ Confirmed'
    : map
      ? 'Drag the pin, click the map, search, or use your location'
      : 'Loading map…'

  return (
    <div>
      <div className="mb-2 space-y-2">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder="Search exact place (e.g. Bhavani Bus Stand)…"
              aria-label="Search exact place"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 pr-16 text-sm"
            />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">
              {searching ? '…' : '🔍'}
            </span>
          </div>
          <button
            type="button"
            onClick={handleUseMyLocation}
            disabled={gpsState === 'locating'}
            className="shrink-0 rounded-lg border border-brand-600 px-3 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-60"
          >
            {gpsState === 'locating' ? 'Locating…' : 'Use my location'}
          </button>
        </div>

        {selectedPlace && (
          <p className="text-xs text-brand-700">
            Selected place: <span className="font-medium">{selectedPlace}</span> — review the exact spot, then confirm it below.
          </p>
        )}
        {gpsState === 'detected' && (
          <p className="text-xs font-medium text-emerald-600">Current location detected</p>
        )}
        {gpsError && <p className="text-xs text-amber-600">{gpsError}</p>}
        {searchError && <p className="text-xs text-amber-600">{searchError}</p>}

        {places.length > 0 && (
          <ul className="max-h-44 overflow-auto rounded-lg border border-gray-200 bg-white">
            {places.map((p, i) => (
              <li key={`${p.latitude},${p.longitude}-${i}`}>
                <button
                  type="button"
                  onClick={() => selectPlace(p)}
                  className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-brand-50"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-gray-800">{p.name}</span>
                    <span className="block truncate text-[11px] text-gray-400">{p.display_name}</span>
                  </span>
                  <span className="shrink-0 rounded border border-brand-200 bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-700">
                    Select
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {!searching && !searchError && showNoPlaces && (
          <p className="text-xs text-gray-400">No places found for "{searchedFor}".</p>
        )}
      </div>

      <div style={{ height, width: '100%', borderRadius: 12, overflow: 'hidden' }}>
        <Map latitude={latitude} longitude={longitude} zoom={14} onLoad={setMap}>
          <MapClickToMove onMove={handleManualMove} />
          <Marker
            draggable
            position={[pos.lat, pos.lng]}
            eventHandlers={{
              dragend: (e) => {
                const ll = (e.target as { getLatLng: () => { lat: number; lng: number } }).getLatLng()
                handleManualMove(ll.lat, ll.lng)
              },
            }}
          />
        </Map>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-gray-50 p-2 text-xs text-gray-600">
        <span className="font-mono">
          {pos.lat.toFixed(5)}, {pos.lng.toFixed(5)}
        </span>
        <span className={confirmed ? 'text-emerald-600' : 'text-amber-600'}>{statusText}</span>
      </div>
    </div>
  )
}