import { useEffect, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { Card, Badge } from '../components/ui'
import { useAnalysis } from '../lib/analysisStore'

type Run = { analysis_id: string; state: string; district: string; block: string; village: string; category_code: string; language: string; created_at: string; result?: any }

export function History() {
  const { setResult } = useAnalysis()
  const [rows, setRows] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_URL || ''}/analysis/list?limit=20`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((j: any) => setRows(j.runs || j || []))
      .catch(() => {
        // Fallback to localStorage single entry
        try {
          const raw = localStorage.getItem('grambiz.last.analysis')
          if (raw) {
            const one = JSON.parse(raw)
            setRows([{ analysis_id: one.analysis_id || 'local', state: one.location.state, district: one.location.district, block: one.location.block, village: one.location.village, category_code: one.profit_model?.category_code || '—', language: 'en', created_at: new Date().toISOString(), result: one }])
          }
        } catch {}
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Client • History" title="Saved Analyses" desc="Every report you generated — village, category, score and loan — kept for the client to revisit and share." />
      {loading ? <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-400">Loading…</div> : rows.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="text-3xl">📂</div>
          <div className="mt-2 text-sm font-bold text-slate-900">No history yet</div>
          <p className="mx-auto mt-1 max-w-md text-xs text-slate-500">As a client you expect a ledger. Run an analysis from Analyze — it will appear here with village, date and score for future reference.</p>
          <a href="/analyze" className="mt-4 inline-flex rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white">Go to Analyze →</a>
        </Card>
      ) : (
        <div className="grid gap-3">
          {rows.map(r => (
            <Card key={r.analysis_id} className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-bold text-slate-900">{r.village || r.block} • {r.district}, {r.state}</div>
                  <div className="text-xs text-slate-500">{r.category_code} • {r.language} • {new Date(r.created_at).toLocaleString()}</div>
                </div>
                <div className="flex gap-2">
                  {r.result?.opportunity_score && <Badge color="brand">{r.result.opportunity_score.overall_score}/100</Badge>}
                  {r.result?.recommendation && <Badge color={r.result.recommendation.label==='GO'?'green':r.result.recommendation.label==='MODIFY'?'amber':'red'}>{r.result.recommendation.label}</Badge>}
                  {r.result && <button onClick={() => { setResult(r.result); location.href='/dashboard' }} className="rounded-xl bg-brand-600 px-3 py-1 text-xs font-bold text-white">Open →</button>}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <a href="/compare" className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold">Compare villages →</a>
        <button onClick={()=>{ localStorage.removeItem('grambiz.last.analysis'); location.reload() }} className="rounded-xl bg-slate-100 px-4 py-2 text-xs font-semibold">Clear local history</button>
      </div>
    </div>
  )
}
