import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader, Provenance } from '../components/ui'
import { BusinessMap } from '../components/BusinessMap'
import { pointsFromGeoJSON } from '../lib/geo'
import type { AnalysisResult, InfrastructurePoint, LocationOut, MapLayersResponse, MapPoint } from '../types'

interface Price {
  item: string
  category?: string
  unit?: string
  min?: number | null
  max?: number | null
  modal?: number | null
  market?: string
  district?: string
  reference?: string | null
  source?: string | null
}

export function Market() {
  const { result, setResult, setForm } = useAnalysis()
  const [prices, setPrices] = useState<Price[]>([])
  const [pricesNote, setPricesNote] = useState('')
  const [markets, setMarkets] = useState<MapPoint[]>([])
  const [infrastructure, setInfrastructure] = useState<InfrastructurePoint[]>([])
  const [layersNote, setLayersNote] = useState('')

  const [demoLoading, setDemoLoading] = useState(false)

  const loadDemo = async () => {
    setDemoLoading(true)
    try {
      const locs = await api.get<LocationOut[]>(
        `/locations/search?q=${encodeURIComponent('Bhavani')}&state=${encodeURIComponent('Tamil Nadu')}&limit=5`,
      )
      const loc = locs[0]
      const payload = {
        state: 'Tamil Nadu',
        district: 'Erode',
        block: loc?.block || 'Erode',
        village: loc?.village || 'Bhavani',
        capital_available: 100000,
        category_code: 'dairy',
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
    api
      .get<{ count: number; note: string; prices: Price[] }>('/market/prices')
      .then((r) => {
        setPrices(r.prices)
        setPricesNote(r.note)
      })
      .catch(() => setPrices([]))
  }, [])

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

  if (!result) return <Empty onLoadDemo={() => loadDemo()} loadingDemo={demoLoading} />
  const bc = result.business_competition

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Market Intelligence</h1>
        <p className="text-sm text-gray-500">Local demand, competition and going prices around your pinned village.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Mini label="Competitors (5 km)" value={bc?.mapped_competitors_5km ?? '-'} />
        <Mini label="Competitors (10 km)" value={bc?.mapped_competitors_10km ?? '-'} />
        <Mini
          label="Nearest competitor"
          value={bc?.nearest_competitor_km != null ? `${bc.nearest_competitor_km} km` : '—'}
          sub={bc?.nearest_competitor}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader title="Live Map of Nearby Businesses" subtitle="Clusters show Mapped businesses; red pins are competitors; orange = markets, purple = other infrastructure." />
            <BusinessMap
              center={{ latitude: result.location.latitude, longitude: result.location.longitude }}
              businesses={bc?.businesses || []}
              competitors={bc?.businesses || []}
              markets={markets}
              infrastructure={infrastructure}
            />
            <p className="mt-2 text-xs text-gray-500">{layersNote || bc?.note || ''}</p>
            <div className="mt-3">
              <Provenance
                source={bc?.data_completeness || 'Mapped via OpenStreetMap'}
                reference="© OpenStreetMap contributors"
                confidence={bc?.note ? 'Partial' : 'High'}
              />
            </div>
          </Card>
        </div>

        <Card>
          <CardHeader title="Nearest Markets" subtitle="Markets/mandis within 20 km" />
          {markets.length === 0 ? (
            <p className="text-sm text-gray-500">No market points mapped around this village yet.</p>
          ) : (
            <ul className="space-y-2">
              {markets.map((m, i) => (
                <li key={i} className="rounded-lg bg-gray-50 p-2 text-sm text-gray-700">
                  {m.name || (m.kind ? `${m.kind} · ` : '') + `Market ${i + 1}`}
                  {m.distance_km != null && <span className="ml-1 text-xs text-gray-400">({m.distance_km} km)</span>}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Sample Going Prices" subtitle={pricesNote} />
        {prices.length === 0 ? (
          <p className="text-sm text-gray-500">No sourced price data available. GramBiz only shows referenced, not invented, prices.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-gray-500">
                  <th className="py-2 pr-4">Item</th>
                  <th className="py-2 pr-4">Unit</th>
                  <th className="py-2 pr-4">Modal (₹)</th>
                  <th className="py-2 pr-4">Range (₹)</th>
                  <th className="py-2 pr-4">Market</th>
                  <th className="py-2">Reference</th>
                </tr>
              </thead>
              <tbody>
                {(prices || []).slice(0, 20).map((p, i) => (
                  <tr key={i} className="border-b border-gray-50">
                    <td className="py-2 pr-4 capitalize">{p.item}</td>
                    <td className="py-2 pr-4">{p.unit || '—'}</td>
                    <td className="py-2 pr-4">{p.modal ?? '—'}</td>
                    <td className="py-2 pr-4">
                      {p.min != null && p.max != null ? `${p.min}–${p.max}` : '—'}
                    </td>
                    <td className="py-2 pr-4">{p.market || '—'}</td>
                    <td className="py-2 text-xs text-gray-400">{p.reference || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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

function Empty({ onLoadDemo, loadingDemo }: { onLoadDemo: () => void; loadingDemo: boolean }) {
  return (
    <div className="py-20 text-center text-gray-500">
      <p>Run an analysis first to see market data.</p>
      <div className="mt-4 flex items-center justify-center gap-3">
        <button
          onClick={onLoadDemo}
          disabled={loadingDemo}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {loadingDemo ? 'Loading demo…' : 'Load demo workspace (Erode, dairy)'}
        </button>
        <a href="/analyze" className="text-sm text-brand-600 underline">
          Analyze now →
        </a>
      </div>
      <p className="mt-3 text-xs text-gray-400">
        One click loads a ready-made demo analysis; you can also build your own on the Analyze page.
      </p>
    </div>
  )
}
