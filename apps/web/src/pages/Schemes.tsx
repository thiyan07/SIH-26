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
  const { result, setResult, form, lang, selectedSchemeCode, setSelectedSchemeCode } = useAnalysis()
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [note, setNote] = useState('')
  const [matches, setMatches] = useState<any[]>([])
  const [selecting, setSelecting] = useState<string | null>(null)
  const [selectError, setSelectError] = useState<string | null>(null)
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result?.location?.block, result?.location?.village, projectCost])

  const routed = schemes.length > 0 && projectCost != null ? route(projectCost, schemes, lang) : null
  const [expanded, setExpanded] = useState<string | null>(null)

  const handleSelectScheme = async (code: string) => {
    if (!result || !form) {
      setSelectedSchemeCode(code)
      return
    }
    setSelecting(code)
    setSelectError(null)
    try {
      const payload: any = {
        ...form,
        preferred_scheme_code: code,
        // Ensure location + category are present
        state: (form as any).state || result.location.state,
        district: (form as any).district || result.location.district,
        block: (form as any).block || result.location.block,
        village: (form as any).village || result.location.village,
        capital_available: (form as any).capital_available || result.financial_plan.capital_available,
        category_code: (form as any).category_code || (result as any).profit_model?.category_code,
      }
      // Preserve proposed location if present in previous result
      if ((result as any).location?.proposed_latitude) {
        payload.proposed_latitude = (result as any).location.proposed_latitude
        payload.proposed_longitude = (result as any).location.proposed_longitude
      }
      const { api } = await import('../lib/api')
      const res = await api.post<any>('/analysis', payload)
      setResult(res)
      setSelectedSchemeCode(code)
    } catch (e: any) {
      setSelectError(e.message || 'Could not apply scheme')
    } finally {
      setSelecting(null)
    }
  }

  const selectedMatch = matches.find((x) => x.scheme_code === selectedSchemeCode)
  const fundingGap = result ? Math.max(0, (result.financial_plan.project_cost - result.financial_plan.capital_available)) : 0

  return (
    <div className="space-y-6">
      <Spotlight>
        <div className="rounded-xl border border-teal-100 bg-gradient-to-br from-white to-teal-50/40 p-4">
          <h1 className="break-words text-2xl font-bold tracking-tight text-gray-900">{tr('govtSchemes', lang)}</h1>
          <p className="mt-1 break-words text-sm leading-relaxed text-gray-500">{note} · {schemes.length} schemes · Select a scheme to drive your finance calculation — eligibility is evaluated honestly.</p>
        </div>
      </Spotlight>

      {selectedSchemeCode && (
        <div className="rounded-xl border border-brand-200 bg-brand-50 p-4 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-brand-900">
            <strong>Selected Scheme:</strong> {selectedMatch?.scheme_name || selectedSchemeCode} {selectedMatch?.status ? <Badge color={selectedMatch.status === 'ELIGIBLE' ? 'green' : selectedMatch.status === 'NOT_ELIGIBLE' ? 'red' : 'amber'}>{selectedMatch.status.replace('_', ' ')}</Badge> : null}
            <span className="ml-2 text-xs text-brand-700">This scheme will drive your Finance calculation (interest, tenure, moratorium, eligible loan).</span>
          </div>
          <div className="flex gap-2">
            <a href="/finance" className="rounded-lg bg-brand-600 px-4 py-1.5 text-xs font-bold text-white hover:bg-brand-700">View Finance →</a>
            <button onClick={() => setSelectedSchemeCode(null)} className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700">Clear</button>
          </div>
        </div>
      )}
      {selectError && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{selectError}</div>}

      {projectCost != null && routed && !selectedSchemeCode && (
        <Card3D>
          <div className="rounded-xl border border-teal-200 bg-gradient-to-br from-teal-50 to-cyan-50 p-4 text-sm text-teal-900 shadow-sm">
            <strong>{interpolate(tr('forProjectCost', lang), { cost: `₹${formatINR(projectCost)}` })}</strong> {tr('routedTo', lang)}{' '}
            <strong>{routed.scheme?.name || tr('noSupportedScheme', lang)}</strong> — {routed.reason}
          </div>
        </Card3D>
      )}
      {result && (
        <div className="rounded-lg bg-slate-900 p-3 text-xs text-white flex flex-wrap gap-4">
          <span>Project: <strong>₹{formatINR(projectCost || 0)}</strong></span>
          <span>Own capital: <strong>₹{formatINR(result.financial_plan.capital_available)}</strong></span>
          <span>Funding gap: <strong>₹{formatINR(fundingGap)}</strong></span>
          <span className="text-white/60">Select a scheme below to see eligible financing</span>
        </div>
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
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {schemes.map((s) => {
              const lo = s.min_project_cost ?? -Infinity
              const hi = s.max_project_cost ?? Infinity
              const covers = projectCost != null && projectCost >= lo && projectCost <= hi
              const m = matches.find((x) => x.scheme_code === s.code)
              const isExpanded = expanded === s.code
              const isSelected = selectedSchemeCode === s.code
              const status = m?.status || (covers ? 'ELIGIBLE' : 'UNKNOWN')
              const statusLabel = status === 'ELIGIBLE' ? 'Eligible' : status === 'PARTIALLY_ELIGIBLE' ? 'Potentially Eligible' : status === 'NOT_ELIGIBLE' ? 'Not Eligible' : status === 'INSUFFICIENT_INFO' ? 'Insufficient Info' : '—'
              const statusColor = status === 'ELIGIBLE' ? 'green' : status === 'NOT_ELIGIBLE' ? 'red' : 'amber'
              // Eligible financing under this scheme for current funding gap
              const eligibleLoan = s.max_loan_amount != null ? Math.min(fundingGap, s.max_loan_amount) : fundingGap
              const shortfall = fundingGap > eligibleLoan ? fundingGap - eligibleLoan : 0
              return (
                <React.Fragment key={s.code}>
                  <tr className={`border-b border-gray-50 hover:bg-gray-50 ${status === 'ELIGIBLE' ? 'bg-emerald-50/50' : ''} ${isSelected ? 'bg-brand-50' : ''} ${isExpanded ? 'bg-brand-50/50' : ''}`}>
                    <td className="px-4 py-3 cursor-pointer" onClick={() => setExpanded(isExpanded ? null : s.code)}>
                      <div className="font-semibold text-gray-900 flex items-center gap-1.5 flex-wrap">{s.name} <Badge color={statusColor}>{statusLabel}</Badge> {isSelected && <Badge color="green">Selected</Badge>} <span className="text-xs text-gray-500">{isExpanded ? '▼' : '▶'}</span></div>
                      <div className="text-xs text-gray-500">{s.code} · {s.scheme_type || ''} {m ? `· ${m.match_score}%` : ''}</div>
                      {shortfall > 0 && <div className="text-[11px] text-amber-700 mt-0.5">₹{formatINR(shortfall)} additional own funding required if selected</div>}
                      {s.description && <div className="text-xs text-gray-500 mt-0.5 line-clamp-1">{s.description.slice(0, 90)}...</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {s.min_project_cost != null ? `₹${formatINR(s.min_project_cost)}` : '—'} – {s.max_project_cost != null ? `₹${formatINR(s.max_project_cost)}` : '∞'}
                    </td>
                    <td className="px-4 py-3"><div>₹{s.max_loan_amount != null ? formatINR(s.max_loan_amount) : '—'}</div>{eligibleLoan !== fundingGap && <div className="text-[11px] text-gray-500">Eligible: ₹{formatINR(eligibleLoan)}</div>}</td>
                    <td className="px-4 py-3">{s.interest_rate != null ? `${s.interest_rate}%` : <span className="text-amber-600 text-xs">Unknown</span>}</td>
                    <td className="px-4 py-3">{s.tenure_years != null ? `${s.tenure_years} ${tr('yr', lang)}` : <span className="text-amber-600 text-xs">Unknown</span>}</td>
                    <td className="px-4 py-3">{s.moratorium_months != null ? `${s.moratorium_months} ${tr('mo', lang)}` : '—'}</td>
                    <td className="px-4 py-3">
                      {projectCost != null ? (
                        m ? <Badge color={statusColor}>{statusLabel} {m.match_score}%</Badge> : covers ? <Badge color="green">Eligible</Badge> : <Badge color="gray">—</Badge>
                      ) : (
                        <span className="text-gray-500">—</span>
                      )}
                      {m?.missing_information?.length ? <div className="text-[11px] text-gray-500 mt-1">Missing: {m.missing_information.slice(0,2).join(', ')}</div> : null}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleSelectScheme(s.code) }}
                        disabled={selecting === s.code || status === 'NOT_ELIGIBLE'}
                        className={`rounded-lg px-3 py-1 text-xs font-bold ${isSelected ? 'bg-brand-600 text-white' : status === 'NOT_ELIGIBLE' ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-slate-900 text-white hover:bg-slate-800'} disabled:opacity-60`}
                        title={status === 'NOT_ELIGIBLE' ? 'Not eligible for this project' : status === 'INSUFFICIENT_INFO' ? 'Potentially eligible — verify applicant criteria' : 'Select to drive finance'}
                      >
                        {selecting === s.code ? 'Applying…' : isSelected ? 'Selected' : 'Select'}
                      </button>
                      {status === 'INSUFFICIENT_INFO' && <div className="text-[10px] text-amber-700 mt-1">Potentially eligible — verify criteria</div>}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="bg-gray-50">
                      <td colSpan={8} className="px-4 py-4">
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
