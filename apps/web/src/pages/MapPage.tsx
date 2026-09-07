import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Card } from '../components/ui'
import { BusinessMap } from '../components/BusinessMap'
import { geolocationMessage, getCurrentPosition, isAccurateFix, accuracyKm, msmeClustersFromGeoJSON, pointsFromGeoJSON } from '../lib/geo'
import type { Business, InfrastructurePoint, MapLayersResponse, MapPoint, MSMECluster } from '../types'
import { tr, interpolate } from '../lib/i18n'

export function MapPage() {
  const { result, form, lang } = useAnalysis()
  const [businesses, setBusinesses] = useState<Business[]>([])
  const [competitors, setCompetitors] = useState<Business[]>([])
  const [infrastructure, setInfrastructure] = useState<InfrastructurePoint[]>([])
  const [markets, setMarkets] = useState<MapPoint[]>([])
  const [msmeClusters, setMsmeClusters] = useState<MSMECluster[]>([])
  const [counts, setCounts] = useState<MapLayersResponse['counts'] | null>(null)
  const [msmeCount, setMsmeCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [gpsState, setGpsState] = useState<'idle' | 'locating' | 'detected'>('idle')
  const [gpsError, setGpsError] = useState<string | null>(null)
  const cacheRef = useState(() => new Map<string, any>())[0]

  // The selected business category from the analysis form or result
  const selectedCategory = (form?.category_code as string) || result?.profit_model?.category_code || undefined

  // Keep the chosen/pinned location as the source of truth (primary): this is
  // what demos need, since we present different districts/villages on demand.
  const [center, setCenter] = useState<{ latitude: number; longitude: number }>(() =>
    result
      ? { latitude: result.location.latitude, longitude: result.location.longitude }
      : { latitude: 11.446, longitude: 77.682 },
  )

  // Resync the centre whenever the saved analysis result changes (e.g. the user
  // picks a different village in the Analyze flow and returns to this tab).
  useEffect(() => {
    if (result) setCenter({ latitude: result.location.latitude, longitude: result.location.longitude })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result?.location?.latitude, result?.location?.longitude])

  // GPS is a convenience to jump straight to your current spot, never the
  // default: the selected area stays primary so the project stays easy to demo.
  // We only move the map when the fix is accurate enough — invalid/IP-based
  // fixes (hundreds of km of error) would otherwise jump to the wrong town.
  const useMyLocation = () => {
    setGpsError(null)
    setGpsState('locating')
    getCurrentPosition()
      .then((c) => {
        if (!isAccurateFix(c)) {
          setGpsError(interpolate(tr('gpsTooCoarse', lang), { acc: accuracyKm(c.accuracy) || tr('veryLargeDistance', lang) }))
          return
        }
        setGpsState('detected')
        setCenter({ latitude: c.latitude, longitude: c.longitude })
      })
      .catch((fail: unknown) => {
        setGpsState('idle')
        setGpsError(
          typeof fail === 'object' && fail !== null && 'code' in fail
            ? geolocationMessage(fail as Parameters<typeof geolocationMessage>[0])
            : tr('unableToLocate', lang),
        )
      })
  }

  const load = async (opts?: { force?: boolean }) => {
    const key = `${center.latitude.toFixed(3)}:${center.longitude.toFixed(3)}:${selectedCategory||'all'}`
    const cached = cacheRef.get(key)
    if (cached && !opts?.force) {
      setBusinesses(cached.businesses); setCompetitors(cached.competitors); setCounts(cached.counts)
      setInfrastructure(cached.infrastructure); setMarkets(cached.markets); setMsmeClusters(cached.msmeClusters); setMsmeCount(cached.msmeCount)
      // Serve instantly from cache — still refresh in background without blocking
      setLoading(false)
      // Background refresh (no spinner) if cache exists
      try {
        const layers = await api.post<MapLayersResponse>('/geojson/layers', {
          latitude: center.latitude,
          longitude: center.longitude,
          radius_km: 10,
        })
        const infra = pointsFromGeoJSON(layers.layers.infrastructure?.features) as InfrastructurePoint[]
        const mkts = pointsFromGeoJSON(layers.layers.markets?.features)
        // Derive businesses directly from layers to avoid a duplicate /nearby call
        const layerBusinesses = (layers.layers.businesses?.features || []).map((f: any) => ({
          id: f.properties?.id || f.properties?.name,
          name: f.properties?.name,
          category_code: f.properties?.category,
          latitude: f.geometry.coordinates[1],
          longitude: f.geometry.coordinates[0],
          address: f.properties?.address,
          distance_km: f.properties?.distance_km,
          source_name: f.properties?.source,
          metadata: f.properties,
        })) as Business[]
        setCounts(layers.counts)
        setInfrastructure(infra)
        setMarkets(mkts)
        if (layerBusinesses.length) setBusinesses(layerBusinesses)
        cacheRef.set(key, { ...cached, businesses: layerBusinesses.length ? layerBusinesses : cached.businesses, counts: layers.counts, infrastructure: infra, markets: mkts })
      } catch { /* background refresh failures are silent when cache exists */ }
      return
    }
    setLoading(true)
    setError(null)
    try {
      // Optimized: /geojson/layers already returns businesses+infra+markets in one
      // call — run it in parallel with the category-filtered competitors and MSME
      // clusters. This cuts 4 calls → 3 and avoids the duplicate businesses fetch.
      const [competitorsResp, layers, msme] = await Promise.all([
        api.post<{ businesses: Business[] }>('/businesses/nearby', {
          latitude: center.latitude,
          longitude: center.longitude,
          radius_km: 10,
          category_code: selectedCategory || undefined,
        }),
        api.post<MapLayersResponse>('/geojson/layers', {
          latitude: center.latitude,
          longitude: center.longitude,
          radius_km: 10,
        }),
        api.post<{ features: any[]; metadata: { count: number } }>('/businesses/msme-clusters', {
          latitude: center.latitude,
          longitude: center.longitude,
          radius_km: 10,
          include_units: true,
        }),
      ])
      const infra = pointsFromGeoJSON(layers.layers.infrastructure?.features) as InfrastructurePoint[]
      const mkts = pointsFromGeoJSON(layers.layers.markets?.features)
      const msmes = msmeClustersFromGeoJSON(msme.features)
      const layerBusinesses = (layers.layers.businesses?.features || []).map((f: any) => ({
        id: f.properties?.id || f.properties?.name,
        name: f.properties?.name,
        category_code: f.properties?.category,
        latitude: f.geometry.coordinates[1],
        longitude: f.geometry.coordinates[0],
        address: f.properties?.address,
        distance_km: f.properties?.distance_km,
        source_name: f.properties?.source,
        metadata: f.properties,
      })) as Business[]
      const allBusinesses = layerBusinesses.length ? layerBusinesses : competitorsResp.businesses
      setBusinesses(allBusinesses)
      setCompetitors(competitorsResp.businesses)
      setCounts(layers.counts)
      setInfrastructure(infra)
      setMarkets(mkts)
      setMsmeClusters(msmes)
      setMsmeCount(msme.metadata.count)
      cacheRef.set(key, { businesses: allBusinesses, competitors: competitorsResp.businesses, counts: layers.counts, infrastructure: infra, markets: mkts, msmeClusters: msmes, msmeCount: msme.metadata.count })
    } catch (e: any) {
      if (!cached) setError(e.message || tr('couldNotLoad', lang))
    } finally {
      setLoading(false)
    }
  }

  // Reload whenever the centre changes (picked village or GPS jump), so the map
  // always reflects the currently selected area instead of a stale first load.
  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center.latitude, center.longitude])

  const locationLabel = result
    ? `${result.location.village || result.location.block}, ${result.location.district}`
    : tr('selectedArea', lang)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{tr('liveBusinessMap', lang)}</h1>
          <p className="text-sm text-gray-500">
            {locationLabel} ·{' '}
            {selectedCategory ? `${tr('categoryPrefix', lang)} ${selectedCategory} · ` : ''}
            {counts
              ? `${interpolate(tr('businessesMarketsInfra', lang), {
                  b: counts.businesses,
                  m: counts.markets,
                  i: counts.infrastructure,
                })}${msmeCount != null ? ` · ${interpolate(tr('msmeClusters', lang), { n: msmeCount })}` : ''} ${tr('within10km', lang)}`
              : interpolate(tr('mappedWithin10', lang), { n: businesses.length })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={useMyLocation}
            disabled={gpsState === 'locating'}
            className="rounded-lg border border-brand-600 px-4 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-60"
          >
            {gpsState === 'locating' ? tr('locating', lang) : gpsState === 'detected' ? tr('gpsCurrentLocation', lang) : tr('useMyLocation', lang)}
          </button>
          <button onClick={() => load({ force: true })} disabled={loading} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
            {loading ? tr('loading', lang) : tr('refresh', lang)}
          </button>
        </div>
      </div>

      {gpsError && <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">{gpsError}</div>}

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <Card className="p-0 overflow-hidden">
        <div style={{ height: '68vh', width: '100%' }}>
          <BusinessMap center={center} businesses={businesses} competitors={competitors} markets={markets} infrastructure={infrastructure} msmeClusters={msmeClusters} zoom={12} height="100%" selectedCategory={selectedCategory} />
        </div>
      </Card>
    </div>
  )
}