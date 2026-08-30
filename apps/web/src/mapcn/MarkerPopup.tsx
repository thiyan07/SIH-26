import type { ReactNode } from 'react'
import L from 'leaflet'
import { Marker, Popup } from 'react-leaflet'

export interface MarkerContentProps {
  latitude: number
  longitude: number
  children?: ReactNode
  open?: boolean
}

const transparentIcon = L.divIcon({ className: '', html: '', iconSize: [0, 0], iconAnchor: [0, 0] })

/**
 * MapCN <MarkerPopup> — a Leaflet marker whose popup content is a React node.
 * The marker itself is invisible; only the popup is rendered.
 */
export function MarkerPopup({ latitude, longitude, children, open = true }: MarkerContentProps) {
  return (
    <Marker position={[latitude, longitude]} icon={transparentIcon}>
      {open && children != null && <Popup>{children}</Popup>}
    </Marker>
  )
}
