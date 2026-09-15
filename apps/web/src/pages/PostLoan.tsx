import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { Card, CardHeader } from '../components/ui'
import { useAuth } from '../lib/auth'

export function PostLoan() {
  const { isAuthenticated } = useAuth()
  const nav = useNavigate()
  const [businesses, setBusinesses] = useState<any[]>([])
  const [reports, setReports] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return }
    Promise.all([
      api.get<any[]>('/user/businesses').catch(() => []),
      api.get<any[]>('/user/pre-loan-reports').catch(() => []),
    ]).then(([b, r]) => { setBusinesses(b); setReports(r) }).finally(() => setLoading(false))
  }, [isAuthenticated])

  if (!isAuthenticated) {
    return (
      <div className="mx-auto max-w-md py-20 text-center">
        <p className="text-sm text-gray-500">Please log in to access Post-Loan.</p>
        <Link to="/login" state={{ next: '/post-loan' }} className="mt-4 inline-block rounded-lg bg-brand-600 px-5 py-2 text-sm text-white">Log in</Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Post-Loan" subtitle="Select a business to continue — your Pre-Loan report, loan status, and business type" />
        {loading ? <p className="p-4 text-sm text-gray-500">Loading…</p> : (
          <>
            <div className="p-4">
              <h3 className="text-sm font-semibold text-gray-900">My Businesses</h3>
              {businesses.length === 0 ? <p className="text-xs text-gray-500">No businesses yet. <Link to="/businesses" className="underline">Create one</Link> or save a report from Dashboard.</p> : (
                <ul className="mt-2 divide-y divide-gray-100 rounded-lg border">
                  {businesses.map((b: any) => (
                    <li key={b.id} className="flex items-center justify-between p-3">
                      <div><div className="font-medium text-gray-900">{b.name}</div><div className="text-xs text-gray-500">{b.category_code} · {b.address || 'No location'}</div></div>
                      <button onClick={() => nav(`/businesses/${b.id}/profile`)} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold hover:bg-slate-50">Open</button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="p-4">
              <h3 className="text-sm font-semibold text-gray-900">My Pre-Loan Reports</h3>
              {reports.length === 0 ? <p className="text-xs text-gray-500">No saved reports. <Link to="/reports" className="underline">View reports</Link></p> : (
                <ul className="mt-2 divide-y divide-gray-100 rounded-lg border">
                  {reports.map((r: any) => (
                    <li key={r.id} className="flex items-center justify-between p-3">
                      <div><div className="font-medium text-gray-900 truncate">{r.title || r.business_type}</div><div className="text-xs text-gray-500">v{r.report_version} · {new Date(r.created_at).toLocaleDateString()}</div></div>
                      <Link to={`/businesses/${r.business_id || ''}/profile`} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold hover:bg-slate-50">Use for Post-Loan</Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="p-4 rounded-lg bg-amber-50 text-xs text-amber-800">
              Next: <strong>Did you take a bank loan?</strong> → If yes, you’ll be asked to upload sanction/statement (optional) and confirm details. If no, continue without loan info.
            </div>
          </>
        )}
      </Card>
      <div className="flex gap-2">
        <Link to="/businesses" className="rounded-xl border border-slate-200 bg-white px-5 py-2 text-sm font-bold">My Businesses</Link>
        <Link to="/reports" className="rounded-xl bg-brand-600 px-5 py-2 text-sm font-bold text-white">My Reports</Link>
      </div>
    </div>
  )
}
