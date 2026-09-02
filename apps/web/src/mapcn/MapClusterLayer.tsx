import L from 'leaflet'
import { Marker, Popup } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import type { FeatureCollection, Point } from 'geojson'

export interface ClusterLayerProps {
  id?: string
  data: FeatureCollection<Point>
  color?: string
  highlightColor?: string
}

function dotIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: 'mapcn-dot',
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,0.35);"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

interface PointProps {
  name?: string
  category?: string
  subcategory?: string
  address?: string
  phone?: string
  website?: string
  opening_hours?: string
  brand?: string
  distance_km?: number | null
  source?: string
  source_type?: string
  is_demo?: boolean
  confidence?: string
  verification_status?: string
}

/**
 * MapCN <MapClusterLayer> — clustered dot layer for business point sets.
 * Nearby points group into numbered clusters; each point has a detail popup
 * that also shows data provenance (source + demo/test marker) so users can
 * tell verified mappings from demonstration rows.
 */
export function MapClusterLayer({ data, color = '#10b981', highlightColor = '#16a34a' }: ClusterLayerProps) {
  const features = data?.features || []
  return (
    <MarkerClusterGroup
      showCoverageOnHover={false}
      spiderfyOnMaxZoom
      iconCreateFunction={(cluster: { getChildCount: () => number }) =>
        L.divIcon({
          html: `<div style="width:32px;height:32px;border-radius:50%;background:${color};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.35);">${cluster.getChildCount()}</div>`,
          className: 'mapcn-cluster',
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        })
      }
    >
      {features.map((f, i) => {
        const coords = (f.geometry as Point)?.coordinates
        if (!coords) return null
        const [lng, lat] = coords
        const props = (f.properties || {}) as PointProps
        return (
          <Marker
            key={props.name ?? i}
            position={[lat, lng]}
            icon={dotIcon(highlightColor)}
            title={props.name || ''}
          >
            <Popup>
              <div className="p-1 min-w-[180px]">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-gray-900">{props.name || 'Business'}</span>
                  {props.is_demo && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">Demo/test</span>}
                </div>
                {(props.category || props.subcategory) && (
                  <div className="text-xs text-gray-500">{props.subcategory || props.category}{props.brand ? ` · ${props.brand}` : ''}</div>
                )}
                {props.address && <div className="text-xs text-gray-600">{props.address}</div>}
                {props.phone && <div className="text-xs text-gray-600">📞 {props.phone}</div>}
                {props.opening_hours && <div className="text-xs text-gray-600">🕒 {props.opening_hours}</div>}
                {props.website && (
                  <a className="text-xs text-blue-600 underline" href={props.website} target="_blank" rel="noreferrer">{props.website}</a>
                )}
                {props.distance_km != null && <div className="text-xs">{Number(props.distance_km).toFixed(2)} km away</div>}
                {props.source && <div className="mt-1 text-[11px] text-gray-400">Source: {props.source}</div>}
                {props.verification_status && <div className="text-[11px] text-gray-400">Verification: {props.verification_status}</div>}
                {props.confidence && <div className="text-[11px] text-gray-400">Confidence: {props.confidence}</div>}
              </div>
            </Popup>
          </Marker>
        )
      })}
    </MarkerClusterGroup>
  )
}
