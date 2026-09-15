import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAnalysis } from '../lib/analysisStore'
import { api } from '../lib/api'
import { Button, Card, CardHeader, Badge } from '../components/ui'
import { ScoreDonut } from '../components/ScoreDonut'
import { formatINR } from './Dashboard'
import { recommendationLabel, tr, interpolate, type Language } from '../lib/i18n'
import { downloadJSON, printElement } from '../lib/export'
import { BusinessMap } from '../components/BusinessMap'

export function Report() {
  const { result, lang, selectedSchemeCode, selectedSchemeName, applicantDetails, setApplicantDetails, eligibilityResult, applicantAge } = useAnalysis()
  const navigate = useNavigate()
  const [aiText, setAiText] = useState<string | null>(null)
  const [loadingAi, setLoadingAi] = useState(false)
  const [formName, setFormName] = useState(applicantDetails?.fullName || "")
  const [formPhone, setFormPhone] = useState(applicantDetails?.phone || "")
  const [formAddress, setFormAddress] = useState(applicantDetails?.houseAddress || "")
  const [formError, setFormError] = useState<string | null>(null)

  const analysisId = (result as any)?.analysis_id
  const cacheRef = useState(() => new Map<string,string>())[0] as Map<string,string>
  const loadReport = async () => {
    if (!result) return
    const key = `${analysisId || 'no-id'}:${lang}`
    if (cacheRef.has(key)) { setAiText(cacheRef.get(key)!); return }
    setLoadingAi(true)
    try {
      const evidence = result as unknown as Record<string, unknown>
      const res = await api.post<{ content: string }>('/ai/report', {
        evidence,
        language: lang,
        ...(analysisId ? { analysis_id: analysisId } : {}),
      })
      const content = res.content || tr('aiUnavailable', lang)
      cacheRef.set(key, content)
      setAiText(content)
    } catch {
      setAiText(tr('aiUnavailable', lang))
    } finally {
      setLoadingAi(false)
    }
  }

  useEffect(() => {
    if (!result) return
    loadReport()
  }, [lang, analysisId])

  const handleSaveApplicant = () => {
    if (!formName.trim()) { setFormError(tr('reportValName', lang)); return }
    if (!/^\d{10}$/.test(formPhone.replace(/\s/g,''))) { setFormError(tr('reportValPhone', lang)); return }
    if (!formAddress.trim()) { setFormError(tr('reportValAddress', lang)); return }
    setFormError(null)
    setApplicantDetails({ fullName: formName.trim(), phone: formPhone.trim(), houseAddress: formAddress.trim() })
  }

  const handleDownloadPDF = () => {
    // Use browser print as PDF - preserves layout, includes map if rendered
    printElement('report-print')
  }

  if (!result) return <Empty lang={lang} />

  const s = result.opportunity_score
  const fp = result.financial_plan as any
  const pm = result.profit_model as any
  const bc = result.business_competition as any
  const rec = result.recommendation as any
  const me = result.monthly_economics as any
  const selectedLoc = result.location
  const uf = (result as any).unified_financial
  const schemeElig = eligibilityResult

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{tr('feasibilityReport', lang)}</h1>
          <p className="text-sm text-gray-500">
            {result.location.village || result.location.block} · {result.location.district}, {result.location.state} — {tr('generatedPrefix', lang)} {new Date().toLocaleDateString()}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={handleDownloadPDF} data-testid="download-pdf">{tr('reportDownloadPdf', lang)}</Button>
          <Button variant="outline" onClick={() => printElement('report-print')} data-testid="print-btn">{tr('printSave', lang)}</Button>
          <Button variant="outline" data-testid="export-json" onClick={() => downloadJSON(`grambiz-report-${Date.now()}.json`, result)}>Export JSON</Button>
        </div>
      </div>

      <div id="report-print" className="space-y-6 print:space-y-4">
        {/* 1. Header */}
        <Card>
          <div className="text-center">
            <h1 className="text-2xl font-black text-slate-900">{tr('reportHeaderTitle', lang)}</h1>
            <p className="mt-1 text-xs text-slate-500">{interpolate(tr('reportDeterministic', lang), { date: new Date().toLocaleDateString() })}</p>
          </div>
        </Card>

        {/* 2. Selected Business Name */}
        <Card>
          <CardHeader title={tr('reportSelectedBusiness', lang)} subtitle={tr('reportReflectsMod', lang)} />
          <div className="text-lg font-bold text-slate-900">{pm?.label || (result as any).profit_model?.category_code || '—'}</div>
          <div className="text-sm text-slate-500">{(result as any).profit_model?.category_code} · {(result as any).cost_breakdown?.scale} scale</div>
        </Card>

        {/* 3. Applicant Details */}
        <Card>
          <CardHeader title={tr('reportApplicantDetails', lang)} subtitle={tr('reportStoredWith', lang)} />
          {applicantDetails ? (
            <div className="space-y-2 text-sm">
              <div><span className="text-slate-500">{tr('reportFullName', lang)}</span> <strong className="text-slate-900">{applicantDetails.fullName}</strong></div>
              <div><span className="text-slate-500">{tr('reportPhone', lang)}</span> <strong className="text-slate-900">{applicantDetails.phone}</strong></div>
              <div><span className="text-slate-500">{tr('reportHouseAddress', lang)}</span> <strong className="text-slate-900">{applicantDetails.houseAddress}</strong></div>
              <button onClick={() => setApplicantDetails(null)} className="mt-2 text-xs text-brand-600 underline">{tr('reportEdit', lang)}</button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <label className="text-xs font-medium text-slate-600">{tr('reportFullNameStar', lang)}</label>
                  <input value={formName} onChange={e=>setFormName(e.target.value)} placeholder={tr('reportPlaceholderName', lang)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid="applicant-name" />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600">{tr('reportPhoneStar', lang)}</label>
                  <input value={formPhone} onChange={e=>setFormPhone(e.target.value)} placeholder={tr('reportPlaceholderPhone', lang)} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid="applicant-phone" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600">{tr('reportHouseAddressStar', lang)}</label>
                <textarea value={formAddress} onChange={e=>setFormAddress(e.target.value)} placeholder={tr('reportPlaceholderAddress', lang)} rows={2} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid="applicant-address" />
              </div>
              {formError && <p className="text-xs text-red-600">{formError}</p>}
              <button onClick={handleSaveApplicant} className="rounded-xl bg-brand-600 px-5 py-2 text-sm font-bold text-white hover:bg-brand-700" data-testid="applicant-save">{tr('reportSaveApplicant', lang)}</button>
            </div>
          )}
        </Card>

        {/* 4. Dashboard Analysis */}
        <Card>
          <CardHeader title={tr('reportDashboardAnalysis', lang)} subtitle={tr('reportConciseOverview', lang)} />
          <div className="flex flex-wrap items-center gap-6">
            <ScoreDonut value={s.overall_score} size={100} />
            <div>
              <div className="text-sm text-slate-600">{interpolate(tr('reportOverallOpp', lang), { score: s.overall_score, confidence: s.confidence_label })}</div>
              <Badge color={rec.label === 'GO' ? 'green' : rec.label === 'MODIFY' ? 'amber' : 'red'}>{recommendationLabel(rec.label, lang)}</Badge>
              <p className="mt-2 text-sm text-slate-600">{rec.reason}</p>
            </div>
          </div>
        </Card>

        {/* 5. Selected Location + Map */}
        <Card>
          <CardHeader title={tr('reportSelectedLocation', lang)} subtitle={`${selectedLoc.village || selectedLoc.block}, ${selectedLoc.district}, ${selectedLoc.state}`} />
          <div className="text-sm text-slate-700">
            <div>{interpolate(tr('reportExact', lang), { lat: Number(selectedLoc.latitude).toFixed(4), lng: Number(selectedLoc.longitude).toFixed(4), type: selectedLoc.uses_proposed_location ? tr('reportProposedPin', lang) : tr('reportCentroid', lang), precision: selectedLoc.geo_precision })}</div>
            <div className="mt-1 text-xs text-slate-500">{tr('reportNeverFabricated', lang)}</div>
          </div>
          <div className="mt-3 h-[300px] overflow-hidden rounded-xl border">
            <BusinessMap center={{ latitude: selectedLoc.latitude, longitude: selectedLoc.longitude }} businesses={bc?.businesses || []} markets={[]} infrastructure={[]} zoom={14} height="300px" />
          </div>
        </Card>

        {/* 6. Market Summary */}
        <Card>
          <CardHeader title={tr('marketSummary', lang)} subtitle={tr('marketSummarySub', lang)} />
          <Rows rows={[
            [tr('competitorsWithin5', lang), bc?.mapped_competitors_5km ?? '—'],
            [tr('additional5to10', lang), bc?.mapped_competitors_5km != null && bc?.mapped_competitors_10km != null ? bc.mapped_competitors_10km - bc.mapped_competitors_5km : '—'],
            [tr('competitorsWithin10', lang), bc?.mapped_competitors_10km ?? '—'],
            [tr('nearestCompetitorRow', lang), bc?.nearest_competitor_km != null ? `${bc.nearest_competitor_km} ${tr('km', lang)} (${bc.nearest_competitor || ''})` : '—'],
          ]} />
        </Card>

        {/* 7. Market Reach */}
        <Card>
          <CardHeader title={tr('marketReach', lang)} subtitle={tr('marketReachSub', lang)} />
          {renderMarketReach(result.market, lang)}
        </Card>

        {/* 8. Data Confidence Score */}
        <Card>
          <CardHeader title={tr('dataConfidenceTitle', lang)} subtitle={tr('dataConfidenceSub', lang)} />
          {renderDataConfidence(result.data_confidence, s, lang)}
        </Card>

        {/* 9. Financial Plan & Profitability */}
        <Card>
          <CardHeader title={tr('reportFinancialProfit', lang)} subtitle={tr('reportStartupLoan', lang)} />
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500">{tr('reportFinancialPlanHeading', lang)}</h4>
              <Rows rows={[
                [tr('projectCost', lang), `₹${formatINR(fp.project_cost)}`],
                [tr('availableCapital', lang), `₹${formatINR(fp.capital_available)}`],
                [tr('ownContribution', lang), `₹${formatINR(fp.own_contribution)}`],
                [tr('loanAmount', lang), `₹${formatINR(fp.loan_amount)}`],
              ]} />
            </div>
            <div>
              <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500">{tr('reportProfitabilityHeading', lang)}</h4>
              <Rows rows={[
                [tr('monthlyRevenue', lang), `₹${formatINR(me?.monthly_revenue ?? pm?.outputs?.monthly_revenue)}`],
                [tr('monthlyCost', lang), `₹${formatINR(me?.opex ?? pm?.outputs?.monthly_cost)}`],
                [tr('operatingProfit', lang), `₹${formatINR(me?.operating_profit ?? pm?.outputs?.operating_profit)}`],
                [tr('breakEvenRevenue', lang), me?.break_even_revenue ? `₹${formatINR(me.break_even_revenue)}` : '—'],
              ]} />
            </div>
          </div>
        </Card>

        {/* 10. EMI Calculation */}
        <Card>
          <CardHeader title={tr('reportEmiTitle', lang)} subtitle={tr('reportDeterministicSchedule', lang)} />
          <Rows rows={[
            [tr('loanAmount', lang), `₹${formatINR(uf?.loan_amount ?? fp.loan_amount)}`],
            [tr('interestRate', lang), `${uf?.interest_rate ?? fp.interest_rate ?? '—'}%`],
            [tr('tenure', lang), `${uf?.tenure_years ?? fp.tenure_years ?? '—'} ${tr('years', lang)}`],
            [tr('monthlyEMI', lang), `₹${formatINR(uf?.emi ?? result.repayment?.monthly_emi ?? fp.emi)}`],
            [tr('reportRepaymentPeriod', lang), `${(uf?.tenure_years ?? fp.tenure_years ?? 0) * 12} ${tr('months', lang)}`],
            [tr('reportMoratorium', lang), fp.moratorium_months ? `${fp.moratorium_months} ${tr('months', lang)} (${fp.moratorium_mode})` : tr('reportNone', lang)],
          ]} />
        </Card>

        {/* 11. Selected Scheme */}
        <Card>
          <CardHeader title={tr('reportSelectedScheme', lang)} subtitle={tr('reportChosenByYou', lang)} />
          {selectedSchemeCode ? (
            <div className="space-y-2 text-sm">
              <div><span className="text-slate-500">{tr('reportSchemeLabel', lang)}</span> <strong className="text-slate-900">{selectedSchemeName || selectedSchemeCode}</strong> {selectedSchemeCode && <span className="text-xs text-slate-500">({selectedSchemeCode})</span>}</div>
              <div><span className="text-slate-500">{tr('reportApplicantAge', lang)}</span> <strong>{applicantAge ?? '—'}</strong></div>
              {schemeElig ? (
                <div>
                  <div>{tr('reportEligibility', lang)} <Badge color={schemeElig.status === 'ELIGIBLE' ? 'green' : schemeElig.status === 'NOT_ELIGIBLE' ? 'red' : 'amber'}>{schemeElig.status?.replace('_',' ')}</Badge></div>
                  {schemeElig.matching_reasons?.length > 0 && <div className="mt-1 text-xs text-green-700">✓ {schemeElig.matching_reasons.slice(0,3).join(' · ')}</div>}
                  {schemeElig.mismatch_reasons?.length > 0 && <div className="text-xs text-red-700">✗ {schemeElig.mismatch_reasons.slice(0,3).join(' · ')}</div>}
                  {schemeElig.missing_information?.length > 0 && <div className="text-xs text-amber-700">{tr('schemesMissingColon', lang)} {schemeElig.missing_information.slice(0,3).join(' · ')}</div>}
                </div>
              ) : (
                <p className="text-xs text-amber-600">{tr('reportEligibilityNotEval', lang)}</p>
              )}
              <div className="text-xs text-slate-500">{tr('reportImportantConditions', lang)}</div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">{tr('reportNoScheme', lang)}</p>
          )}
        </Card>

        {/* 12. Executive Summary */}
        <Card>
          <CardHeader title={tr('executiveSummary', lang)} />
          <p className="text-sm text-slate-700">{(result as any).viability?.reason || rec.reason}</p>
        </Card>

        {/* 13. One-line Strategic AI Advice */}
        {aiText ? (
          <Card>
            <CardHeader title={tr('reportStrategicAdvice', lang)} subtitle={tr('reportOneLine', lang)} />
            <p className="text-sm font-medium text-slate-900">{aiText.split('\n')[0]?.slice(0,300) || aiText.slice(0,300)}</p>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-slate-500">{tr('reportFullNarrative', lang)}</summary>
              <pre className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{aiText}</pre>
            </details>
          </Card>
        ) : loadingAi ? (
          <Card>
            <CardHeader title={tr('reportStrategicAdvice', lang)} />
            <div className="h-3 animate-pulse rounded bg-slate-100" />
          </Card>
        ) : null}

        {/* 14. Official GramBiz AI Declaration */}
        <Card>
          <CardHeader title={tr('reportOfficialDeclaration', lang)} />
          <div className="space-y-2 text-xs leading-relaxed text-slate-600">
            <p>{tr('reportAiAssisted', lang)}</p>
            <p>{tr('reportDeterministicCalc', lang)}</p>
            <p>{interpolate(tr('reportDataSourcesDecl', lang), { sources: (result.data_sources || []).slice(0,3).map((d:any)=> d.name || d.source).join(', ') || 'OpenStreetMap, Census 2011, verified market prices' })}</p>
            <p>{tr('reportEstimates', lang)}</p>
            <p className="font-bold text-slate-800">{tr('reportNotGuarantee', lang)}</p>
          </div>
        </Card>
      </div>

      <div className="flex justify-center">
        <button onClick={() => navigate('/videos')} className="rounded-xl bg-slate-900 px-8 py-3 text-sm font-bold text-white hover:bg-black shadow" data-testid="watch-video-cta">
          {tr('reportWatchVideo', lang)}
        </button>
      </div>
    </div>
  )
}


function Rows({ rows }: { rows: [string, import('react').ReactNode][] }) {
  return (
    <dl className="divide-y divide-gray-100">
      {rows.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between py-2 text-sm">
          <dt className="text-gray-500">{k}</dt>
          <dd className="font-medium text-gray-900">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function Empty({ lang }: { lang: Language }) {
  return (
    <div className="py-20 text-center text-gray-500">
      <p>{tr('runAnalysisReport', lang)}</p>
      <a href="/analyze" className="mt-2 inline-block text-brand-600">{tr('analyzeNow', lang)}</a>
    </div>
  )
}

function renderMarketReach(market: any, lang: Language) {
  const mr = market?.market_reach
  if (!mr) {
    return <p className="text-sm text-gray-500">{tr('marketReachNotComputed', lang)}</p>
  }
  const signals = mr.commercial_demand_signals || {}
  const acc = mr.market_accessibility || {}
  const signalRows: [string, React.ReactNode][] = Object.entries(signals).map(([k, v]: any) => [
    `${tr('mappedPrefix', lang)} ${k} (${v?.radius_km ?? '?'} ${tr('km', lang)})`,
    v?.count ?? '—',
  ])
  return (
    <div className="text-sm">
      <Rows rows={[
        [tr('populationBaseline', lang), mr.population_baseline != null ? `${mr.population_baseline.toLocaleString('en-IN')} (${tr('census', lang)} ${mr.population_year ?? '2011'})` : tr('unavailableHistorical', lang)],
        [tr('households', lang), mr.households != null ? mr.households.toLocaleString('en-IN') : '—'],
        [tr('nearestMarketRow', lang), acc.nearest_market_km != null ? `${acc.nearest_market_km} ${tr('km', lang)}` : '—'],
        [tr('nearestTransport', lang), acc.nearest_transport_km != null ? `${acc.nearest_transport_km} ${tr('km', lang)}` : '—'],
        [tr('marketsWithin20', lang), acc.markets_within_20km ?? '—'],
        ...signalRows,
      ]} />
      {(mr.notes || []).map((n: string, i: number) => (
        <p key={i} className="mt-1 text-[11px] italic text-gray-500">{n}</p>
      ))}
    </div>
  )
}

function renderDataConfidence(dc: any, s: any, lang: Language) {
  const reasons: string[] = dc?.reasons ?? []
  const confReasons: string[] = s?.confidence_factors?.reasons ?? []
  return (
    <div className="text-sm">
      <Rows rows={[
        [tr('dataConfidenceScore', lang), dc?.data_confidence_score != null ? `${dc.data_confidence_score}/100 (${dc.confidence_label || ''})` : '—'],
        [tr('evidenceConfidence', lang), s?.confidence_label ?? '—'],
        [tr('coverage', lang), dc?.coverage ?? '—'],
        [tr('completeness', lang), dc?.completeness != null ? `${Math.round(dc.completeness * 100)}%` : '—'],
      ]} />
      <div className="mt-2 space-y-1">
        {[...reasons, ...confReasons].map((r, i) => (
          <p key={i} className="rounded bg-gray-50 px-2 py-1 text-xs text-gray-600">• {r}</p>
        ))}
      </div>
    </div>
  )
}
