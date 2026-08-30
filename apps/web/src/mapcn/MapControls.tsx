import { useEffect } from 'react'
import { ZoomControl, useMap } from 'react-leaflet'
import L from 'leaflet'

const LocateBtn = L.Control.extend({
  onAdd(map: L.Map) {
    const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control')
    const link = L.DomUtil.create('a', 'mapcn-locate', container)
    link.href = '#'
    link.title = 'Locate me'
    link.setAttribute('role', 'button')
    link.innerHTML = '◎'
    link.addEventListener('click', (e) => {
      e.preventDefault()
      e.stopPropagation()
      map.locate({ setView: true, maxZoom: 14 })
    })
    L.DomEvent.disableClickPropagation(container)
    return container
  },
})

function LocateControl() {
  const map = useMap()
  useEffect(() => {
    const control = new LocateBtn({ position: 'topright' })
    control.addTo(map)
    return () => {
      control.remove()
    }
  }, [map])
  return null
}

/**
 * MapCN <MapControls> — Leaflet navigation + geolocate controls.
 */
export function MapControls({ navigation = true, geolocate = false }: { navigation?: boolean; geolocate?: boolean }) {
  return (
    <>
      {navigation && <ZoomControl position="topright" />}
      {geolocate && <LocateControl />}
    </>
  )
}
