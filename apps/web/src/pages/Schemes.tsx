import React, { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { Badge, Disclaimer } from '../components/ui'
import { Spotlight } from '../components/aceternity/BackgroundBeams'
import { Card3D } from '../components/aceternity/Card3D'
import { tr, interpolate, type Language } from '../lib/i18n'
import { formatINR } from './Dashboard'

interface Scheme {
  code: string
  name: string
  description?: string | null
  implementing_agency?: string | null
  scheme_url?: string | null
  scheme_type?: string | null
  min_project_cost?: number | null
  max_project_cost?: number | null
  max_loan_amount?: number | null
  interest_rate?: number | null
  tenure_years?: number | null
  moratorium_months?: number | null
  moratorium_mode?: string
  margin_pct?: number | null
  beneficiary_contribution_pct?: number | null
  subsidy_pct?: number | null
  eligible_business_types?: string[] | null
  eligible_states?: string[] | null
  eligible_districts?: string[] | null
  target_beneficiary_categories?: string[] | null
  min_age?: number | null
  max_age?: number | null
  min_annual_income?: number | null
  max_annual_income?: number | null
  requires_existing_business?: boolean | null
  requires_domicile?: boolean | null
  category_eligibility_rules?: Record<string, string> | null
  required_documents?: string[] | null
  application_authority?: string | null
  application_process?: string | null
  source_document?: string | null
  source_date?: string | null
  note?: string | null
  confidence_level?: string | null
}

export function Schemes() {
  const { result, lang } = useAnalysis()
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [note, setNote] = useState('')
  const [matches, setMatches] = useState<any[]>([])
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

  useEffect(() => {
    if (result?.location) {
      api.post<{ matches: any[] }>('/advisory/schemes/match', {
        state: result.location.state,
        district: result.location.district,
        block: result.location.block,
        village: result.location.village,
        business_type: (result.profit_model as any)?.category_code || result.financial_plan?.scheme_code,
        project_cost: projectCost,
        capital_available: result.financial_plan?.capital_available,
      }).then((r) => setMatches(r.matches || [])).catch(() => {})
    }
  }, [result?.location?.block, result?.location?.village, projectCost])

  const routed = schemes.length > 0 && projectCost != null ? route(projectCost, schemes, lang) : null
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <div className="space-y-6">
      <Spotlight>
        <div className="rounded-xl border border-teal-100 bg-gradient-to-br from-white to-teal-50/40 p-4">
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">{tr('govtSchemes', lang)}</h1>
          <p className="mt-1 text-sm text-gray-500">{note} · {schemes.length} schemes · All eligibility requirements shown — click any scheme for details.</p>
        </div>
      </Spotlight>

      {projectCost != null && routed && (
        <Card3D>
          <div className="rounded-xl border border-teal-200 bg-gradient-to-br from-teal-50 to-cyan-50 p-4 text-sm text-teal-900 shadow-sm">
            <strong>{interpolate(tr('forProjectCost', lang), { cost: `₹${formatINR(projectCost)}` })}</strong> {tr('routedTo', lang)}{' '}
            <strong>{routed.scheme?.name || tr('noSupportedScheme', lang)}</strong> — {routed.reason}
          </div>
        </Card3D>
      )}

      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-gray-500">
              <th className="px-4 py-3">{tr('schemeHeader', lang)}</th>
              <th className="px-4 py-3">{tr('projectRange', lang)}</th>
              <th className="px-4 py-3">{tr('maxLoan', lang)}</th>
              <th className="px-4 py-3">{tr('rate', lang)}</th>
              <th className="px-4 py-3">{tr('tenure', lang)}</th>
              <th className="px-4 py-3">{tr('moratorium', lang)}</th>
              <th className="px-4 py-3">{tr('coversYou', lang)}</th>
            </tr>
          </thead>
          <tbody>
            {schemes.map((s) => {
              const lo = s.min_project_cost ?? -Infinity
              const hi = s.max_project_cost ?? Infinity
              const covers = projectCost != null && projectCost >= lo && projectCost <= hi
              const m = matches.find((x) => x.scheme_code === s.code)
              const isExpanded = expanded === s.code
              return (
                <React.Fragment key={s.code}>
                  <tr className={`border-b border-gray-50 cursor-pointer hover:bg-gray-50 ${m?.status === 'ELIGIBLE' ? 'bg-emerald-50' : ''} ${isExpanded ? 'bg-brand-50' : ''}`} onClick={() => setExpanded(isExpanded ? null : s.code)}>
                    <td className="px-4 py-3">
                      <div className="font-semibold text-gray-900 flex items-center gap-1.5">{s.name} {m?.status === 'ELIGIBLE' ? <Badge color="green">Eligible</Badge> : m?.status === 'PARTIALLY_ELIGIBLE' ? <Badge color="amber">Partial</Badge> : null} <span className="text-xs text-gray-400">{isExpanded ? '▼' : '▶'}</span></div>
                      <div className="text-xs text-gray-400">{s.code} · {s.scheme_type || ''} {m ? `· ${m.match_score}%` : ''} {s.confidence_level ? `· ${s.confidence_level}` : ''}</div>
                      {s.description && <div className="text-xs text-gray-500 mt-0.5 line-clamp-1">{s.description.slice(0, 90)}...</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {s.min_project_cost != null ? `₹${formatINR(s.min_project_cost)}` : '—'} – {s.max_project_cost != null ? `₹${formatINR(s.max_project_cost)}` : '∞'}
                    </td>
                    <td className="px-4 py-3">{s.max_loan_amount != null ? `₹${formatINR(s.max_loan_amount)}` : '—'}</td>
                    <td className="px-4 py-3">{s.interest_rate != null ? `${s.interest_rate}%` : '—'}</td>
                    <td className="px-4 py-3">{s.tenure_years != null ? `${s.tenure_years} ${tr('yr', lang)}` : '—'}</td>
                    <td className="px-4 py-3">{s.moratorium_months != null ? `${s.moratorium_months} ${tr('mo', lang)}` : '—'}</td>
                    <td className="px-4 py-3">
                      {projectCost != null ? (
                        m ? (m.status === 'ELIGIBLE' ? <Badge color="green">{tr('yes', lang)} {m.match_score}%</Badge> : <Badge color={m.status === 'PARTIALLY_ELIGIBLE' ? 'amber' : 'gray'}>{m.status.slice(0,3)} {m.match_score}%</Badge>) : covers ? <Badge color="green">{tr('yes', lang)}</Badge> : <Badge color="gray">{tr('no', lang)}</Badge>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="bg-gray-50">
                      <td colSpan={7} className="px-4 py-4">
                        <div className="grid gap-3 md:grid-cols-2 text-xs">
                          <div className="space-y-2">
                            <div><span className="font-semibold">Eligible Business Types:</span> {s.eligible_business_types ? s.eligible_business_types.slice(0,8).join(', ') + (s.eligible_business_types.length>8 ? ` +${s.eligible_business_types.length-8}` : '') : 'All types'}</div>
                            <div><span className="font-semibold">Beneficiary Categories:</span> {s.target_beneficiary_categories ? s.target_beneficiary_categories.join(', ') : 'All'}</div>
                            <div><span className="font-semibold">Age:</span> {s.min_age != null || s.max_age != null ? `${s.min_age ?? 'any'} – ${s.max_age ?? 'any'} years` : 'No restriction'}</div>
                            <div><span className="font-semibold">Income:</span> {(s.min_annual_income != null || s.max_annual_income != null) ? `₹${s.min_annual_income ? formatINR(s.min_annual_income) : 'any'} – ₹${s.max_annual_income ? formatINR(s.max_annual_income) : 'any'}` : 'No restriction'}</div>
                            <div><span className="font-semibold">Domicile/Existing:</span> {s.requires_domicile ? 'Domicile required' : 'No domicile'} · {s.requires_existing_business ? 'Existing business required' : s.requires_existing_business === false ? 'New business only' : 'Any'}</div>
                            {s.category_eligibility_rules && Object.keys(s.category_eligibility_rules).length>0 && <div><span className="font-semibold">Special Rules:</span> {Object.entries(s.category_eligibility_rules).map(([k,v]) => `${k}: ${v}`).join(' · ')}</div>}
                          </div>
                          <div className="space-y-2">
                            <div><span className="font-semibold">Required Documents:</span> {s.required_documents ? s.required_documents.join(' · ') : '—'}</div>
                            <div><span className="font-semibold">Implementing Agency:</span> {s.implementing_agency || '—'}</div>
                            <div><span className="font-semibold">Apply At:</span> {s.application_authority || '—'}</div>
                            <div className="text-gray-600">{s.application_process || ''}</div>
                            {s.scheme_url && <div><a href={s.scheme_url} target="_blank" rel="noopener" className="text-brand-600 underline">{s.scheme_url}</a></div>}
                            {m && m.mismatch_reasons?.length>0 && <div className="text-amber-700"><span className="font-semibold">Why not eligible:</span> {m.mismatch_reasons.join(' · ')}</div>}
                            {m && m.missing_information?.length>0 && <div className="text-gray-500"><span className="font-semibold">Missing info:</span> {m.missing_information.join(' · ')}</div>}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      <Disclaimer>{tr('schemesDisclaimer', lang)}</Disclaimer>
    </div>
  )
}

function route(projectCost: number, schemes: Scheme[], lang: Language) {
  for (const s of schemes) {
    const lo = s.min_project_cost ?? -Infinity
    const hi = s.max_project_cost ?? Infinity
    if (projectCost >= lo && projectCost <= hi) {
      return { scheme: s, reason: interpolate(tr('projectCostRange', lang), { cost: projectCost.toLocaleString('en-IN'), name: s.name }) }
    }
  }
  return { scheme: null as Scheme | null, reason: tr('noSchemeCovers', lang) }
}
