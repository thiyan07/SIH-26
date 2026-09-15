import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { tr } from '../lib/i18n'
import { Card, CardHeader } from '../components/ui'

export function Health() {
  const { lang } = useAnalysis()
  const { id } = useParams()
  const [history, setHistory] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    if (!id) return
    api.get<any[]>(`/user/businesses/${id}/health/history`).then(setHistory).catch(()=>{}).finally(()=>setLoading(false))
  }, [id])
  if (!id) return null
  const latest = history[history.length-1]
  const prev = history[history.length-2]
  const change = latest && prev ? latest.score - prev.score : null
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title={tr('healthTitle', lang)} subtitle={tr('healthSubtitle', lang)} />
        {loading ? <p className="p-4 text-sm text-gray-500">Loading…</p> : history.length===0 ? <p className="p-4 text-sm text-gray-500">No health snapshots yet. Add a metric and click “Recalculate Health”.</p> : (
          <>
            <div className="grid gap-4 p-4 sm:grid-cols-3">
              <div className="rounded-xl bg-brand-50 p-4 text-center">
                <div className="text-xs uppercase text-gray-500">Current</div><div className="text-3xl font-black text-brand-700">{latest.score}</div><div className="text-xs text-gray-500">{latest.as_of}</div>
              </div>
              <div className="rounded-xl bg-gray-50 p-4 text-center">
                <div className="text-xs uppercase text-gray-500">Previous</div><div className="text-2xl font-bold text-gray-700">{prev ? prev.score : '—'}</div>
              </div>
              <div className="rounded-xl bg-amber-50 p-4 text-center">
                <div className="text-xs uppercase text-gray-500">Change</div><div className={`text-2xl font-bold ${change!=null && change<0 ? 'text-red-600' : 'text-green-600'}`}>{change!=null ? (change>0?`+${change}`:change) : '—'}</div>
              </div>
            </div>
            {latest && <div className="mx-4 rounded-lg bg-gray-50 p-3 text-xs text-gray-700"><strong>Why:</strong> {latest.explanation} <br/><strong>Drivers:</strong> {latest.drivers?.join(' · ')}</div>}
            <div className="p-4">
              <h4 className="text-xs font-semibold uppercase text-gray-500">History</h4>
              <ul className="mt-2 divide-y divide-gray-100">
                {history.map((h:any) => (
                  <li key={h.id} className="flex justify-between py-2 text-sm"><span>{h.as_of} · {h.score}</span><span className="text-xs text-gray-500">{h.drivers?.[0] || ''}</span></li>
                ))}
              </ul>
            </div>
          </>
        )}
      </Card>
      <Link to={`/businesses/${id}/profile`} className="text-sm text-brand-600 underline">← Back to Business</Link>
    </div>
  )
}
