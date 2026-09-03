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

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [nearby, competitorsResp, layers, msme] = await Promise.all([
        api.post<{ businesses: Business[] }>('/businesses/nearby', {
          latitude: center.latitude,
          longitude: center.longitude,
          radius_km: 10,
        }),
        // Wider sweep for the Competitors layer: filtered by the selected
        // category so only relevant competitors appear as red pins on the map.
        api.post<{ businesses: Business[] }>('/businesses/nearby', {
          latitude: center.latitude,
          longitude: center.longitude,
          radius_km: 20,
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
      setBusinesses(nearby.businesses)
      setCompetitors(competitorsResp.businesses)
      setCounts(layers.counts)
      setInfrastructure(pointsFromGeoJSON(layers.layers.infrastructure?.features) as InfrastructurePoint[])
      setMarkets(pointsFromGeoJSON(layers.layers.markets?.features))
      setMsmeClusters(msmeClustersFromGeoJSON(msme.features))
      setMsmeCount(msme.metadata.count)
    } catch (e: any) {
      setError(e.message || tr('couldNotLoad', lang))
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
          <button onClick={load} disabled={loading} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
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