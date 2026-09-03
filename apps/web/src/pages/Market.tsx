import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader, Provenance } from '../components/ui'
import { BusinessMap } from '../components/BusinessMap'
import { pointsFromGeoJSON } from '../lib/geo'
import { interpolate, tr, type Language } from '../lib/i18n'
import type { AnalysisResult, InfrastructurePoint, LocationOut, MapLayersResponse, MapPoint, MarketIntelligenceResponse } from '../types'

const BUSINESS_CATEGORY_LABEL: Record<string, keyof typeof import('../lib/i18n')['dict']> = {
  restaurant: 'categoryRestaurant',
  grocery: 'categoryGrocery',
  vegetable_shop: 'categoryVegetableShop',
  fruit_shop: 'categoryFruitShop',
  dairy: 'categoryDairy',
  bakery: 'categoryBakery',
  meat_shop: 'categoryMeatShop',
  fish_shop: 'categoryFishShop',
  food_processing: 'categoryFoodProcessing',
  agriculture: 'categoryAgriculture',
  poultry: 'categoryPoultry',
  sweet_shop: 'categorySweetShop',
  textile: 'categoryTextile',
  pharmacy: 'categoryPharmacy',
  salon: 'categorySalon',
  other: 'categoryOther',
}

export function businessCategoryName(code: string | undefined, lang: Language): string {
  if (!code) return '—'
  const k = BUSINESS_CATEGORY_LABEL[code]
  return k ? tr(k, lang) : code
}

export function Market() {
  const { result, setResult, setForm, lang } = useAnalysis()
  const [markets, setMarkets] = useState<MapPoint[]>([])
  const [infrastructure, setInfrastructure] = useState<InfrastructurePoint[]>([])
  const [layersNote, setLayersNote] = useState('')

  const [mi, setMi] = useState<MarketIntelligenceResponse | null>(null)
  const [miLoading, setMiLoading] = useState(false)
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
    if (!result) {
      setMi(null)
      return
    }
    const category = result.profit_model?.category_code
    const loc = result.location
    setMiLoading(true)
    api
      .post<MarketIntelligenceResponse>('/market/intelligence', {
        category_code: category || 'other',
        state: loc.state,
        district: loc.district,
        latitude: loc.latitude,
        longitude: loc.longitude,
        radius_km: 10,
        max_age_days: 90,
      })
      .then(setMi)
      .catch(() => setMi(null))
      .finally(() => setMiLoading(false))
  }, [result])

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
  const categoryLabel = businessCategoryName(result.profit_model?.category_code, lang)

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
                  {m.distance_km != null && <span className="ml-1 text-xs text-gray-400">({m.distance_km} {tr('km', lang)})</span>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Category-aware verified prices + evidence */}
      <Card>
        <CardHeader
          title={tr('relevantPrices', lang)}
          subtitle={interpolate(tr('relevantPricesSub', lang), { category: categoryLabel || '—', district: result.location.district })}
        />
        {miLoading ? (
          <p className="text-sm text-gray-500">{tr('loadingDemo', lang)}</p>
        ) : !mi || !mi.available || mi.prices.length === 0 ? (
          <div className="text-sm text-gray-500">
            <p>{tr('noRelevantPrices', lang)}</p>
            {mi?.availability_note && <p className="mt-1 text-xs text-gray-400">{mi.availability_note}</p>}
          </div>
        ) : (
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-4">
              <span className="text-sm text-gray-600">
                {tr('confidence', lang)}:{' '}
                <b className="capitalize">{mi.confidence?.label}</b>{' '}
                <span className="text-xs text-gray-400">({mi.confidence?.score ?? 0}%)</span>
              </span>
              <span className="text-xs text-gray-400">
                {Math.round((mi.coverage ?? 0) * 100)}% {tr('ofRelevantCommodities', lang)}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-gray-500">
                    <th className="py-2 pr-4">{tr('item', lang)}</th>
                    <th className="py-2 pr-4">{tr('unit', lang)}</th>
                    <th className="py-2 pr-4">{tr('modal', lang)}</th>
                    <th className="py-2 pr-4">{tr('range', lang)}</th>
                    <th className="py-2 pr-4">{tr('marketLabel', lang)}</th>
                    <th className="py-2 pr-4">{tr('reference', lang)}</th>
                    <th className="py-2">{tr('freshness', lang)}</th>
                  </tr>
                </thead>
                <tbody>
                  {mi.prices.slice(0, 25).map((p, i) => (
                    <tr key={i} className="border-b border-gray-50">
                      <td className="py-2 pr-4 capitalize">{p.item}</td>
                      <td className="py-2 pr-4">{p.unit || '—'}</td>
                      <td className="py-2 pr-4">{p.modal ?? '—'}</td>
                      <td className="py-2 pr-4">
                        {p.min != null && p.max != null ? `${p.min}–${p.max}` : '—'}
                      </td>
                      <td className="py-2 pr-4">{p.market || p.mandi || '—'}</td>
                      <td className="py-2 pr-4 text-xs text-gray-400">{p.reference_date || '—'}</td>
                      <td className="py-2 text-xs capitalize text-gray-500">{p.freshness || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {mi.source_hierarchy && mi.source_hierarchy.length > 0 && (
              <div className="mt-4">
                <div className="mb-1 text-sm font-semibold text-gray-700">{tr('sourceHierarchy', lang)}</div>
                <p className="mb-2 text-xs text-gray-500">{tr('sourcesRanked', lang)}</p>
                <ul className="space-y-1">
                  {mi.source_hierarchy.map((s, i) => (
                    <li key={i} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-1.5 text-xs text-gray-600">
                      <span className="font-medium">{s.source_name}</span>
                      <span className="text-gray-400">
                        {s.items} {tr('item', lang).toLowerCase()} · {s.source_type || '—'}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {mi.notes && mi.notes.length > 0 && (
              <p className="mt-3 text-xs text-gray-400">{mi.notes.join(' ')}</p>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}

function Mini({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <Card>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {sub && <div className="truncate text-xs text-gray-400">{sub}</div>}
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
      <p className="mt-3 text-xs text-gray-400">
        {tr('marketOneClickNote', lang)}
      </p>
    </div>
  )
}
