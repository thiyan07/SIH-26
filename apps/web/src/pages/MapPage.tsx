import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Card } from '../components/ui'
import { BusinessMap } from '../components/BusinessMap'
import { pointsFromGeoJSON } from '../lib/geo'
import type { Business, InfrastructurePoint, MapLayersResponse, MapPoint } from '../types'

export function MapPage() {
  const { result } = useAnalysis()
  const [businesses, setBusinesses] = useState<Business[]>([])
  const [infrastructure, setInfrastructure] = useState<InfrastructurePoint[]>([])
  const [markets, setMarkets] = useState<MapPoint[]>([])
  const [counts, setCounts] = useState<MapLayersResponse['counts'] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const center = result
    ? { latitude: result.location.latitude, longitude: result.location.longitude }
    : { latitude: 11.446, longitude: 77.682 }

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [nearby, layers] = await Promise.all([
        api.post<{ businesses: Business[] }>('/businesses/nearby', {
          latitude: center.latitude,
          longitude: center.longitude,
          radius_km: 10,
        }),
        api.post<MapLayersResponse>('/geojson/layers', {
          latitude: center.latitude,
          longitude: center.longitude,
          radius_km: 10,
        }),
      ])
      setBusinesses(nearby.businesses)
      setCounts(layers.counts)
      setInfrastructure(pointsFromGeoJSON(layers.layers.infrastructure?.features) as InfrastructurePoint[])
      setMarkets(pointsFromGeoJSON(layers.layers.markets?.features))
    } catch (e: any) {
      setError(e.message || 'Could not load businesses')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Live Business Map</h1>
          <p className="text-sm text-gray-500">
            {result ? `${result.location.village || result.location.block}, ${result.location.district}` : 'Demo workspace (Erode)'} ·{' '}
            {counts
              ? `${counts.businesses} businesses · ${counts.markets} markets · ${counts.infrastructure} infra points within 10 km`
              : `${businesses.length} mapped within 10 km`}
          </p>
        </div>
        <button onClick={load} disabled={loading} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <Card className="p-0 overflow-hidden">
        <div style={{ height: '68vh', width: '100%' }}>
          <BusinessMap center={center} businesses={businesses} markets={markets} infrastructure={infrastructure} zoom={12} height="100%" />
        </div>
      </Card>
    </div>
  )
}