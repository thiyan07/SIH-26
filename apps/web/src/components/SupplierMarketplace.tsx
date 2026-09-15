import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { tr, interpolate } from '../lib/i18n'
import { useAnalysis } from '../lib/analysisStore'

interface SupplierMarketplaceProps {
  latitude?: number | null
  longitude?: number | null
  category?: string | null
  placeName?: string | null
  district?: string | null
}

interface Supplier {
  id: string
  name: string
  category_code?: string
  subcategory?: string
  latitude?: number | null
  longitude?: number | null
  address?: string
  phone?: string | null
  website?: string | null
  distance_km?: number | null
  source_name?: string
  source_type?: string
  confidence?: string
  retrieved_at_date?: string | null
  is_scraped?: boolean
  is_fresh?: boolean
  years_in_business?: string | null
  source_url?: string
}

interface SupplierResponse {
  category_code: string
  district: string
  place_name?: string
  count: number
  scraped_count: number
  db_count: number
  suppliers: Supplier[]
  provenance?: {
    scraped_source?: string
    scraped_retrieved_at?: string
    note?: string
  }
}

export function SupplierMarketplace({ latitude, longitude, category, placeName, district }: SupplierMarketplaceProps) {
  const { lang } = useAnalysis() as any
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [meta, setMeta] = useState<SupplierResponse | null>(null)

  useEffect(() => {
    if (!latitude || !longitude || !category) {
      setSuppliers([])
      setMeta(null)
      return
    }
    setLoading(true)
    setError(null)
    api
      .post<SupplierResponse>('/suppliers/search', {
        latitude,
        longitude,
        category_code: category,
        district: district || placeName?.split(',').pop()?.trim() || 'Erode',
        place_name: placeName || undefined,
        radius_km: 10,
        limit: 8,
      })
      .then((res) => {
        setSuppliers(res.suppliers || [])
        setMeta(res)
      })
      .catch((e: any) => {
        setError(e.message || 'Could not load suppliers')
        setSuppliers([])
      })
      .finally(() => setLoading(false))
  }, [latitude, longitude, category, district, placeName])

  const titlePlace = placeName ? ` • ${placeName}` : ''
  const titleCat = category ? ` • ${category}` : ''

  if (!latitude || !longitude || !category) {
    return (
      <div data-testid="supplier-marketplace" className="space-y-3">
        <div className="text-sm font-bold text-slate-900 dark:text-white">
          {tr('supplierTitleSelect', lang)}
        </div>
        <p className="text-xs text-slate-500">
          {tr('supplierChooseVillage', lang)}
        </p>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-center text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800">
          {tr('supplierNoLocation', lang)}
        </div>
      </div>
    )
  }

  return (
    <div data-testid="supplier-marketplace" className="space-y-3">
      <div className="text-sm font-bold text-slate-900 dark:text-white">
        {tr('supplierMarketplaceTitle', lang)} • {loading ? tr('supplierLoading', lang) : interpolate(tr('supplierNearYou', lang), {count: suppliers.length})}
        <span className="ml-1 text-xs font-normal text-slate-500">
          {titleCat}
          {titlePlace} · 10km
        </span>
        {meta && !loading && (
          <span className="ml-2 text-[10px] font-normal text-emerald-600">
            {interpolate(tr('supplierScrapedVerified', lang), {scraped: meta.scraped_count, db: meta.db_count})}
          </span>
        )}
      </div>

      {loading && <p className="text-xs text-slate-500">{interpolate(tr('supplierSearching', lang), {category: category || '', place: placeName || 'your pin'})}</p>}
      {error && <p className="text-xs text-amber-600">{error}</p>}

      {!loading && suppliers.length === 0 && !error && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {interpolate(tr('supplierNoVerified', lang), {category: category || '', place: placeName || 'this location'})}
        </div>
      )}

      {!loading && suppliers.length > 0 && (
        <div className="grid gap-2 md:grid-cols-2">
          {suppliers.map((s) => (
            <div
              key={s.id}
              className="flex items-start justify-between rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-slate-900 dark:text-white">{s.name}</div>
                <div className="truncate text-xs text-slate-500">
                  {s.address ? `${s.address.slice(0, 60)}` : s.subcategory || s.category_code || ''}
                  {s.distance_km != null ? ` • ${s.distance_km} km` : ''}
                  {s.years_in_business ? ` • ${s.years_in_business}` : ''}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${s.is_scraped ? 'bg-blue-100 text-blue-700' : 'bg-emerald-100 text-emerald-700'}`}>
                    {s.source_name || (s.is_scraped ? 'ExportersIndia' : 'Google Maps')}
                  </span>
                  {s.is_fresh && <span className="rounded-full bg-green-50 px-2 py-0.5 text-[10px] text-green-700">{tr('supplierFresh', lang)} {s.retrieved_at_date ? `• ${s.retrieved_at_date}` : ''}</span>}
                  {!s.is_fresh && s.retrieved_at_date && <span className="text-[10px] text-slate-400">{s.retrieved_at_date}</span>}
                </div>
                {s.website || (s as any).source_url ? (
                  <a href={s.website || (s as any).source_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[11px] text-blue-600 underline">
                    {interpolate(tr('supplierViewOn', lang), {source: s.source_name || 'site'})}
                  </a>
                ) : null}
              </div>
              <div className="ml-2 flex shrink-0 flex-col items-end gap-1">
                {s.phone ? (
                  <a
                    href={`https://wa.me/91${s.phone.replace(/\s/g, '')}`}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={`supplier-wa-${s.name}`}
                    className="rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-700"
                  >
                    WhatsApp
                  </a>
                ) : s.website || (s as any).source_url ? (
                  <a
                    href={s.website || (s as any).source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-xl bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-700"
                  >
                    {tr('supplierInquiry', lang)}
                  </a>
                ) : (
                  <span className="rounded-xl bg-slate-200 px-3 py-1.5 text-xs font-bold text-slate-500">{tr('supplierNoContact', lang)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-[11px] text-slate-500">
        {interpolate(tr('supplierLiveVia', lang), {category: category || '', place: placeName || `${latitude?.toFixed(4)}, ${longitude?.toFixed(4)}`})} {suppliers.length > 0 ? interpolate(tr('supplierFooterFound', lang), {count: suppliers.length}) : tr('supplierFooterNone', lang)}
        {meta?.provenance?.note && <span className="ml-1 italic">{meta.provenance.note}</span>}
      </p>
    </div>
  )
}
