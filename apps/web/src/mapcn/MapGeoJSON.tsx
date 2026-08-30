import { GeoJSON } from 'react-leaflet'
import L from 'leaflet'
import type { GeoJsonObject } from 'geojson'

export interface GeoJSONLayerProps {
  id?: string
  data: GeoJsonObject
  fillColor?: string
  fillOpacity?: number
  lineColor?: string
  circleRadius?: number
  circleColor?: string
}

/**
 * MapCN <MapGeoJSON> — Leaflet GeoJSON layer.
 * Point features render as circles; polygon features as filled/outlined paths.
 */
export function MapGeoJSON({
  data,
  fillColor = '#16a34a',
  fillOpacity = 0.15,
  lineColor = '#166534',
  circleRadius = 6,
  circleColor = '#16a34a',
}: GeoJSONLayerProps) {
  return (
    <GeoJSON
      data={data}
      style={() => ({ color: lineColor, weight: 2, fillColor, fillOpacity })}
      pointToLayer={(_feature, latlng) =>
        L.circleMarker(latlng, {
          radius: circleRadius,
          color: '#ffffff',
          weight: 1,
          fillColor: circleColor,
          fillOpacity: 0.9,
        })
      }
    />
  )
}
