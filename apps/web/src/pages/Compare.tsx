import { useState } from 'react'
import { api } from '../lib/api'
import { Card, CardHeader, Badge } from '../components/ui'
import { PageHeader } from '../components/PageHeader'
import { formatINR } from './Dashboard'

export function Compare() {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [resA, setResA] = useState<any>(null)
  const [resB, setResB] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    if (!a || !b) return
    setLoading(true)
    try {
      const [ra, rb] = await Promise.all([
        api.post<any>('/analysis', { state: 'Tamil Nadu', district: 'Erode', block: a, village: a, capital_available: 100000, category_code: 'grocery' }),
        api.post<any>('/analysis', { state: 'Tamil Nadu', district: 'Erode', block: b, village: b, capital_available: 100000, category_code: 'grocery' }),
      ])
      setResA(ra); setResB(rb)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Client • Compare" title="Village Compare" desc="Put two villages side-by-side: opportunity, competition, and financial fit. All scores are deterministic, never invented." />
      <Card>
        <CardHeader title="Pick two villages" subtitle="Try Perundurai vs Bhavani, or Pethampalayam vs Nallampatti" />
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] items-end">
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Village A</span>
            <input value={a} onChange={e=>setA(e.target.value)} placeholder="e.g. Perundurai" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-600">Village B</span>
            <input value={b} onChange={e=>setB(e.target.value)} placeholder="e.g. Bhavani" className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
          </label>
          <button onClick={run} disabled={loading || !a || !b} className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50">{loading ? 'Comparing…' : 'Compare'}</button>
        </div>
        <p className="mt-2 text-xs text-slate-500">Tip: Use exact village names from the Analyze picker (593 villages now live for Erode).</p>
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

      {!resA && (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500">
          As a client you want to know: <em>where</em> is the better bet. Pick two villages above and see the evidence side-by-side.
        </div>
      )}
    </div>
  )
}
