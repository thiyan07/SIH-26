import { useMap as useReactLeafletMap } from 'react-leaflet'
import type { Map as LeafletMap } from 'leaflet'

/**
 * Access the active Leaflet map instance.
 * Only valid for components rendered inside a mapcn <Map>.
 */
export function useMap(): LeafletMap {
  return useReactLeafletMap()
}
