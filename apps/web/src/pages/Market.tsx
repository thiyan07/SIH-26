import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader, Provenance } from '../components/ui'
import { BusinessMap } from '../components/BusinessMap'
import { pointsFromGeoJSON } from '../lib/geo'
import { tr, type Language } from '../lib/i18n'
import { SupplierMarketplace } from '../components/SupplierMarketplace'
import type { AnalysisResult, InfrastructurePoint, LocationOut, MapLayersResponse, MapPoint } from '../types'

export function Market() {
  const { result, setResult, setForm, lang } = useAnalysis()
  const [markets, setMarkets] = useState<MapPoint[]>([])
  const [infrastructure, setInfrastructure] = useState<InfrastructurePoint[]>([])
  const [layersNote, setLayersNote] = useState('')
  const [demoLoading, setDemoLoading] = useState(false)

  const loadDemo = async () => {
    setDemoLoading(true)
    try {
      const locs = await api.get<LocationOut[]>(
        `/locations/search?q=${encodeURIComponent('Perundurai')}&state=${encodeURIComponent('Tamil Nadu')}&limit=5`,
      )
      const loc = locs[0]
      const payload = {
        state: 'Tamil Nadu',
        district: 'Erode',
        block: loc?.block || 'Erode',
        village: loc?.village || 'Perundurai',
        capital_available: 100000,
        category_code: 'restaurant',
        business_experience: false,
        existing_shop: false,
        existing_equipment: false,
        family_members: 3,
      }
      setForm(payload)
      const res = await api.post<AnalysisResult>('/analysis', payload)
      setResult(res)
    } catch {
      /* ignore — the Empty state error handling covers messaging */
    } finally {
      setDemoLoading(false)
    }
  }

  useEffect(() => {
    if (!result) return
    api
      .post<MapLayersResponse>('/geojson/layers', {
        latitude: result.location.latitude,
        longitude: result.location.longitude,
        radius_km: 20,
      })
      .then((r) => {
        setMarkets(pointsFromGeoJSON(r.layers.markets?.features))
        setInfrastructure(pointsFromGeoJSON(r.layers.infrastructure?.features) as InfrastructurePoint[])
        setLayersNote(r.note || '')
      })
      .catch(() => {
        setMarkets([])
        setInfrastructure([])
      })
  }, [result])

  if (!result) return <Empty lang={lang} onLoadDemo={() => loadDemo()} loadingDemo={demoLoading} />
  const bc = result.business_competition

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{tr('marketIntelligence', lang)}</h1>
        <p className="text-sm text-gray-500">{tr('marketIntelligenceSub', lang)}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Mini label={tr('competitors5km', lang)} value={bc?.mapped_competitors_5km ?? '-'} />
        <Mini label={tr('competitors5to10km', lang)} value={bc?.mapped_competitors_5km != null && bc?.mapped_competitors_10km != null ? bc.mapped_competitors_10km - bc.mapped_competitors_5km : '-'} sub={tr('additionalInRing', lang)} />
        <Mini label={tr('competitors10km', lang)} value={bc?.mapped_competitors_10km ?? '-'} />
        <Mini
          label={tr('nearestCompetitor', lang)}
          value={bc?.nearest_competitor_km != null ? `${bc.nearest_competitor_km} ${tr('km', lang)}` : '—'}
          sub={bc?.nearest_competitor}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader title={tr('liveMapNearby', lang)} subtitle={tr('liveMapSub', lang)} />
            <BusinessMap
              center={{ latitude: result.location.latitude, longitude: result.location.longitude }}
              businesses={bc?.businesses || []}
              competitors={bc?.businesses || []}
              markets={markets}
              infrastructure={infrastructure}
              selectedCategory={result.profit_model?.category_code}
            />
            <p className="mt-2 text-xs text-gray-500">{layersNote || bc?.note || ''}</p>
            <div className="mt-3">
              <Provenance
                source={bc?.data_completeness || tr('mappedViaOSM', lang)}
                reference="© OpenStreetMap contributors"
                confidence={bc?.note ? tr('confidencePartial', lang) : tr('confidenceHigh', lang)}
              />
            </div>
          </Card>
        </div>

        <Card>
          <CardHeader title={tr('nearestMarkets', lang)} subtitle={tr('nearestMarketsSub', lang)} />
          {markets.length === 0 ? (
            <p className="text-sm text-gray-500">{tr('noMarketPoints', lang)}</p>
          ) : (
            <ul className="space-y-2">
              {markets.map((m, i) => (
                <li key={i} className="rounded-lg bg-gray-50 p-2 text-sm text-gray-700">
                  {m.name || (m.kind ? `${m.kind} · ` : '') + `${tr('marketLabel', lang)} ${i + 1}`}
                  {m.distance_km != null && <span className="ml-1 text-xs text-gray-500">({m.distance_km} {tr('km', lang)})</span>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Supplier Marketplace" subtitle="Trusted suppliers near your village — WhatsApp to order" />
        <SupplierMarketplace />
      </Card>

      {/* Market prices are available via Market Intelligence API and used for demand/seasonality — detailed price table removed per product scope */}
    </div>
  )
}

function Mini({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {sub && <div className="truncate text-xs text-gray-500">{sub}</div>}
    </Card>
  )
}

function Empty({ lang, onLoadDemo, loadingDemo }: { lang: Language; onLoadDemo: () => void; loadingDemo: boolean }) {
  return (
    <div className="py-20 text-center text-gray-500">
      <p>{tr('runAnalysisMarket', lang)}</p>
      <div className="mt-4 flex items-center justify-center gap-3">
        <button
          onClick={onLoadDemo}
          disabled={loadingDemo}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {loadingDemo ? tr('loadingDemo', lang) : tr('loadDemoWorkspace', lang)}
        </button>
        <a href="/analyze" className="text-sm text-brand-600 underline">
          {tr('analyzeNow', lang)}
        </a>
      </div>
      <p className="mt-3 text-xs text-gray-500">
        {tr('marketOneClickNote', lang)}
      </p>
    </div>
  )
}
