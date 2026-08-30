import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Badge, Disclaimer } from '../components/ui'
import { formatINR } from './Dashboard'

interface Scheme {
  code: string
  name: string
  min_project_cost?: number | null
  max_project_cost?: number | null
  max_loan_amount?: number | null
  interest_rate?: number | null
  tenure_years?: number | null
  moratorium_months?: number | null
  moratorium_mode?: string
  source_document?: string | null
  source_date?: string | null
  note?: string | null
}

export function Schemes() {
  const { result } = useAnalysis()
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [note, setNote] = useState('')
  const projectCost = result?.financial_plan?.project_cost

  useEffect(() => {
    api
      .get<{ schemes: Scheme[]; note: string }>('/schemes')
      .then((r) => {
        setSchemes(r.schemes)
        setNote(r.note)
      })
      .catch(() => setSchemes([]))
  }, [])

  const routed = schemes.length > 0 && projectCost != null ? route(projectCost, schemes) : null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Government Schemes</h1>
        <p className="text-sm text-gray-500">{note}</p>
      </div>

      {projectCost != null && routed && (
        <div className="rounded-xl border border-brand-200 bg-brand-50 p-4 text-sm text-brand-800">
          <strong>For your project cost ₹{formatINR(projectCost)}:</strong> routed to{' '}
          <strong>{routed.scheme?.name || 'no supported scheme'}</strong> — {routed.reason}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full rounded-xl border border-gray-200 bg-white text-sm shadow-sm">
          <thead>
            <tr className="border-b text-left text-xs text-gray-500">
              <th className="px-4 py-3">Scheme</th>
              <th className="px-4 py-3">Project range</th>
              <th className="px-4 py-3">Max loan</th>
              <th className="px-4 py-3">Rate</th>
              <th className="px-4 py-3">Tenure</th>
              <th className="px-4 py-3">Moratorium</th>
              <th className="px-4 py-3">Covers you?</th>
            </tr>
          </thead>
          <tbody>
            {schemes.map((s) => {
              const lo = s.min_project_cost ?? -Infinity
              const hi = s.max_project_cost ?? Infinity
              const covers = projectCost != null && projectCost >= lo && projectCost <= hi
              return (
                <tr key={s.code} className="border-b border-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-gray-900">{s.name}</div>
                    <div className="text-xs text-gray-400">{s.code} · {s.source_document || ''}</div>
                  </td>
                  <td className="px-4 py-3 text-gray-700">
                    {s.min_project_cost != null ? `₹${formatINR(s.min_project_cost)}` : '—'} – {s.max_project_cost != null ? `₹${formatINR(s.max_project_cost)}` : '∞'}
                  </td>
                  <td className="px-4 py-3">{s.max_loan_amount != null ? `₹${formatINR(s.max_loan_amount)}` : '—'}</td>
                  <td className="px-4 py-3">{s.interest_rate != null ? `${s.interest_rate}%` : '—'}</td>
                  <td className="px-4 py-3">{s.tenure_years != null ? `${s.tenure_years} yr` : '—'}</td>
                  <td className="px-4 py-3">{s.moratorium_months != null ? `${s.moratorium_months} mo (${s.moratorium_mode || ''})` : '—'}</td>
                  <td className="px-4 py-3">
                    {projectCost != null ? (
                      covers ? <Badge color="green">Yes</Badge> : <Badge color="gray">No</Badge>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <Disclaimer>Scheme parameters shown are demo assumptions based on the problem statement and must be verified with the relevant government agency before use.</Disclaimer>
    </div>
  )
}

function route(projectCost: number, schemes: Scheme[]) {
  for (const s of schemes) {
    const lo = s.min_project_cost ?? -Infinity
    const hi = s.max_project_cost ?? Infinity
    if (projectCost >= lo && projectCost <= hi) {
      return { scheme: s, reason: `Project cost ₹${projectCost.toLocaleString('en-IN')} lies within the ${s.name} range.` }
    }
  }
  return { scheme: null as Scheme | null, reason: 'No supported scheme covers this project cost.' }
}
