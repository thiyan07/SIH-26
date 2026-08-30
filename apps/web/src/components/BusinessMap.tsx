import { useState } from 'react'
import type { Business, InfrastructurePoint, MapPoint } from '../types'
import { businessesToGeoJSON, infrastructureToGeoJSON, pointsToGeoJSON } from '../lib/geo'
import {
  Map,
  MapControls,
  MapGeoJSON,
  MapMarker,
  MapClusterLayer,
  createRadiusGeoJSON,
} from '../mapcn'

export interface BusinessMapProps {
  center: { latitude: number; longitude: number }
  businesses?: Business[]
  competitors?: Business[]
  markets?: MapPoint[]
  infrastructure?: InfrastructurePoint[]
  showRadius?: boolean
  zoom?: number
  height?: string
}

const layerOptions = [
  { key: 'all', label: 'All' },
  { key: 'competitors', label: 'Competitors' },
  { key: 'markets', label: 'Markets' },
  { key: 'restaurants', label: 'Restaurants' },
  { key: 'retail', label: 'Retail' },
  { key: 'infrastructure', label: 'Infrastructure' },
]

export function BusinessMap({ center, businesses = [], competitors = [], markets = [], infrastructure = [], showRadius = true, zoom = 12, height = '420px' }: BusinessMapProps) {
  const [layer, setLayer] = useState('all')

  // Layer toggles select which data the map shows (plan §26).
  const showBusinesses = layer === 'all' || layer === 'restaurants' || layer === 'retail'
  const showCompetitors = layer === 'all' || layer === 'competitors'
  const showMarkets = layer === 'all' || layer === 'markets'
  const showInfrastructure = layer === 'all' || layer === 'infrastructure'
  const comps = showCompetitors ? competitors : []
  const allShown = showBusinesses
    ? businesses.filter((b) => {
        if (layer === 'restaurants') return b.category_code === 'restaurant'
        if (layer === 'retail') return b.category_code === 'grocery' || b.category_code === 'textile'
        return true
      })
    : []

  const radius5 = createRadiusGeoJSON(center.latitude, center.longitude, 5, 'r5')
  const radius10 = createRadiusGeoJSON(center.latitude, center.longitude, 10, 'r10')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height, width: '100%' }}>
      <div className="mb-2 flex shrink-0 flex-wrap gap-1">
        {layerOptions.map((l) => (
          <button
            key={l.key}
            onClick={() => setLayer(l.key)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium ${
              layer === l.key ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>
      <div style={{ flex: '1 1 auto', minHeight: 0, borderRadius: 12, overflow: 'hidden' }}>
        <Map latitude={center.latitude} longitude={center.longitude} zoom={zoom}>
          <MapControls navigation />
          {showRadius && <MapGeoJSON id="radius5" data={radius5} fillColor="#16a34a" fillOpacity={0.05} lineColor="#15803d" />}
          {showRadius && <MapGeoJSON id="radius10" data={radius10} fillOpacity={0.03} />}
          <MapMarker latitude={center.latitude} longitude={center.longitude} color="#111827" label="You are here" />
          <MapClusterLayer id="businesses" data={businessesToGeoJSON(allShown)} />
          {showMarkets && markets.length > 0 && (
            <MapGeoJSON id="markets" data={pointsToGeoJSON(markets)} circleColor="#d97706" />
          )}
          {showInfrastructure && infrastructure.length > 0 && (
            <MapGeoJSON id="infrastructure" data={infrastructureToGeoJSON(infrastructure)} circleColor="#7c3aed" circleRadius={5} />
          )}
          {comps.map((c) => (
            <MapMarker
              key={c.id}
              latitude={c.latitude}
              longitude={c.longitude}
              color="#dc2626"
              label={c.name}
              popup={`${c.category_code || ''} · ${c.distance_km != null ? c.distance_km + ' km' : ''}`}
            />
          ))}
        </Map>
      </div>
      <p className="mt-1 shrink-0 text-[10px] text-gray-400">© OpenStreetMap contributors. Mapped business data may be incomplete.</p>
    </div>
  )
}
