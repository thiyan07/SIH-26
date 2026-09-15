import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { tr } from '../lib/i18n'
import { Card, CardHeader } from '../components/ui'

export function Scenarios() {
  const { lang } = useAnalysis()
  const { id } = useParams()
  const [overrides, setOverrides] = useState('{"revenue_pct": -20}')
  const [result, setResult] = useState<any>(null)
  const run = async (kind: string) => {
    if (!id) return
    let ov: any = {}
    try { ov = JSON.parse(overrides) } catch {}
    if (kind==='BASELINE') ov={}
    if (kind==='OPTIMISTIC') ov={revenue_pct:20}
    if (kind==='PESSIMISTIC') ov={revenue_pct:-20}
    const r: any = await api.post(`/user/businesses/${id}/scenarios`, { kind, overrides: ov })
    setResult(r.results)
  }
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title={tr('scenarioTitle', lang)} subtitle={tr('scenarioSubtitle', lang)} />
        <div className="p-4 flex flex-wrap gap-2">
          <button onClick={()=>run('BASELINE')} className="rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white">Baseline</button>
          <button onClick={()=>run('OPTIMISTIC')} className="rounded-xl bg-green-600 px-4 py-2 text-xs font-bold text-white">Optimistic +20%</button>
          <button onClick={()=>run('PESSIMISTIC')} className="rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold text-white">Pessimistic -20%</button>
        </div>
        <div className="p-4">
          <label className="text-xs font-semibold">Custom overrides JSON</label>
          <textarea value={overrides} onChange={e=>setOverrides(e.target.value)} rows={3} className="mt-1 w-full rounded-lg border px-3 py-2 font-mono text-xs" />
          <button onClick={()=>run('CUSTOM')} className="mt-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold">Run Custom</button>
        </div>
        {result && (
          <div className="p-4 rounded-lg bg-gray-50">
            <div className="text-xs font-semibold">Results (isolated)</div>
            <pre className="mt-2 overflow-auto rounded bg-white p-3 text-xs">{JSON.stringify(result, null, 2)}</pre>
            <p className="mt-2 text-xs text-gray-500">Health {result.business_health?.score} · EMI coverage {result.emi_coverage} · {result.repayment_risk}</p>
          </div>
        )}
      </Card>
    </div>
  )
}
