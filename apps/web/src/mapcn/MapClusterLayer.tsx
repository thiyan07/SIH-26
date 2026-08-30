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
  distance_km?: number | null
}

/**
 * MapCN <MapClusterLayer> — clustered dot layer for business point sets.
 * Nearby points group into numbered clusters; each point has a detail popup.
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
              <div className="p-1">
                <div className="font-semibold text-gray-900">{props.name || 'Business'}</div>
                {props.category && <div className="text-xs text-gray-500">{props.category}</div>}
                {props.distance_km != null && <div className="text-xs">{Number(props.distance_km).toFixed(2)} km away</div>}
              </div>
            </Popup>
          </Marker>
        )
      })}
    </MarkerClusterGroup>
  )
}
