import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Card, CardHeader } from '../components/ui'
import { useAuth } from '../lib/auth'
import { useAnalysis } from '../lib/analysisStore'

interface Report {
  id: string
  business_type: string | null
  title: string | null
  location_id: string | null
  report_version: number
  created_at: string | null
  financial_snapshot: any
  opportunity_snapshot: any
}

export function MyReports() {
  const { isAuthenticated } = useAuth()
  const { setResult } = useAnalysis()
  const [items, setItems] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const nav = useNavigate()

  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return }
    api.get<Report[]>('/user/pre-loan-reports').then(setItems).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [isAuthenticated])

  const openReport = async (id: string) => {
    try {
      const r: any = await api.get(`/user/pre-loan-reports/${id}`)
      // Fetch the original analysis_run result for full dashboard (fallback to snapshots)
      if (r.analysis_run_id) {
        const ar: any = await api.get(`/analysis/${r.analysis_run_id}`)
        if (ar.result) {
          setResult(ar.result)
          nav('/dashboard')
          return
        }
      }
      // Fallback — show snapshots
      alert(`Report ${r.title || r.id} — structured snapshots available. Full report view coming in Phase 2.`)
    } catch (e: any) {
      setError(e.message)
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="mx-auto max-w-md py-20 text-center">
        <p className="text-sm text-gray-500">Please log in to see your reports.</p>
        <Link to="/login" className="mt-4 inline-block rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white">Log in</Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="My Pre-Loan Reports" subtitle={`${items.length} report${items.length !== 1 ? 's' : ''} — versioned, reproducible`} />
        {loading ? <p className="p-4 text-sm text-gray-500">Loading…</p> : error ? <p className="p-4 text-sm text-red-600">{error}</p> : items.length === 0 ? (
          <p className="p-4 text-sm text-gray-500">No saved reports yet. Run an analysis and click “Save Report”.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {items.map(r => (
              <li key={r.id} className="flex items-center justify-between p-4 hover:bg-gray-50">
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-gray-900 truncate">{r.title || r.business_type || 'Report'}</div>
                  <div className="text-xs text-gray-500">v{r.report_version} · {r.business_type || '—'} · {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}</div>
                </div>
                <button onClick={() => openReport(r.id)} className="ml-3 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold hover:bg-slate-50">Open</button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
