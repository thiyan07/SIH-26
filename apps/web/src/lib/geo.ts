import type { FeatureCollection, Point } from 'geojson'
import type { Business, InfrastructurePoint, MapPoint } from '../types'

export function businessesToGeoJSON(businesses: Business[]): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: (businesses || []).map((b) => ({
      type: 'Feature',
      properties: {
        id: b.id,
        name: b.name,
        category: b.category_code,
        distance_km: b.distance_km,
        source: b.source_name,
        is_demo: b.is_demo,
      },
      geometry: { type: 'Point', coordinates: [b.longitude, b.latitude] },
    })),
  }
}

export function pointsToGeoJSON(points: MapPoint[]): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: (points || []).map((p) => ({
      type: 'Feature',
      properties: {
        id: p.id,
        name: p.name,
        kind: p.kind,
        source: p.source_name,
        is_demo: p.is_demo,
      },
      geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
    })),
  }
}

export function infrastructureToGeoJSON(points: InfrastructurePoint[]): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: (points || []).map((p) => ({
      type: 'Feature',
      properties: {
        id: p.id,
        name: p.name,
        kind: p.kind,
        distance_km: p.distance_km,
        source: p.source_name,
        confidence: p.confidence,
        is_demo: p.is_demo,
      },
      geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
    })),
  }
}

/** Decode backend GeoJSON layer features into plain point objects for layers. */
export function pointsFromGeoJSON(features: any[]): MapPoint[] {
  return (features || [])
    .filter((f) => f.geometry?.type === 'Point')
    .map((f) => ({
      id: f.properties?.id,
      name: f.properties?.name,
      kind: f.properties?.kind,
      latitude: f.geometry.coordinates[1],
      longitude: f.geometry.coordinates[0],
      distance_km: f.properties?.distance_km,
      source_name: f.properties?.source_name,
      confidence: f.properties?.confidence,
    }))
}