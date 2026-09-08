import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Card, CardHeader, Badge } from '../components/ui'
import { PageHeader } from '../components/PageHeader'
import { formatINR } from './Dashboard'
import type { LocationOut } from '../types'

async function resolveVillage(village: string): Promise<{ payload: Record<string, unknown>; label: string }> {
  const q = village.trim()
  // Try to resolve to a real location for accurate lat/lon
  try {
    const locs = await api.get<LocationOut[]>(`/locations/search?q=${encodeURIComponent(q)}&state=${encodeURIComponent('Tamil Nadu')}&limit=5`)
    const hit = locs.find(l => l.village?.toLowerCase() === q.toLowerCase() || l.block?.toLowerCase() === q.toLowerCase()) || locs[0]
    if (hit) {
      return {
        payload: {
          state: hit.state,
          district: hit.district,
          block: hit.block,
          village: hit.village,
          capital_available: 100000,
          category_code: 'grocery',
          proposed_latitude: hit.latitude,
          proposed_longitude: hit.longitude,
        },
        label: hit.village || hit.block || q,
      }
    }
  } catch { /* fallback to raw */ }
  return {
    payload: { state: 'Tamil Nadu', district: 'Erode', block: q, village: q, capital_available: 100000, category_code: 'grocery' },
    label: q,
  }
}

export function Compare() {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [resA, setResA] = useState<any>(null)
  const [resB, setResB] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [suggestionsA, setSuggestionsA] = useState<LocationOut[]>([])
  const [suggestionsB, setSuggestionsB] = useState<LocationOut[]>([])
  const [focusA, setFocusA] = useState(false)
  const [focusB, setFocusB] = useState(false)

  // Live suggestions
  useEffect(() => {
    if (a.trim().length < 2) { setSuggestionsA([]); return }
    const id = setTimeout(async () => {
      try {
        const locs = await api.get<LocationOut[]>(`/locations/search?q=${encodeURIComponent(a)}&state=${encodeURIComponent('Tamil Nadu')}&limit=5`)
        setSuggestionsA(locs)
      } catch { setSuggestionsA([]) }
    }, 300)
    return () => clearTimeout(id)
  }, [a])
  useEffect(() => {
    if (b.trim().length < 2) { setSuggestionsB([]); return }
    const id = setTimeout(async () => {
      try {
        const locs = await api.get<LocationOut[]>(`/locations/search?q=${encodeURIComponent(b)}&state=${encodeURIComponent('Tamil Nadu')}&limit=5`)
        setSuggestionsB(locs)
      } catch { setSuggestionsB([]) }
    }, 300)
    return () => clearTimeout(id)
  }, [b])

  const run = async () => {
    if (!a.trim() || !b.trim()) return
    if (a.trim().toLowerCase() === b.trim().toLowerCase()) { setError('Pick two different villages.'); return }
    setSuggestionsA([]); setSuggestionsB([]);
    setLoading(true); setError(null)
    try {
      const [pa, pb] = await Promise.all([resolveVillage(a), resolveVillage(b)])
      const [ra, rb] = await Promise.all([
        api.post<any>('/analysis', pa.payload),
        api.post<any>('/analysis', pb.payload),
      ])
      setResA(ra); setResB(rb)
    } catch (e: any) { setError(e?.message || 'Comparison failed — check village names and try again.') }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Client • Compare" title="Village Compare" desc="Put two villages side-by-side: opportunity, competition, and financial fit. All scores are deterministic, never invented." />
      <Card>
        <CardHeader title="Pick two villages" subtitle="Try Perundurai vs Bhavani, or Pethampalayam vs Nallampatti" />
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] items-end">
          <label className="block relative">
            <span className="text-xs font-medium text-slate-600">Village A</span>
            <input value={a} onChange={e=>setA(e.target.value)} onFocus={()=>setFocusA(true)} onBlur={()=>setTimeout(()=>setFocusA(false),150)} onKeyDown={e=> e.key==='Enter' && run()} placeholder="e.g. Perundurai" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" data-testid="compare-a" />
            {focusA && suggestionsA.length > 0 && (
              <div className="relative z-20 mt-1 max-h-40 overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg">
                {suggestionsA.map(loc => (
                  <button key={loc.id} onMouseDown={e=>e.preventDefault()} onClick={() => { setA((loc.village || loc.block) || ''); setSuggestionsA([]) }} className="w-full px-3 py-2 text-left text-xs hover:bg-slate-50">{loc.village || loc.block} · {loc.block}, {loc.district}</button>
                ))}
              </div>
            )}
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Village B</span>
            <input value={b} onChange={e=>setB(e.target.value)} onFocus={()=>setFocusB(true)} onBlur={()=>setTimeout(()=>setFocusB(false),150)} onKeyDown={e=> e.key==='Enter' && run()} placeholder="e.g. Bhavani" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" data-testid="compare-b" />
            {focusB && suggestionsB.length > 0 && (
              <div className="relative z-20 mt-1 max-h-40 overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg">
                {suggestionsB.map(loc => (
                  <button key={loc.id} onMouseDown={e=>e.preventDefault()} onClick={() => { setB((loc.village || loc.block) || ''); setSuggestionsB([]) }} className="w-full px-3 py-2 text-left text-xs hover:bg-slate-50">{loc.village || loc.block} · {loc.block}, {loc.district}</button>
                ))}
              </div>
            )}
          </label>
          <button onClick={run} disabled={loading || !a.trim() || !b.trim()} className="relative z-30 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50" data-testid="compare-run">{loading ? 'Comparing…' : 'Compare'}</button>
        </div>
        <p className="mt-2 text-xs text-slate-500">Tip: Use exact village names from the Analyze picker (593 villages now live for Erode).</p>
        {error && <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700" data-testid="compare-error">{error}</div>}
      </Card>

      {resA && resB && (
        <div className="grid gap-4 md:grid-cols-2">
          {[resA,resB].map((r,i)=>(
            <Card key={i} className="p-5">
              <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Village {i===0?'A':'B'} • {r.location.village}, {r.location.block}</div>
              <div className="mt-2 flex items-center gap-3">
                <div className="text-3xl font-extrabold">{r.opportunity_score.overall_score}</div>
                <Badge color={r.recommendation.label==='GO'?'green':r.recommendation.label==='MODIFY'?'amber':'red'}>{r.recommendation.label}</Badge>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-slate-50 p-2"><span className="text-slate-500">Competition 5km</span><div className="font-bold text-slate-900">{r.business_competition.mapped_competitors_5km}</div></div>
                <div className="rounded-lg bg-slate-50 p-2"><span className="text-slate-500">Project cost</span><div className="font-bold text-slate-900">₹{formatINR(r.financial_plan.project_cost)}</div></div>
                <div className="rounded-lg bg-slate-50 p-2"><span className="text-slate-500">Demand</span><div className="font-bold text-slate-900">{r.opportunity_score.demand_score}</div></div>
                <div className="rounded-lg bg-slate-50 p-2"><span className="text-slate-500">Risk</span><div className="font-bold text-slate-900">{r.opportunity_score.risk_score}</div></div>
              </div>
              <p className="mt-3 text-xs text-slate-600">{r.recommendation.reason}</p>
            </Card>
          ))}
        </div>
      )}

      {!resA && !resB && !loading && !error && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500">
          As a client you want to know: <em>where</em> is the better bet. Pick two villages above and see the evidence side-by-side.
        </div>
      )}
    </div>
  )
}
