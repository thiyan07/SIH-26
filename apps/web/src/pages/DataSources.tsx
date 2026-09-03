import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card, Badge, Disclaimer } from '../components/ui'
import { useAnalysis } from '../lib/analysisStore'
import { tr, interpolate, dict, type Language } from '../lib/i18n'

interface Source {
  key: string
  display_name: string
  category: string
  dataset_name?: string
  source_url?: string
  publisher?: string
  reference_year?: number
  reference_date?: string | null
  retrieved_at?: string | null
  geographic_level?: string
  confidence?: string
  license_note?: string
  is_demo?: boolean
  is_estimate?: boolean
  record_count?: number
  freshness_note?: string
  why_used?: string
  known_limitations?: string[]
}

interface SourceStatus {
  key: string
  status: string
  freshness: string
  last_updated?: string | null
  reference_date?: string | null
  reference_year?: number
  record_count?: number
  is_demo?: boolean
  freshness_note?: string
}

interface Provider {
  key: string
  name: string
  state: 'ready' | 'config_missing' | 'no_rows'
  rows_in_db: number
  refresh_cadence?: string
  is_historical?: boolean
  missing_keys?: string[]
  note?: string
}

const CATEGORY_KEY: Record<string, keyof typeof import('../lib/i18n')['dict']> = {
  demographic: 'categoryDemo',
  competition: 'categoryCompetition',
  infrastructure: 'categoryInfrastructure',
  weather: 'categoryWeather',
  market_prices: 'categoryMarketPrices',
  social: 'categorySocial',
  financial: 'categoryFinancial',
  other: 'categoryOther',
}

const FRESHNESS_COLOR: Record<string, string> = {
  fresh: 'green',
  recent: 'blue',
  aging: 'amber',
  old: 'gray',
  unknown: 'gray',
}

const STATUS_COLOR: Record<string, string> = {
  operational: 'green',
  no_rows: 'gray',
  unavailable: 'red',
  historical: 'blue',
  demo: 'amber',
  disabled: 'gray',
}

const PROVIDER_STATE: Record<string, { key: keyof typeof import('../lib/i18n')['dict']; color: string }> = {
  ready: { key: 'providerReady', color: 'green' },
  config_missing: { key: 'providerKeyRequired', color: 'amber' },
  no_rows: { key: 'providerNoRows', color: 'gray' },
}

function categoryLabel(cat: string, lang: Language): string {
  const k = CATEGORY_KEY[cat]
  return k ? tr(k, lang) : cat
}

export function DataSources() {
  const [sources, setSources] = useState<Source[]>([])
  const [statusMap, setStatusMap] = useState<Record<string, SourceStatus>>({})
  const [providers, setProviders] = useState<Provider[]>([])
  const [note, setNote] = useState('')
  const [filter, setFilter] = useState('all')
  const lang = useLanguage()

  useEffect(() => {
    api
      .get<{ note: string; sources: Source[] }>('/data-sources')
      .then((r) => {
        setSources(r.sources)
        setNote(r.note)
      })
      .catch(() => setSources([]))
    Promise.all([
      api.get<{ sources: SourceStatus[] }>('/data-sources/status'),
      api.get<{ providers: Provider[] }>('/data-sources/providers'),
    ])
      .then(([st, pv]) => {
        setStatusMap(Object.fromEntries(st.sources.map((s) => [s.key, s])))
        setProviders(pv.providers)
      })
      .catch(() => undefined)
  }, [])

  const cats = Array.from(new Set(sources.map((s) => s.category)))
  const shown = filter === 'all' ? sources : sources.filter((s) => s.category === filter)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{tr('dataSourcesTitle', lang)}</h1>
        <p className="text-sm text-gray-500">{note}</p>
      </div>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">{tr('liveProviderHealth', lang)}</h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {providers.map((p) => {
            const st = PROVIDER_STATE[p.state]
            return (
              <div key={p.key} className="rounded-lg border border-gray-200 bg-white p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="text-sm font-medium text-gray-900">{p.name}</div>
                  <Badge color={st.color}>{tr(st.key, lang)}</Badge>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-gray-500">
                  <Badge color="gray">{p.rows_in_db} {tr('rowsBadge', lang)}</Badge>
                  {p.refresh_cadence && <Badge color="gray">{p.refresh_cadence}</Badge>}
                  {p.is_historical && <Badge color="blue">{tr('historical', lang)}</Badge>}
                </div>
                {p.missing_keys && p.missing_keys.length > 0 && (
                  <p className="mt-1 text-[11px] text-amber-700">
                    {interpolate(tr('setMissingEnv', lang), { keys: p.missing_keys.join(', ') })}
                  </p>
                )}
                {p.note && <p className="mt-1 text-[11px] text-gray-400">{p.note}</p>}
              </div>
            )
          })}
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        <FilterBtn active={filter === 'all'} onClick={() => setFilter('all')} label={tr('all', lang)} />
        {cats.map((c) => (
          <FilterBtn key={c} active={filter === c} onClick={() => setFilter(c)} label={categoryLabel(c, lang)} />
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((s) => {
          const st = statusMap[s.key]
          return (
            <Card key={s.key} className="flex flex-col">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div className="font-semibold text-gray-900">{s.display_name}</div>
                {s.is_demo ? <Badge color="amber">{tr('demo', lang)}</Badge> : <Badge color="green">{tr('live', lang)}</Badge>}
              </div>
              <div className="mb-3 flex flex-wrap gap-1 text-[11px]">
                <Badge color="blue">{categoryLabel(s.category, lang)}</Badge>
                {s.is_estimate && <Badge color="gray">{tr('estimate', lang)}</Badge>}
                {st && (
                  <>
                    <Badge color={FRESHNESS_COLOR[st.freshness] || 'gray'}>{tr(freshnessKey(st.freshness), lang)}</Badge>
                    <Badge color={STATUS_COLOR[st.status] || 'gray'}>{tr(statusKey(st.status), lang)}</Badge>
                  </>
                )}
              </div>
              <dl className="flex-1 space-y-1 text-xs text-gray-600">
                <Row k={tr('publisher', lang)} v={s.publisher} />
                <Row k={tr('dataset', lang)} v={s.dataset_name} />
                <Row k={tr('level', lang)} v={s.geographic_level} />
                <Row k={tr('reference', lang)} v={s.reference_year ? String(s.reference_year) : s.reference_date?.slice(0, 10)} />
                <Row k={tr('updated', lang)} v={st?.last_updated?.slice(0, 10) || s.retrieved_at?.slice(0, 10)} />
                <Row k={tr('confidence', lang)} v={s.confidence} />
                <Row k={tr('records', lang)} v={s.record_count != null ? String(s.record_count) : undefined} />
              </dl>
              {s.freshness_note && <p className="mt-2 text-[11px] italic text-gray-400">{s.freshness_note}</p>}
              {s.why_used && (
                <p className="mt-2 text-xs text-gray-600">
                  <span className="font-medium text-gray-500">{tr('whyWeUseThis', lang)}</span> {s.why_used}
                </p>
              )}
              {s.known_limitations && s.known_limitations.length > 0 && (
                <div className="mt-2 text-[11px] text-amber-700">
                  <div className="font-medium text-gray-500">{tr('knownLimitations', lang)}</div>
                  <ul className="mt-1 list-disc pl-4">
                    {s.known_limitations.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}
              {s.source_url && (
                <a href={s.source_url} target="_blank" rel="noreferrer" className="mt-2 text-xs font-medium text-brand-600 hover:underline">
                  {tr('viewSource', lang)}
                </a>
              )}
            </Card>
          )
        })}
      </div>

      <Disclaimer>{tr('dataSourcesDisclaimer', lang)}</Disclaimer>
    </div>
  )
}

function freshnessKey(f: string): keyof typeof dict {
  const map: Record<string, keyof typeof dict> = {
    fresh: 'freshnessFresh',
    recent: 'freshnessRecent',
    aging: 'freshnessAging',
    old: 'freshnessOld',
    unknown: 'freshnessOld',
  }
  return map[f] || 'freshnessOld'
}

function statusKey(s: string): keyof typeof dict {
  const map: Record<string, keyof typeof dict> = {
    operational: 'statusOperational',
    no_rows: 'statusNoRows',
    unavailable: 'statusUnavailable',
    historical: 'statusHistorical',
    demo: 'statusDemo',
    disabled: 'statusDisabled',
  }
  return map[s] || ('statusUnknown' as keyof typeof dict)
}

function useLanguage(): Language {
  const { lang } = useAnalysis()
  return lang
}

function FilterBtn({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1 text-xs font-medium ${
        active ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
    >
      {label}
    </button>
  )
}

function Row({ k, v }: { k: string; v?: string | null }) {
  if (!v) return null
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-gray-400">{k}</dt>
      <dd className="text-right font-medium text-gray-700">{v}</dd>
    </div>
  )
}