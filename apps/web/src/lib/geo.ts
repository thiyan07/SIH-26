import type { FeatureCollection, Point } from 'geojson'
import type { Business, InfrastructurePoint, MapPoint, MSMECluster } from '../types'

export interface GeoCoordinate {
  latitude: number
  longitude: number
}

export type GeolocationFailure =
  | { code: 'denied' }
  | { code: 'unavailable' }
  | { code: 'timeout' }
  | { code: 'unsupported' }
  | { code: 'error'; message: string }

/**
 * Promise wrapper around the browser Geolocation API (a single, shared helper).
 * No coordinates are persisted or sent anywhere by this function — the caller
 * decides when to use them (the required flow is: locate -> draft -> confirm).
 */
export function getCurrentPosition(
  options?: PositionOptions,
): Promise<GeoCoordinate> {
  return new Promise((resolve, reject) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      reject({ code: 'unsupported' } as GeolocationFailure)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        })
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) reject({ code: 'denied' } as GeolocationFailure)
        else if (err.code === err.POSITION_UNAVAILABLE) reject({ code: 'unavailable' } as GeolocationFailure)
        else if (err.code === err.TIMEOUT) reject({ code: 'timeout' } as GeolocationFailure)
        else reject({ code: 'error', message: err.message } as GeolocationFailure)
      },
      options ?? { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    )
  })
}

export function geolocationMessage(failure: GeolocationFailure): string {
  switch (failure.code) {
    case 'denied':
      return 'Location permission was denied. You can choose the location manually on the map.'
    case 'unavailable':
      return 'Unable to determine your location. Please choose the location manually.'
    case 'timeout':
      return 'Location request timed out. Please try again or choose the location manually.'
    case 'unsupported':
      return 'Your browser does not support location services. Please choose the location manually.'
    default:
      return failure.message || 'Location request failed. Please choose the location manually.'
  }
}

export function businessesToGeoJSON(businesses: Business[]): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: (businesses || []).map((b) => ({
      type: 'Feature',
      properties: {
        id: b.id,
        name: b.name,
        category: b.category_code,
        subcategory: b.subcategory,
        address: b.address,
        phone: b.phone,
        website: b.website,
        opening_hours: b.opening_hours,
        brand: b.brand,
        distance_km: b.distance_km,
        source: b.source_name,
        source_type: b.source_type,
        confidence: b.confidence,
        verification_status: b.verification_status,
        is_demo: b.is_demo,
        rating: b.metadata?.rating,
        review_count: b.metadata?.review_count,
        google_category: b.metadata?.google_category,
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

/** Encode pincode-cluster MSME points as a GeoJSON feature layer, sized by count. */
export function msmeClustersToGeoJSON(clusters: MSMECluster[]): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: (clusters || []).map((c) => ({
      type: 'Feature',
      properties: {
        pincode: c.pincode,
        total: c.total,
        activity_codes: c.activity_codes,
        distance_km: c.distance_km,
        geo_resolution: c.geo_resolution || 'pincode',
      },
      geometry: { type: 'Point', coordinates: [c.longitude, c.latitude] },
    })),
  }
}

/** Decode MSME pincode-cluster GeoJSON features into plain cluster points. */
export function msmeClustersFromGeoJSON(features: any[]): MSMECluster[] {
  return (features || [])
    .filter((f) => f.geometry?.type === 'Point')
    .map((f) => ({
      pincode: f.properties?.pincode,
      total: f.properties?.total,
      activity_codes: f.properties?.activity_codes,
      latitude: f.geometry.coordinates[1],
      longitude: f.geometry.coordinates[0],
      distance_km: f.properties?.distance_km,
      geo_resolution: f.properties?.geo_resolution,
      units: f.properties?.units ?? [],
    }))
}