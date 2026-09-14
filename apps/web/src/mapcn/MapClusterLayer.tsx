import L from 'leaflet'
import { Marker, Popup, useMap } from 'react-leaflet'
import type { FeatureCollection, Point } from 'geojson'

export interface ClusterLayerProps {
  id?: string
  data: FeatureCollection<Point>
  color?: string
  highlightColor?: string
  /** Geographic clustering radius in meters — only points of the same category within this distance are clustered. Default 100m so map doesn't feel empty. */
  clusterRadiusMeters?: number
  /** When true, cluster bubbles use same 14px size as single dots (for "All" view). */
  smallCluster?: boolean
}

function dotIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: 'mapcn-dot',
    html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,0.35);"></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })
}

function clusterIcon(count: number, color: string, small = false): L.DivIcon {
  if (small) {
    // Same 14px footprint as dotIcon, with centered count — keeps "All" visually uniform
    return L.divIcon({
      className: 'mapcn-cluster-small',
      html: `<div style="width:14px;height:14px;border-radius:50%;background:${color};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:9px;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,0.35);line-height:14px;text-align:center;">${count}</div>`,
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    })
  }
  return L.divIcon({
    className: 'mapcn-cluster',
    html: `<div style="width:32px;height:32px;border-radius:50%;background:${color};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.35);">${count}</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  })
}

function haversineMeters(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

interface PointProps {
  id?: string
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
  rating?: number | null
  review_count?: number | null
  google_category?: string | null
}

/**
 * MapCN <MapClusterLayer> — clustered dot layer for business point sets.
 * Clusters are geographic: only points of the SAME category within
 * `clusterRadiusMeters` (default 100m) are grouped. This prevents the map
 * from feeling empty — distant points of the same category stay as individual
 * pins instead of being merged into a distant cluster. Each point/cluster has
 * a detail popup that also shows data provenance.
 */
export function MapClusterLayer({ data, color = '#10b981', highlightColor = '#16a34a', clusterRadiusMeters = 100, smallCluster = false }: ClusterLayerProps) {
  const features = data?.features || []
  const map = useMap()

  // Group by category so only same-category points within 100m cluster
  const clusters = (() => {
    if (!features.length) return [] as Array<{ key: string; lat: number; lng: number; count: number; members: typeof features }>
    const byCat = new Map<string, typeof features>()
    for (const f of features) {
      const cat = ((f.properties as any)?.category as string) || 'other'
      if (!byCat.has(cat)) byCat.set(cat, [])
      byCat.get(cat)!.push(f)
    }
    const out: Array<{ key: string; lat: number; lng: number; count: number; members: typeof features }> = []
    for (const [cat, pts] of byCat) {
      const remaining = [...pts]
      const visited = new Set<number>()
      for (let i = 0; i < remaining.length; i++) {
        if (visited.has(i)) continue
        const clusterMembers: typeof features = []
        const queue: number[] = [i]
        visited.add(i)
        while (queue.length) {
          const idx = queue.shift()!
          const cur = remaining[idx]
          clusterMembers.push(cur)
          const [lngC, latC] = (cur.geometry as Point).coordinates as [number, number]
          for (let j = 0; j < remaining.length; j++) {
            if (visited.has(j)) continue
            const [lng2, lat2] = (remaining[j].geometry as Point).coordinates as [number, number]
            if (haversineMeters(latC, lngC, lat2, lng2) <= clusterRadiusMeters) {
              visited.add(j)
              queue.push(j)
            }
          }
        }
        // centroid
        let sumLat = 0, sumLng = 0
        for (const m of clusterMembers) {
          const [lng, lat] = (m.geometry as Point).coordinates as [number, number]
          sumLat += lat; sumLng += lng
        }
        out.push({
          key: `${cat}-${i}`,
          lat: sumLat / clusterMembers.length,
          lng: sumLng / clusterMembers.length,
          count: clusterMembers.length,
          members: clusterMembers,
        })
      }
    }
    return out
  })()

  if (!features.length) return null

  return (
    <>
      {clusters.map((c) => {
        if (c.count === 1) {
          const f = c.members[0]
          const [lng, lat] = (f.geometry as Point).coordinates as [number, number]
          const props = (f.properties || {}) as PointProps
          return (
            <Marker
              key={props.id ?? props.name ?? `${c.key}`}
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
                    <div className="text-xs text-gray-500">{props.google_category || props.subcategory || props.category}{props.brand ? ` · ${props.brand}` : ''}</div>
                  )}
                  {props.rating != null && (
                    <div className="text-xs font-medium text-amber-600">
                      ★ {props.rating}{props.review_count != null ? ` (${props.review_count} reviews)` : ''}
                    </div>
                  )}
                  {props.address && <div className="text-xs text-gray-600">{props.address}</div>}
                  {props.phone && <div className="text-xs text-gray-600">📞 {props.phone}</div>}
                  {props.opening_hours && <div className="text-xs text-gray-600">🕒 {props.opening_hours}</div>}
                  {props.website && (
                    <a className="text-xs text-blue-600 underline" href={props.website} target="_blank" rel="noreferrer">{props.website}</a>
                  )}
                  {props.distance_km != null && <div className="text-xs">{Number(props.distance_km).toFixed(2)} km away</div>}
                  {props.source && <div className="mt-1 text-[11px] text-gray-500">Source: {props.source}</div>}
                  {props.verification_status && <div className="text-[11px] text-gray-500">Verification: {props.verification_status}</div>}
                  {props.confidence && <div className="text-[11px] text-gray-500">Confidence: {props.confidence}</div>}
                </div>
              </Popup>
            </Marker>
          )
        }
        // cluster with count >1 — show count bubble at centroid; click zooms in
        return (
          <Marker
            key={c.key}
            position={[c.lat, c.lng]}
            icon={clusterIcon(c.count, color, smallCluster)}
            eventHandlers={{
              click: () => map.setView([c.lat, c.lng], Math.min(map.getZoom() + 2, 17), { animate: true }),
            }}
            title={`${c.count} businesses within ${clusterRadiusMeters}m`}
          >
            <Popup>
              <div className="p-1 min-w-[200px]">
                <div className="font-semibold text-gray-900">{c.count} businesses within {clusterRadiusMeters}m</div>
                <div className="text-xs text-gray-500">{(c.members[0].properties as any)?.category || 'businesses'} cluster — tap to zoom</div>
                <ul className="mt-2 max-h-32 overflow-auto text-xs text-gray-700">
                  {c.members.slice(0, 10).map((m, idx) => {
                    const p = (m.properties || {}) as PointProps
                    return <li key={idx} className="truncate">• {p.name || 'Business'}{p.rating ? ` ★${p.rating}` : ''}</li>
                  })}
                  {c.members.length > 10 && <li className="text-gray-500">+{c.members.length - 10} more</li>}
                </ul>
              </div>
            </Popup>
          </Marker>
        )
      })}
    </>
  )
}
