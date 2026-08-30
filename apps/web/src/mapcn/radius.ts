import type { FeatureCollection, GeoJsonProperties, Polygon } from 'geojson'

/** Approximate equirectangular circle polygon GeoJSON for radius visualization. */
export function createRadiusGeoJSON(
  lat: number,
  lon: number,
  radiusKm: number,
  id?: string,
): FeatureCollection<Polygon, GeoJsonProperties> {
  const coords: [number, number][] = []
  const points = 64
  for (let i = 0; i < points; i++) {
    const bearing = (i / points) * 2 * Math.PI
    const dx = radiusKm * Math.cos(bearing)
    const dy = radiusKm * Math.sin(bearing)
    const dLat = dy / 111.32
    const dLon = dx / (111.32 * Math.cos((lat * Math.PI) / 180))
    coords.push([lon + dLon, lat + dLat])
  }
  coords.push(coords[0])
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        id,
        properties: { radius_km: radiusKm, name: `${radiusKm} km` },
        geometry: { type: 'Polygon', coordinates: [coords] },
      },
    ],
  }
}
