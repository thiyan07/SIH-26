import { useEffect, useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { api } from '../lib/api'
import { Button, Card, CardHeader, Badge, Disclaimer } from '../components/ui'
import { ScoreDonut } from '../components/ScoreDonut'
import { formatINR } from './Dashboard'
import { recommendationLabel, tr, type Language } from '../lib/i18n'

export function Report() {
  const { result, lang } = useAnalysis()
  const [aiText, setAiText] = useState<string | null>(null)
  const [loadingAi, setLoadingAi] = useState(false)

  const analysisId = (result as any)?.analysis_id

  const loadReport = async () => {
    setLoadingAi(true)
    try {
      const evidence = result as unknown as Record<string, unknown>
      const res = await api.post<{ content: string }>('/ai/report', {
        evidence,
        language: lang,
        ...(analysisId ? { analysis_id: analysisId } : {}),
      })
      setAiText(res.content)
    } catch {
      setAiText(tr('aiUnavailable', lang))
    } finally {
      setLoadingAi(false)
    }
  }

  useEffect(() => {
    if (!result) return
    loadReport()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  if (!result) return <Empty lang={lang} />

  const s = result.opportunity_score
  const fp = result.financial_plan
  const pm = result.profit_model
  const bc = result.business_competition
  const rec = result.recommendation

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{tr('feasibilityReport', lang)}</h1>
          <p className="text-sm text-gray-500">
            {result.location.village || result.location.block} · {result.location.district}, {result.location.state} — {tr('generatedPrefix', lang)} {new Date().toLocaleDateString()}
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => window.print()} variant="outline">{tr('printSave', lang)}</Button>
          <Button onClick={loadReport} disabled={loadingAi}>{loadingAi ? tr('generating', lang) : tr('regenerateNarrative', lang)}</Button>
        </div>
      </div>

      <div id="report-print" className="space-y-6 print:space-y-4">
        <Card>
          <CardHeader title={tr('executiveSummary', lang)} />
          <div className="flex flex-wrap items-center gap-6">
            <ScoreDonut value={s.overall_score} size={120} />
            <div className="min-w-[220px] flex-1">
              <div className="text-sm text-gray-600">
                {tr('overallOpportunity', lang)} <strong className="text-gray-900">{s.overall_score}/100</strong> · {tr('confidence', lang)}{' '}
                <strong>{s.confidence_label}</strong>
              </div>
              <div className="mt-2">
                <Badge color={rec.label === 'GO' ? 'green' : rec.label === 'MODIFY' ? 'amber' : 'red'}>
                  {tr('recommendation', lang)} {recommendationLabel(rec.label, lang)}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-gray-600">{rec.reason}</p>
            </div>
          </div>
        </Card>

        {aiText && (
          <Card>
            <CardHeader title={tr('aiNarrative', lang)} subtitle={tr('aiNarrativeSub', lang)} />
            <pre className="whitespace-pre-wrap text-sm text-gray-700">{aiText}</pre>
          </Card>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader title={tr('marketSummary', lang)} subtitle={tr('marketSummarySub', lang)} />
            <Rows rows={[
              [tr('competitorsWithin5', lang), bc?.mapped_competitors_5km ?? '—'],
              [tr('additional5to10', lang), bc?.mapped_competitors_5km != null && bc?.mapped_competitors_10km != null ? bc.mapped_competitors_10km - bc.mapped_competitors_5km : '—'],
              [tr('competitorsWithin10', lang), bc?.mapped_competitors_10km ?? '—'],
              [tr('nearestCompetitorRow', lang), bc?.nearest_competitor_km != null ? `${bc.nearest_competitor_km} ${tr('km', lang)} (${bc.nearest_competitor || ''})` : '—'],
              [tr('dataCompleteness', lang), bc?.data_completeness || '—'],
            ]} />
            {bc?.note && <p className="mt-2 text-xs italic text-gray-400">{bc.note}</p>}
          </Card>

          <Card>
            <CardHeader title={tr('marketReach', lang)} subtitle={tr('marketReachSub', lang)} />
            {renderMarketReach(result.market, lang)}
          </Card>

          <Card>
            <CardHeader title={tr('dataConfidenceTitle', lang)} subtitle={tr('dataConfidenceSub', lang)} />
            {renderDataConfidence(result.data_confidence, s, lang)}
          </Card>

          <Card>
            <CardHeader title={tr('financialPlan', lang)} subtitle={fp.scheme_name || tr('conceptLoan', lang)} />
            <Rows rows={[
              [tr('availableCapital', lang), `₹${formatINR(fp.capital_available)}`],
              [tr('projectCost', lang), `₹${formatINR(fp.project_cost)}`],
              [tr('loanAmount', lang), `₹${formatINR(fp.loan_amount)}`],
              [tr('interestTenure', lang), `${fp.interest_rate ?? '—'}% · ${fp.tenure_years ?? '—'} ${tr('years', lang)}`],
              [tr('monthlyEMI', lang), `₹${formatINR(result.repayment?.monthly_emi ?? fp.emi)}`],
              [tr('repayHealth', lang), result.repayment?.health_label || '—'],
              [tr('schemeRouted', lang), fp.scheme_name || '—'],
            ]} />
          </Card>
        </div>

        <Card>
          <CardHeader title={tr('profitModel', lang)} subtitle={pm?.label || ''} />
          {pm?.is_estimate && (
            <p className="mb-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-700">
              {tr('estimatedOperatingModel', lang)}
            </p>
          )}
          <div className="grid grid-cols-3 gap-4 text-center">
            <Cell label={tr('monthlyRevenue', lang)} value={`₹${formatINR(pm?.outputs?.monthly_revenue)}`} />
            <Cell label={tr('monthlyCost', lang)} value={`₹${formatINR(pm?.outputs?.monthly_cost)}`} />
            <Cell label={tr('operatingProfit', lang)} value={`₹${formatINR(pm?.outputs?.operating_profit)}`} />
          </div>
        </Card>

        <Card>
          <CardHeader title={tr('dataProvenance', lang)} subtitle={tr('dataProvenanceSub', lang)} />
          <ul className="space-y-2 text-sm text-gray-600">
            {(result.data_sources || []).map((d, i) => (
              <li key={i} className="rounded-lg bg-gray-50 px-3 py-2">
                <strong className="text-gray-800">{d.name || d.source || tr('source', lang)}</strong>{' '}
                <span className="text-gray-400">·</span> {d.reference || ''}{' '}
                {d.confidence ? <span className="text-gray-400">· {tr('confidence', lang)} {d.confidence}</span> : null}
              </li>
            ))}
          </ul>
          <Disclaimer>{tr('reportDisclaimer', lang)}</Disclaimer>
        </Card>
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

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-brand-50 p-3">
      <div className="text-[11px] text-gray-500">{label}</div>
      <div className="text-lg font-bold text-gray-900">{value}</div>
    </div>
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
        <p key={i} className="mt-1 text-[11px] italic text-gray-400">{n}</p>
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
