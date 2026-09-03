import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Button, Card, CardHeader } from '../components/ui'
import { ShopLocationPicker } from '../components/ShopLocationPicker'
import { tr, interpolate, type Language } from '../lib/i18n'
import type { AnalysisResult, Category, LocationOut, AdvisoryParseOutput, AdvisoryReport } from '../types'

interface DiscoveryResult {
  data_status: string
  search_radius_m?: number
  data?: {
    primary_source?: string
    freshness?: string
    note?: string
    retrieved_at?: string
  }
  confidence?: { score: number; label: string }
  competitors?: {
    total_mapped?: number
    direct?: number
    indirect?: number
    nearest_km?: number | null
    rings?: Record<string, number>
  }
}


export function Analyze() {
  const navigate = useNavigate()
  const { result, setResult, setForm, lang } = useAnalysis()
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<LocationOut[]>([])
  const [searching, setSearching] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setLocalForm] = useState({
    q: '',
    state: '',
    district: '',
    block: '',
    village: '',
    latitude: 0,
    longitude: 0,
    capital_available: 100000,
    category_code: 'dairy',
    business_experience: false,
    existing_shop: false,
    existing_equipment: false,
    family_members: 0,
    preferred_scale: 'small',
  })
  // Exact proposed shop location (dragged on the map). Kept separate from the
  // admin-area selection so the proposed point never overwrites the village.
  const [areaPinned, setAreaPinned] = useState(false)
  const [draftProposed, setDraftProposed] = useState<{ lat: number; lng: number } | null>(null)
  const [confirmedProposed, setConfirmedProposed] = useState<{ lat: number; lng: number } | null>(null)
  // Live competitor preview around the exact dragged map marker. Re-fetched
  // (debounced) on every marker move so results track the pin (A !== B when moved).
  const [liveComp, setLiveComp] = useState<DiscoveryResult | null>(null)
  const [liveCompLoading, setLiveCompLoading] = useState(false)
  const [liveCompError, setLiveCompError] = useState<string | null>(null)

  // SIH26091 multilingual NLP advisory (free-text → structured form + full report)
  const [advisoryText, setAdvisoryText] = useState('')
  const [advisoryLang, setAdvisoryLang] = useState<Language>('en')
  const [advisoryParsing, setAdvisoryParsing] = useState(false)
  const [advisoryReport, setAdvisoryReport] = useState<AdvisoryReport | null>(null)
  const [advisoryLoading, setAdvisoryLoading] = useState(false)
  const [advisoryError, setAdvisoryError] = useState<string | null>(null)
  const [advisoryNote, setAdvisoryNote] = useState<string | null>(null)

  useEffect(() => {
    api.get<{ categories: Category[] }>('/financial/categories')
      .then((r) => setCategories(r.categories))
      .catch(() => setCategories([]))
  }, [])

  useEffect(() => {
    if (!form.q.trim()) {
      setLocations([])
      return
    }
    setSearching(true)
    api
      .get<LocationOut[]>(`/locations/search?q=${encodeURIComponent(form.q)}&limit=15`)
      .then((r) => setLocations(r))
      .catch(() => setLocations([]))
      .finally(() => setSearching(false))
  }, [form.q])

  // Live competitor preview: whenever the exact search radius. Debounce ~600ms
  // so dragging the pin issues one query at rest, keyed by the exact lat/lng.
  useEffect(() => {
    if (!draftProposed) {
      setLiveComp(null)
      setLiveCompError(null)
      return
    }
    setLiveCompLoading(true)
    setLiveCompError(null)
    const timer = window.setTimeout(() => {
      api
        .post<DiscoveryResult>('/businesses/discovery', {
          latitude: draftProposed.lat,
          longitude: draftProposed.lng,
          category_code: form.category_code,
        })
        .then((r) => setLiveComp(r))
        .catch((e: any) => {
          setLiveComp(null)
          setLiveCompError(e.message || tr('competitorPreviewUnavailable', lang))
        })
        .finally(() => setLiveCompLoading(false))
    }, 600)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftProposed, lang])


  const pickLocation = (l: LocationOut) => {
    setLocalForm((f) => ({
      ...f,
      q: [l.village, l.block, l.district, l.state].filter(Boolean).join(', '),
      state: l.state,
      district: l.district,
      block: l.block || '',
      village: l.village || '',
      latitude: l.latitude,
      longitude: l.longitude,
    }))
    setAreaPinned(true)
    setDraftProposed(null)
    setConfirmedProposed(null)
    setLocations([])
  }

  const loadDemo = async () => {
    setLoading(true)
    setError(null)
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
      navigate('/dashboard')
    } catch (e: any) {
      setError(e.message || tr('analysisFailedDemo', lang))
    } finally {
      setLoading(false)
    }
  }

  const confirmProposed = () => {
    if (draftProposed) setConfirmedProposed({ lat: draftProposed.lat, lng: draftProposed.lng })
  }

  // Parse free text (English/Tamil/Hindi) via the NLP engine and pre-fill the
  // structured feasibility form from the extracted fields (SIH26091 FR: NLP).
  const parseAndPrefill = async () => {
    if (!advisoryText.trim()) return
    setAdvisoryParsing(true)
    setAdvisoryError(null)
    setAdvisoryNote(null)
    try {
      const parsed = await api.post<AdvisoryParseOutput>('/advisory/parse', {
        free_text: advisoryText,
        language: advisoryLang,
      })
      const next = { ...form }
      if (parsed.business_type) next.category_code = parsed.business_type
      if (parsed.scale) next.preferred_scale = parsed.scale
      if (parsed.project_cost) next.capital_available = parsed.project_cost
      if (parsed.location?.state) next.state = parsed.location.state
      if (parsed.location?.district) next.district = parsed.location.district
      if (parsed.location?.block) next.block = parsed.location.block
      if (parsed.location?.village) next.village = parsed.location.village
      setLocalForm(next)
      setForm(next)
      setAdvisoryNote(
        interpolate(tr('advisoryParsedAs', lang), {
          type: parsed.business_type || '—',
          lang: parsed.detected_language || 'en',
          pct: String(Math.round((parsed.confidence?.overall ?? 0) * 100)),
        }),
      )
    } catch (e: any) {
      setAdvisoryError(e.message || tr('couldNotParse', lang))
    } finally {
      setAdvisoryParsing(false)
    }
  }

  // Run the full multilingual advisory pipeline and render the report inline.
  const runFullAdvisory = async () => {
    if (!advisoryText.trim()) return
    setAdvisoryLoading(true)
    setAdvisoryError(null)
    setAdvisoryReport(null)
    try {
      const report = await api.post<AdvisoryReport>('/advisory/report', {
        free_text: advisoryText,
        language: advisoryLang,
      })
      setAdvisoryReport(report)
    } catch (e: any) {
      setAdvisoryError(e.message || tr('couldNotGenerateAdvisory', lang))
    } finally {
      setAdvisoryLoading(false)
    }
  }

  // Exact pin placement is mandatory before a real analysis: any new pin
  // placement (drag, map click, GPS, search result) invalidates a previous
  // confirmation, so generate stays blocked until the exact spot is confirmed.
  const exactConfirmed =
    confirmedProposed !== null &&
    draftProposed !== null &&
    confirmedProposed.lat === draftProposed.lat &&
    confirmedProposed.lng === draftProposed.lng
  const canGenerate =
    areaPinned && !!form.latitude && !!form.longitude && !!draftProposed && exactConfirmed

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const payload = {
        state: form.state,
        district: form.district,
        block: form.block || undefined,
        village: form.village || undefined,
        proposed_latitude: confirmedProposed ? confirmedProposed.lat : undefined,
        proposed_longitude: confirmedProposed ? confirmedProposed.lng : undefined,
        capital_available: form.capital_available,
        category_code: form.category_code,
        business_experience: form.business_experience,
        existing_shop: form.existing_shop,
        existing_equipment: form.existing_equipment,
        family_members: form.family_members,
        preferred_scale: form.preferred_scale,
      }
      setForm(payload)
      const res = await api.post<AnalysisResult>('/analysis', payload)
      setResult(res)
      navigate('/dashboard')
    } catch (e: any) {
      setError(e.message || tr('analysisFailedDemo', lang))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{tr('feasibilityPlanTitle', lang)}</h1>
        <p className="text-sm text-gray-500">
          {result ? tr('analyzeIntroResult', lang) : tr('analyzeIntroNoResult', lang)} {tr('viewResultDashboard', lang)}{result ? ` ${tr('viewUpdatedResult', lang)}` : ''} {tr('onDashboard', lang)}
        </p>
      </div>

      {/* SIH26091: Multilingual NLP advisory — describe the business in plain words */}
      <Card>
        <CardHeader
          title={tr('advisoryTitle', advisoryLang)}
          subtitle={tr('advisorySubtitle', advisoryLang)}
        />
        <div className="space-y-3">
          <textarea
            value={advisoryText}
            onChange={(e) => setAdvisoryText(e.target.value)}
            rows={3}
            placeholder={tr('advisoryPlaceholder', advisoryLang)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={advisoryLang}
              onChange={(e) => setAdvisoryLang(e.target.value as Language)}
              className="rounded-lg border border-gray-300 px-2 py-1.5 text-sm text-gray-700"
            >
              <option value="en">English</option>
              <option value="ta">தமிழ்</option>
              <option value="hi">हिंदी</option>
            </select>
            <Button
              type="button"
              variant="outline"
              onClick={parseAndPrefill}
              disabled={advisoryParsing || !advisoryText.trim()}
            >
              {advisoryParsing ? tr('parsing', advisoryLang) : tr('parsePrefill', advisoryLang)}
            </Button>
            <Button
              type="button"
              onClick={runFullAdvisory}
              disabled={advisoryLoading || !advisoryText.trim()}
            >
              {advisoryLoading ? tr('generating', advisoryLang) : tr('fullAdvisory', advisoryLang)}
            </Button>
            {advisoryNote && <span className="text-xs text-emerald-700">{advisoryNote}</span>}
          </div>
          {advisoryError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">{advisoryError}</div>
          )}
          {advisoryReport && <AdvisoryReportView report={advisoryReport} lang={advisoryLang} />}
        </div>
      </Card>

      <div className="rounded-xl border border-brand-200 bg-brand-50 p-4 text-sm text-brand-800">
        <strong>{tr('quickStart', lang)}</strong> {tr('notSureWhatToEnter', lang)}{' '}
        <button onClick={loadDemo} disabled={loading} className="font-semibold underline">
          {loading ? tr('running', lang) : tr('loadDemoWorkspace', lang)}
        </button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title={tr('yourLocation', lang)} subtitle={tr('yourLocationSub', lang)} />
          <label className="mb-1 block text-xs font-medium text-gray-600">{tr('searchVillageBlock', lang)}</label>
          <input
            value={form.q}
            onChange={(e) => setLocalForm((f) => ({ ...f, q: e.target.value }))}
            placeholder={tr('searchPlaceholder', lang)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          {searching && <p className="mt-1 text-xs text-gray-400">{tr('searching', lang)}</p>}
          {locations.length > 0 && (
            <ul className="mt-2 max-h-48 overflow-auto rounded-lg border border-gray-200 bg-white">
              {locations.map((l) => (
                <li key={l.id}>
                  <button
                    type="button"
                    onClick={() => pickLocation(l)}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-brand-50"
                  >
                    <span className="font-medium text-gray-800">
                      {[l.village, l.block].filter(Boolean).join(', ')}
                    </span>
                    <span className="text-gray-400"> · {l.district}, {l.state}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 grid grid-cols-3 gap-3">
            <Field label={tr('state', lang)} value={form.state} onChange={(v) => setLocalForm((f) => ({ ...f, state: v }))} />
            <Field label={tr('district', lang)} value={form.district} onChange={(v) => setLocalForm((f) => ({ ...f, district: v }))} />
            <Field label={tr('block', lang)} value={form.block} onChange={(v) => setLocalForm((f) => ({ ...f, block: v }))} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Field label={tr('village', lang)} value={form.village} onChange={(v) => setLocalForm((f) => ({ ...f, village: v }))} />
            <label className="text-xs text-gray-500">
              <span className="font-medium">{tr('adminAreaCentre', lang)}</span>
              <div className="mt-1 rounded-lg bg-gray-50 p-2 font-mono text-xs">
                {form.latitude ? `${form.latitude.toFixed(4)}, ${form.longitude.toFixed(4)}` : tr('notPinned', lang)}
              </div>
            </label>
          </div>

          {areaPinned && form.latitude && form.longitude ? (
            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-medium text-gray-600">{tr('exactProposedShop', lang)}</span>
                <span className="text-[10px] text-gray-400">{tr('dragPinOrClick', lang)}</span>
              </div>
              <ShopLocationPicker
                latitude={form.latitude}
                longitude={form.longitude}
                confirmedLat={confirmedProposed ? confirmedProposed.lat : null}
                confirmedLng={confirmedProposed ? confirmedProposed.lng : null}
                onProposedChange={(lat, lng) => {
                  setDraftProposed({ lat, lng })
                  setConfirmedProposed(null)
                }}
              />
              <div className="mt-2 rounded-lg border border-gray-200 bg-gray-50 p-2.5 text-xs text-gray-700">
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-medium text-gray-800">{tr('competitorsAroundPoint', lang)}</span>
                  {draftProposed && (
                    <span className="text-[10px] text-gray-400">
                      {tr('refreshOnMove', lang)} {liveCompLoading ? tr('searching', lang) : ''}
                    </span>
                  )}
                </div>
                {!draftProposed ? (
                  <p className="text-gray-400">{tr('movePinToPreview', lang)}</p>
                ) : liveCompError ? (
                  <p className="text-red-600">{liveCompError}</p>
                ) : liveComp ? (
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <strong className="text-base text-gray-900">
                        {interpolate(tr('totalMapped', lang), { n: liveComp.competitors?.total_mapped ?? 0 })}
                      </strong>
                      <span className="text-emerald-700">{interpolate(tr('directCount', lang), { n: liveComp.competitors?.direct ?? 0 })}</span>
                      <span className="text-amber-700">{interpolate(tr('indirectCount', lang), { n: liveComp.competitors?.indirect ?? 0 })}</span>
                      {liveComp.competitors?.nearest_km != null && (
                        <span>{interpolate(tr('nearestApprox', lang), { n: liveComp.competitors.nearest_km })}</span>
                      )}
                      <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[10px] uppercase">
                        {liveComp.data_status}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-gray-500">
                      <span>
                        {interpolate(tr('withinRadiusKm', lang), { n: Math.round((liveComp.search_radius_m || 3000) / 1000) })}
                        {liveComp.data?.primary_source || 'OSM'}
                      </span>
                      {liveComp.confidence?.label && (
                        <span>{tr('coverageLabel', lang)}{liveComp.confidence.label}</span>
                      )}
                      {liveComp.competitors?.rings &&
                        Object.entries(liveComp.competitors.rings)
                          .filter(([, v]) => Number(v) > 0)
                          .slice(0, 4)
                          .map(([k, v]) => (
                            <span key={k}>
                              {k.replace('m', ' m')}: {v}
                            </span>
                          ))}
                    </div>
                    <p className="text-[10px] text-gray-400">
                      {liveComp.data?.note ||
                        tr('zeroMappedNote', lang)}
                    </p>
                  </div>
                ) : (
                  <p className="text-gray-400">{tr('searchingDots', lang)}</p>
                )}
              </div>
              <div className="mt-2 flex items-center justify-between gap-3">
                {exactConfirmed ? (
                  <span className="text-xs font-medium text-emerald-600">
                    {interpolate(tr('confirmedLocation', lang), { lat: confirmedProposed.lat.toFixed(5), lng: confirmedProposed.lng.toFixed(5) })}
                  </span>
                ) : (
                  <span className="text-xs font-medium text-amber-600">
                    {tr('notConfirmed', lang)}
                  </span>
                )}
                <button
                  type="button"
                  onClick={confirmProposed}
                  disabled={!draftProposed || !!confirmedProposed}
                  className="shrink-0 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {confirmedProposed ? tr('confirmed', lang) : tr('confirmThisLocation', lang)}
                </button>
              </div>
              {!exactConfirmed && (
                <p className="mt-1 text-[11px] text-amber-600">
                  {tr('confirmBeforeGenerate', lang)}
                </p>
              )}
              <p className="mt-1 text-[10px] text-gray-400">
                {tr('pinUnconfirmedNote', lang)}
              </p>
            </div>
          ) : null}
        </Card>

        <Card>
          <CardHeader title={tr('businessCapital', lang)} subtitle={tr('businessCapitalSub', lang)} />
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">{tr('businessCategory', lang)}</label>
              <select
                value={form.category_code}
                onChange={(e) => setLocalForm((f) => ({ ...f, category_code: e.target.value }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              >
                {categories.length === 0 && <option value="dairy">{tr('catDairy', lang)}</option>}
                {categories.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">
                {tr('availableCapitalLabel', lang)}{form.capital_available.toLocaleString('en-IN')}
              </label>
              <input
                type="range"
                min={5000}
                max={1000000}
                step={5000}
                value={form.capital_available}
                onChange={(e) => setLocalForm((f) => ({ ...f, capital_available: Number(e.target.value) }))}
                className="w-full"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">{tr('preferredScale', lang)}</label>
              <div className="flex gap-2">
                {['micro', 'small', 'medium'].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setLocalForm((f) => ({ ...f, preferred_scale: s }))}
                    className={`flex-1 rounded-lg border px-3 py-1.5 text-sm capitalize ${
                      form.preferred_scale === s
                        ? 'border-brand-600 bg-brand-50 text-brand-700'
                        : 'border-gray-300 text-gray-600'
                    }`}
                  >
                    {tr(s as 'micro' | 'small' | 'medium', lang)}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Toggle label={tr('experience', lang)} value={form.business_experience} onChange={(v) => setLocalForm((f) => ({ ...f, business_experience: v }))} lang={lang} />
              <Toggle label={tr('hasShop', lang)} value={form.existing_shop} onChange={(v) => setLocalForm((f) => ({ ...f, existing_shop: v }))} lang={lang} />
              <Toggle label={tr('hasEquip', lang)} value={form.existing_equipment} onChange={(v) => setLocalForm((f) => ({ ...f, existing_equipment: v }))} lang={lang} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">{tr('familyMembers', lang)}</label>
              <input
                type="number"
                min={0}
                value={form.family_members}
                onChange={(e) => setLocalForm((f) => ({ ...f, family_members: Number(e.target.value) }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
        </Card>

        <div className="lg:col-span-2 flex justify-between">
          <Button type="button" variant="outline" onClick={() => navigate('/')}>
            {tr('back', lang)}
          </Button>
          <div className="flex flex-col items-end gap-1">
            {!canGenerate && !loading && areaPinned && (
              <p className="text-xs font-medium text-amber-700">
                {tr('confirmBeforeGenerate', lang)}
              </p>
            )}
            <Button type="submit" disabled={loading || !canGenerate}>
              {loading ? tr('computing', lang) : tr('generateReport', lang)}
            </Button>
          </div>
        </div>
      </form>
    </div>
  )
}

function AdvisoryReportView({ report, lang }: { report: AdvisoryReport; lang: Language }) {
  const fs = report.financial_structure
  const ls = fs?.loan_structure
  const summary = report.summary
  const schemes = report.scheme_eligibility ?? []
  return (
    <div className="mt-3 space-y-3 rounded-xl border border-gray-200 bg-gray-50 p-4">
      <h3 className="text-sm font-bold text-gray-900">{tr('fullReportTitle', lang)}</h3>

      {summary && <p className="rounded-lg bg-white p-3 text-sm text-gray-700">{summary}</p>}

      <div className="grid gap-3 md:grid-cols-2">
        {schemes.length > 0 && (
          <div className="rounded-lg bg-white p-3">
            <div className="mb-1 text-xs font-semibold uppercase text-gray-500">{tr('bestSchemes', lang)}</div>
            <ul className="space-y-1">
              {schemes.slice(0, 4).map((s) => (
                <li key={s.scheme_code} className="flex items-center justify-between text-sm">
                  <span className="text-gray-800">{s.scheme_name}</span>
                  <span className="rounded px-1.5 py-0.5 text-[10px] font-medium text-white bg-brand-600">
                    {Math.round(s.match_score)}% · {s.status.slice(0, 3)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {ls && (
          <div className="rounded-lg bg-white p-3">
            <div className="mb-1 text-xs font-semibold uppercase text-gray-500">{tr('loanStructure', lang)}</div>
            <dl className="space-y-1 text-sm">
              <Row k={tr('recommendedScheme', lang)} v={fs?.recommended_scheme ?? ls.scheme_name ?? '—'} />
              <Row k={tr('loanAmount', lang)} v={inr(ls.loan_amount)} />
              <Row k={tr('interestRatePA', lang)} v={ls.interest_rate != null ? `${ls.interest_rate}%` : '—'} />
              <Row k={tr('tenure', lang)} v={ls.tenure_years != null ? `${ls.tenure_years} ${tr('yr', lang)}` : '—'} />
              <Row k={tr('emiDuringMoratorium', lang)} v={inr(ls.monthly_emi_during_moratorium)} />
              <Row k={tr('emiAfterMoratorium', lang)} v={inr(ls.monthly_emi_after_moratorium)} />
              <Row k={tr('totalInterest', lang)} v={inr(ls.total_interest)} />
            </dl>
            {ls && ls.is_assumed && (
              <div className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                {tr('assumedFieldsNote', lang)}{' '}
                {((ls.assumed_fields ?? []).length ? (ls.assumed_fields as string[]) : ['financial_terms']).join(', ')}.
                {tr('verifyWithAgency', lang)}
              </div>
            )}
            {ls.repayment_health?.label && (
              <div className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                {tr('repayHealth', lang)}: {ls.repayment_health.label} {ls.repayment_health.disclaimer ? `· ${tr('estimate', lang)}` : ''}
              </div>
            )}
          </div>
        )}
      </div>

      {report.risks?.high?.length > 0 && (
        <div className="rounded-lg bg-white p-3">
          <div className="mb-1 text-xs font-semibold uppercase text-gray-500">{tr('keyRisks', lang)}</div>
          <ul className="list-inside list-disc space-y-0.5 text-sm text-gray-700">
            {report.risks.high.slice(0, 3).map((r: any, i: number) => (
              <li key={i}>{r.risk || r}</li>
            ))}
          </ul>
        </div>
      )}

      {report.key_documents?.length > 0 && (
        <div className="rounded-lg bg-white p-3">
          <div className="mb-1 text-xs font-semibold uppercase text-gray-500">{tr('documentsNeeded', lang)}</div>
          <ul className="list-inside list-disc space-y-0.5 text-sm text-gray-700">
            {report.key_documents.slice(0, 8).map((d: any, i: number) => (
              <li key={i}>{typeof d === 'string' ? d : d.document || d.name || JSON.stringify(d)}</li>
            ))}
          </ul>
        </div>
      )}

      {report.disclaimer && <p className="text-[11px] text-gray-400">{report.disclaimer}</p>}
    </div>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-gray-500">{k}</dt>
      <dd className="font-medium text-gray-900">{v}</dd>
    </div>
  )
}

function inr(n?: number | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  return '₹' + Math.round(n).toLocaleString('en-IN')
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
    </label>
  )
}

function Toggle({ label, value, onChange, lang }: { label: string; value: boolean; onChange: (v: boolean) => void; lang: Language }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={`rounded-lg border px-3 py-2 text-sm ${
        value ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-gray-300 text-gray-600'
      }`}
    >
      {label}: {value ? tr('yes', lang) : tr('no', lang)}
    </button>
  )
}
