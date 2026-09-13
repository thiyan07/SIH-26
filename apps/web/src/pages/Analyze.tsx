import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Button, CardHeader } from '../components/ui'
import { ShopLocationPicker } from '../components/ShopLocationPicker'
import { VoiceInput } from '../components/VoiceInput'
import { BackgroundBeams, Spotlight } from '../components/aceternity/BackgroundBeams'
import { BentoGrid, BentoCard } from '../components/aceternity/BentoGrid'

import { tr, interpolate, type Language } from '../lib/i18n'
import type { AnalysisResult, Category, LocationOut, AdvisoryParseOutput } from '../types'


export function Analyze() {
  const navigate = useNavigate()
  const { result, setResult, form: storedForm, setForm, lang, advisoryText: storedAdvisoryText, setAdvisoryText: setStoredAdvisoryText, advisoryLang: storedAdvisoryLang, setAdvisoryLang: setStoredAdvisoryLang, setApplicantAge } = useAnalysis() as any
  const [categories, setCategories] = useState<Category[]>([])
  const [locations, setLocations] = useState<LocationOut[]>([])
  const [searching, setSearching] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoRecommend, setAutoRecommend] = useState(false)
  const initialForm = storedForm ? {
    q: (storedForm.q as string) || '',
    state: (storedForm.state as string) || '',
    district: (storedForm.district as string) || '',
    block: (storedForm.block as string) || '',
    village: (storedForm.village as string) || '',
    latitude: (storedForm.latitude as number) || 0,
    longitude: (storedForm.longitude as number) || 0,
    capital_available: (storedForm.capital_available as number) || 100000,
    category_code: (storedForm.category_code as string) || 'dairy',
    business_experience: (storedForm.business_experience as boolean) || false,
    existing_shop: (storedForm.existing_shop as boolean) || false,
    existing_equipment: (storedForm.existing_equipment as boolean) || false,
    family_members: (storedForm.family_members as number) || 0,
    preferred_scale: (storedForm.preferred_scale as string) || 'small',
    applicant_age: (storedForm.applicant_age as number) || 28,
  } : {
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
    applicant_age: 28,
  }
  const [form, setLocalForm] = useState(initialForm)
  const [areaPinned, setAreaPinned] = useState(!!initialForm.latitude && !!initialForm.longitude)
  const [draftProposed, setDraftProposed] = useState<{ lat: number; lng: number } | null>(initialForm.latitude && initialForm.longitude ? { lat: initialForm.latitude, lng: initialForm.longitude } : null)
  const [confirmedProposed, setConfirmedProposed] = useState<{ lat: number; lng: number } | null>(initialForm.latitude && initialForm.longitude ? { lat: initialForm.latitude, lng: initialForm.longitude } : null)

  const [advisoryText, setAdvisoryText] = useState(storedAdvisoryText || '')
  const [advisoryLang, setAdvisoryLang] = useState<Language>(storedAdvisoryLang || 'en')
  const [advisoryParsing, setAdvisoryParsing] = useState(false)
  const [advisoryError, setAdvisoryError] = useState<string | null>(null)
  const [advisoryNote, setAdvisoryNote] = useState<string | null>(null)

  // Persist advisory text/lang to store (survives navigation, clears on refresh)
  useEffect(() => { setStoredAdvisoryText(advisoryText) }, [advisoryText])
  useEffect(() => { setStoredAdvisoryLang(advisoryLang) }, [advisoryLang])

  // Persist form draft to store on every change (so navigation preserves it)
  useEffect(() => {
    setForm(form as any)
    if (form.applicant_age) setApplicantAge(form.applicant_age)
  }, [form])

  useEffect(() => {
    api.get<{ categories: Category[] }>('/financial/categories')
      .then((r) => setCategories(r.categories))
      .catch(() => setCategories([]))
  }, [])

  // Instant search: preload Tamil Nadu villages for client-side filtering (state-wide, not Erode-only)
  const [tamilCache, setTamilCache] = useState<LocationOut[] | null>(null)
  const searchCache = useRef<Map<string, LocationOut[]>>(new Map())
  const seqRef = useRef(0)
  useEffect(() => {
    api.get<LocationOut[]>(`/locations/search?state=${encodeURIComponent('Tamil Nadu')}&limit=800`)
      .then((r) => setTamilCache(r))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const q = form.q.trim()
    if (!q) {
      setLocations([])
      setSearching(false)
      return
    }
    // Instant for single letter: filter from local Tamil Nadu cache (no server fetch)
    if (q.length === 1 && tamilCache) {
      const low = q.toLowerCase()
      const instant = tamilCache.filter(l => (l.village || '').toLowerCase().startsWith(low) || (l.block || '').toLowerCase().startsWith(low)).slice(0, 15)
      if (instant.length) {
        setLocations(instant)
        setSearching(false)
        return
      }
    }
    if (searchCache.current.has(q.toLowerCase())) {
      setLocations(searchCache.current.get(q.toLowerCase())!)
      setSearching(false)
      return
    }
    setSearching(true)
    const seq = ++seqRef.current
    const timer = window.setTimeout(() => {
      api
        .get<LocationOut[]>(`/locations/search?q=${encodeURIComponent(q)}&limit=15`)
        .then((r) => {
          if (seq !== seqRef.current) return
          searchCache.current.set(q.toLowerCase(), r)
          setLocations(r)
        })
        .catch(() => {
          if (seq !== seqRef.current) return
          setLocations([])
        })
        .finally(() => {
          if (seq === seqRef.current) setSearching(false)
        })
    }, q.length === 1 ? 80 : 200)
    return () => window.clearTimeout(timer)
  }, [form.q, tamilCache])




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
    setDraftProposed({ lat: l.latitude, lng: l.longitude })
    setConfirmedProposed(null)
    setLocations([])
  }



  const confirmProposed = () => {
    if (draftProposed) setConfirmedProposed({ lat: draftProposed.lat, lng: draftProposed.lng })
  }

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
      if (parsed.business_type) {
        next.category_code = parsed.business_type
        setAutoRecommend(false)
      }
      if (parsed.scale) next.preferred_scale = parsed.scale
      // Capital: prefer capital_available, fallback to project_cost
      const capital = (parsed as any).capital_available ?? parsed.project_cost
      if (capital) next.capital_available = capital
      // Age if extracted
      if ((parsed as any).age) next.applicant_age = (parsed as any).age
      // Location: update only if provided, but clear block/village if district changes and new block/village is empty
      const newDistrict = parsed.location?.district
      const newBlock = parsed.location?.block
      const newVillage = parsed.location?.village
      const newState = parsed.location?.state
      if (newState) next.state = newState
      if (newDistrict) {
        // If district changes, clear stale block/village if new ones are empty
        const districtChanged = newDistrict && newDistrict.toLowerCase() !== (form.district || '').toLowerCase()
        next.district = newDistrict
        if (newBlock) next.block = newBlock
        else if (districtChanged) next.block = ''
        if (newVillage) next.village = newVillage
        else if (districtChanged) next.village = ''
      } else {
        if (newBlock) next.block = newBlock
        if (newVillage) next.village = newVillage
      }
      // If block is known but district is still empty, infer district/state via location logic (Perundurai -> Erode)
      if (newBlock && !next.district) {
        const lower = newBlock.toLowerCase()
        if (['perundurai','bhavani','gobichettipalayam','sathyamangalam','anthiyur','nambiyur','modakkurichi','erode'].includes(lower)) {
          next.district = 'Erode'
          if (!next.state) next.state = 'Tamil Nadu'
        }
      }
      // Ensure at least state is set if district was set
      if (newDistrict && !next.state) next.state = 'Tamil Nadu'
      // If location resolved, try to geocode to lat/lng via search
      setLocalForm(next)
      setAdvisoryNote(
        interpolate(tr('advisoryParsedAs', lang), {
          type: parsed.business_type || '—',
          lang: parsed.detected_language || 'en',
          pct: String(Math.round((parsed.confidence?.overall ?? 0) * 100)),
        }),
      )
      // If we have district/block/village but no coordinates, attempt to resolve coordinates
      if ((next.district || next.block || next.village) && !next.latitude) {
        try {
          const qParts = [next.village, next.block, next.district].filter(Boolean).join(' ')
          if (qParts) {
            const locs = await api.get<LocationOut[]>(`/locations/search?q=${encodeURIComponent(qParts)}&limit=5`)
            if (locs.length) {
              const best = locs[0]
              setLocalForm((f) => ({
                ...f,
                q: [best.village, best.block, best.district, best.state].filter(Boolean).join(', '),
                state: best.state || f.state,
                district: best.district || f.district,
                block: best.block || f.block,
                village: best.village || f.village,
                latitude: best.latitude,
                longitude: best.longitude,
              }))
              setAreaPinned(true)
              setDraftProposed({ lat: best.latitude, lng: best.longitude })
              setConfirmedProposed(null)
            }
          }
        } catch { /* ignore geocode failure, let user pick manually */ }
      }
    } catch (e: any) {
      setAdvisoryError(e.message || tr('couldNotParse', lang))
    } finally {
      setAdvisoryParsing(false)
    }
  }

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
      const payload: any = {
        state: form.state,
        district: form.district,
        block: form.block || undefined,
        village: form.village || undefined,
        proposed_latitude: confirmedProposed ? confirmedProposed.lat : undefined,
        proposed_longitude: confirmedProposed ? confirmedProposed.lng : undefined,
        capital_available: form.capital_available,
        category_code: autoRecommend ? undefined : form.category_code,
        auto_recommend: autoRecommend,
        business_experience: form.business_experience,
        existing_shop: form.existing_shop,
        existing_equipment: form.existing_equipment,
        family_members: form.family_members,
        preferred_scale: form.preferred_scale,
        applicant_age: form.applicant_age,
      }
      setForm(payload)
      if (form.applicant_age) setApplicantAge(form.applicant_age)
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
      <Spotlight>
        <div>
          <h1 className="break-words text-2xl font-bold tracking-tight text-gray-900">{tr('feasibilityPlanTitle', lang)}</h1>
          <p className="mt-1 break-words text-sm leading-relaxed text-gray-500">
            {result ? tr('analyzeIntroResult', lang) : tr('analyzeIntroNoResult', lang)} {tr('viewResultDashboard', lang)}{result ? ` ${tr('viewUpdatedResult', lang)}` : ''} {tr('onDashboard', lang)}
          </p>
        </div>
      </Spotlight>

      <BackgroundBeams className="rounded-2xl border border-gray-200">
        <div className="relative rounded-2xl bg-white p-5">
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
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
            />
            <div className="flex flex-wrap items-center gap-2">
              <VoiceInput lang={advisoryLang} onResult={(t) => setAdvisoryText((prev: string) => (prev ? prev + ' ' : '') + t)} />
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
              {advisoryNote && <span className="text-xs font-medium text-emerald-700">{advisoryNote}</span>}
            </div>
            {advisoryError && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-2.5 text-sm text-red-700">{advisoryError}</div>
            )}
          </div>
        </div>
      </BackgroundBeams>



      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <form onSubmit={submit} className="space-y-6">
        <BentoGrid className="md:grid-cols-2 lg:grid-cols-2">
          <BentoCard title={tr('yourLocation', lang)} description={tr('yourLocationSub', lang)}>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">{tr('searchVillageBlock', lang)}</label>
                <input
                  value={form.q}
                  onChange={(e) => setLocalForm((f) => ({ ...f, q: e.target.value }))}
                  placeholder={tr('searchPlaceholder', lang)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
                />
                {searching && <p className="mt-1 text-xs text-gray-500">{tr('searching', lang)}</p>}
                {locations.length > 0 && (
                  <ul className="mt-2 max-h-48 overflow-auto rounded-lg border border-gray-200 bg-white shadow-sm">
                    {locations.map((l) => (
                      <li key={l.id}>
                        <button
                          type="button"
                          onClick={() => pickLocation(l)}
                          className="w-full px-3 py-2 text-left text-sm hover:bg-teal-50"
                        >
                          <span className="font-medium text-gray-800">
                            {[l.village, l.block].filter(Boolean).join(', ')}
                          </span>
                          <span className="text-gray-500"> · {l.district}, {l.state}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="grid grid-cols-3 gap-3">
                <Field label={tr('state', lang)} value={form.state} onChange={(v) => {
                  setLocalForm((f) => {
                    // Changing state clears district/block/village and coords if state actually changed
                    const changed = v.toLowerCase() !== (f.state || '').toLowerCase()
                    if (changed) return { ...f, state: v, district: '', block: '', village: '', latitude: 0, longitude: 0, q: '' }
                    return { ...f, state: v }
                  })
                  if (v.toLowerCase() !== (form.state || '').toLowerCase()) {
                    setAreaPinned(false)
                    setDraftProposed(null)
                    setConfirmedProposed(null)
                  }
                }} />
                <Field label={tr('district', lang)} value={form.district} onChange={(v) => {
                  setLocalForm((f) => {
                    const changed = v.toLowerCase() !== (f.district || '').toLowerCase()
                    if (changed) return { ...f, district: v, block: '', village: '', latitude: 0, longitude: 0 }
                    return { ...f, district: v }
                  })
                  if (v.toLowerCase() !== (form.district || '').toLowerCase()) {
                    setAreaPinned(false)
                    setDraftProposed(null)
                    setConfirmedProposed(null)
                  }
                }} />
                <Field label={tr('block', lang)} value={form.block} onChange={(v) => setLocalForm((f) => ({ ...f, block: v }))} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label={tr('village', lang)} value={form.village} onChange={(v) => setLocalForm((f) => ({ ...f, village: v }))} />
                <label className="text-xs text-gray-500">
                  <span className="font-medium">{tr('adminAreaCentre', lang)}</span>
                  <div className="mt-1 rounded-lg bg-gray-50 p-2 font-mono text-xs">
                    {form.latitude ? `${form.latitude.toFixed(4)}, ${form.longitude.toFixed(4)}` : tr('notPinned', lang)}
                  </div>
                </label>
              </div>

              {areaPinned && form.latitude && form.longitude ? (
                <div className="pt-2">
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs font-semibold text-gray-700">{tr('exactProposedShop', lang)}</span>
                    <span className="text-[10px] text-gray-500">{tr('dragPinOrClick', lang)}</span>
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
                      className="shrink-0 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                    >
                      {confirmedProposed ? tr('confirmed', lang) : tr('confirmThisLocation', lang)}
                    </button>
                  </div>
                  {!exactConfirmed && (
                    <p className="mt-1 text-[11px] text-amber-600">
                      {tr('confirmBeforeGenerate', lang)}
                    </p>
                  )}
                  <p className="mt-1 text-[10px] text-gray-500">
                    {tr('pinUnconfirmedNote', lang)}
                  </p>
                </div>
              ) : null}
            </div>
          </BentoCard>

          <BentoCard title={tr('businessCapital', lang)} description={tr('businessCapitalSub', lang)}>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">{tr('businessCategory', lang)}</label>
                <select
                  value={form.category_code}
                  onChange={(e) => setLocalForm((f) => ({ ...f, category_code: e.target.value }))}
                  disabled={autoRecommend}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:bg-gray-100 disabled:text-gray-500 focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
                >
                  {categories.length === 0 && <option value="dairy">{tr('catDairy', lang)}</option>}
                  {categories.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.name}
                    </option>
                  ))}
                </select>
                <label className="mt-2 flex cursor-pointer items-center gap-2 rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2 text-xs font-medium text-amber-900 hover:bg-amber-50">
                  <input
                    type="checkbox"
                    checked={autoRecommend}
                    onChange={(e) => setAutoRecommend(e.target.checked)}
                    className="h-3.5 w-3.5 rounded border-amber-300 text-teal-600 focus:ring-teal-500"
                  />
                  <span>🤖 {tr('aiSuggestLabel', lang)}</span>
                </label>
                {autoRecommend && <p className="mt-1 text-[11px] text-gray-500">{tr('aiSuggestHint', lang)}</p>}
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
                  className="w-full accent-teal-600"
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
                          ? 'border-teal-600 bg-teal-50 text-teal-700'
                          : 'border-gray-300 text-gray-600 hover:bg-gray-50'
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
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">Applicant Age <span className="text-[11px] text-gray-500">(for scheme eligibility)</span></label>
                <input
                  type="number"
                  min={18}
                  max={65}
                  value={form.applicant_age}
                  onChange={(e) => setLocalForm((f) => ({ ...f, applicant_age: Number(e.target.value) || 0 }))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500"
                  placeholder="e.g. 28"
                />
                <p className="mt-1 text-[11px] text-gray-500">Required for age-restricted schemes like UYEGP (18-45) and Stand-Up India. If you leave default, analysis assumes 28.</p>
              </div>
            </div>
          </BentoCard>
        </BentoGrid>

        <div className="flex justify-between">
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

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-teal-500 focus:ring-1 focus:ring-teal-500" />
    </label>
  )
}

function Toggle({ label, value, onChange, lang }: { label: string; value: boolean; onChange: (v: boolean) => void; lang: Language }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={`rounded-lg border px-3 py-2 text-sm ${
        value ? 'border-teal-600 bg-teal-50 text-teal-700' : 'border-gray-300 text-gray-600 hover:bg-gray-50'
      }`}
    >
      {label}: {value ? tr('yes', lang) : tr('no', lang)}
    </button>
  )
}
