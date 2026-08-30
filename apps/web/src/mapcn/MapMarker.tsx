import L from 'leaflet'
import { Marker, Tooltip, Popup } from 'react-leaflet'

export interface MarkerProps {
  latitude: number
  longitude: number
  color?: string
  label?: string
  popup?: string
  onClick?: () => void
}

function pinIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: 'mapcn-pin',
    html: `<div style="width:18px;height:18px;border-radius:50% 50% 50% 0;background:${color};border:2px solid #fff;transform:rotate(-45deg);box-shadow:0 1px 4px rgba(0,0,0,0.35);"></div>`,
    iconSize: [18, 18],
    iconAnchor: [10, 16],
    popupAnchor: [0, -16],
  })
}

/**
 * MapCN <MapMarker> — a Leaflet DOM marker for a point with optional label
 * tooltip and plain-text popup.
 */
export function MapMarker({ latitude, longitude, color = '#16a34a', label, popup, onClick }: MarkerProps) {
  const icon = pinIcon(color)
  return (
    <Marker
      position={[latitude, longitude]}
      icon={icon}
      eventHandlers={onClick ? { click: onClick } : undefined}
      title={label || ''}
    >
      {label && (
        <Tooltip direction="top" offset={[0, -18]}>
          {label}
        </Tooltip>
      )}
      {popup && <Popup offset={[0, -16]}>{popup}</Popup>}
    </Marker>
  )
}
