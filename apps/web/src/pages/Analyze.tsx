import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Button, Card, CardHeader } from '../components/ui'
import { ShopLocationPicker } from '../components/ShopLocationPicker'
import type { AnalysisResult, Category, LocationOut } from '../types'

export function Analyze() {
  const navigate = useNavigate()
  const { result, setResult, setForm } = useAnalysis()
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
      setError(e.message || 'Analysis failed')
    } finally {
      setLoading(false)
    }
  }

  const confirmProposed = () => {
    if (draftProposed) setConfirmedProposed({ lat: draftProposed.lat, lng: draftProposed.lng })
  }

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
      setError(e.message || 'Analysis failed. Try the demo workspace.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Business Feasibility & Financial Plan</h1>
        <p className="text-sm text-gray-500">
          {result ? 'Rebuild the analysis with new inputs, or' : 'Fill in your details and'} view the {result ? 'updated' : ''} result on the Dashboard.
        </p>
      </div>

      <div className="rounded-xl border border-brand-200 bg-brand-50 p-4 text-sm text-brand-800">
        <strong>Quick start:</strong> not sure what to enter yet?{' '}
        <button onClick={loadDemo} disabled={loading} className="font-semibold underline">
          {loading ? 'Running…' : 'Load a demo workspace (Perundurai, restaurant)'}
        </button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Your Location" subtitle="Search for your village or town. Coordinates come from the pinned Census/OSM baseline." />
          <label className="mb-1 block text-xs font-medium text-gray-600">Search village / block / district</label>
          <input
            value={form.q}
            onChange={(e) => setLocalForm((f) => ({ ...f, q: e.target.value }))}
            placeholder="e.g. Bhavani, Erode"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          {searching && <p className="mt-1 text-xs text-gray-400">Searching…</p>}
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
            <Field label="State" value={form.state} onChange={(v) => setLocalForm((f) => ({ ...f, state: v }))} />
            <Field label="District" value={form.district} onChange={(v) => setLocalForm((f) => ({ ...f, district: v }))} />
            <Field label="Block" value={form.block} onChange={(v) => setLocalForm((f) => ({ ...f, block: v }))} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Field label="Village" value={form.village} onChange={(v) => setLocalForm((f) => ({ ...f, village: v }))} />
            <label className="text-xs text-gray-500">
              <span className="font-medium">Admin area centre</span>
              <div className="mt-1 rounded-lg bg-gray-50 p-2 font-mono text-xs">
                {form.latitude ? `${form.latitude.toFixed(4)}, ${form.longitude.toFixed(4)}` : 'Not pinned — demo will pin it'}
              </div>
            </label>
          </div>

          {areaPinned && form.latitude && form.longitude ? (
            <div className="mt-4">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-medium text-gray-600">Exact proposed shop location</span>
                <span className="text-[10px] text-gray-400">drag the pin or click the map</span>
              </div>
              <ShopLocationPicker
                latitude={form.latitude}
                longitude={form.longitude}
                confirmedLat={confirmedProposed ? confirmedProposed.lat : null}
                confirmedLng={confirmedProposed ? confirmedProposed.lng : null}
                onProposedChange={(lat, lng) => setDraftProposed({ lat, lng })}
              />
              <div className="mt-2 flex items-center justify-between gap-3">
                {confirmedProposed ? (
                  <span className="text-xs font-medium text-emerald-600">
                    Using exact location {confirmedProposed.lat.toFixed(5)}, {confirmedProposed.lng.toFixed(5)} for competitor search
                  </span>
                ) : (
                  <span className="text-xs text-gray-500">
                    {draftProposed
                      ? `${draftProposed.lat.toFixed(5)}, ${draftProposed.lng.toFixed(5)} — not yet used.`
                      : 'Pin the exact spot on the map.'}
                  </span>
                )}
                <button
                  type="button"
                  onClick={confirmProposed}
                  disabled={!draftProposed || !!confirmedProposed}
                  className="shrink-0 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                >
                  {confirmedProposed ? 'Confirmed' : 'Confirm this location'}
                </button>
              </div>
              <p className="mt-1 text-[10px] text-gray-400">
                If unconfirmed, analysis uses the selected admin area centre. Competitors are searched from the exact confirmed point.
              </p>
            </div>
          ) : null}
        </Card>

        <Card>
          <CardHeader title="Business & Capital" subtitle="These drive the financial plan and profit estimate." />
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">Business category</label>
              <select
                value={form.category_code}
                onChange={(e) => setLocalForm((f) => ({ ...f, category_code: e.target.value }))}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              >
                {categories.length === 0 && <option value="dairy">Dairy</option>}
                {categories.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">
                Available capital (₹) — {form.capital_available.toLocaleString('en-IN')}
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
              <label className="mb-1 block text-xs font-medium text-gray-600">Preferred scale</label>
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
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Toggle label="Experience" value={form.business_experience} onChange={(v) => setLocalForm((f) => ({ ...f, business_experience: v }))} />
              <Toggle label="Has shop" value={form.existing_shop} onChange={(v) => setLocalForm((f) => ({ ...f, existing_shop: v }))} />
              <Toggle label="Has equip." value={form.existing_equipment} onChange={(v) => setLocalForm((f) => ({ ...f, existing_equipment: v }))} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">Family members helping</label>
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
            Back
          </Button>
          <Button type="submit" disabled={loading}>
            {loading ? 'Computing…' : 'Generate Report'}
          </Button>
        </div>
      </form>
    </div>
  )
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-gray-600">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm" />
    </label>
  )
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={`rounded-lg border px-3 py-2 text-sm ${
        value ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-gray-300 text-gray-600'
      }`}
    >
      {label}: {value ? 'Yes' : 'No'}
    </button>
  )
}
