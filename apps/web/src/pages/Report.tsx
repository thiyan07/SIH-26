import { useEffect, useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { api } from '../lib/api'
import { Button, Card, CardHeader, Badge, Disclaimer } from '../components/ui'
import { ScoreDonut } from '../components/ScoreDonut'
import { formatINR } from './Dashboard'
import { recommendationLabel } from '../lib/i18n'

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
      setAiText('AI narrative unavailable in this environment — deterministic report shown below.')
    } finally {
      setLoadingAi(false)
    }
  }

  useEffect(() => {
    if (!result) return
    loadReport()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  if (!result) return <Empty />

  const s = result.opportunity_score
  const fp = result.financial_plan
  const pm = result.profit_model
  const bc = result.business_competition
  const rec = result.recommendation

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Business Feasibility Report</h1>
          <p className="text-sm text-gray-500">
            {result.location.village || result.location.block} · {result.location.district}, {result.location.state} — generated {new Date().toLocaleDateString()}
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => window.print()} variant="outline">Print / Save PDF</Button>
          <Button onClick={loadReport} disabled={loadingAi}>{loadingAi ? 'Generating…' : 'Regenerate narrative'}</Button>
        </div>
      </div>

      <div id="report-print" className="space-y-6 print:space-y-4">
        <Card>
          <CardHeader title="Executive Summary" />
          <div className="flex flex-wrap items-center gap-6">
            <ScoreDonut value={s.overall_score} size={120} />
            <div className="min-w-[220px] flex-1">
              <div className="text-sm text-gray-600">
                Overall opportunity <strong className="text-gray-900">{s.overall_score}/100</strong> · Confidence{' '}
                <strong>{s.confidence_label}</strong>
              </div>
              <div className="mt-2">
                <Badge color={rec.label === 'GO' ? 'green' : rec.label === 'MODIFY' ? 'amber' : 'red'}>
                  Recommendation: {recommendationLabel(rec.label, lang)}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-gray-600">{rec.reason}</p>
            </div>
          </div>
        </Card>

        {aiText && (
          <Card>
            <CardHeader title="AI Narrative" subtitle="Generated explanation — all numbers come from the deterministic engines" />
            <pre className="whitespace-pre-wrap text-sm text-gray-700">{aiText}</pre>
          </Card>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader title="Market Summary" subtitle="Mapped data (© OSM) may be incomplete" />
            <Rows rows={[
              ['Competitors within 5 km', bc?.mapped_competitors_5km ?? '—'],
              ['Competitors within 10 km', bc?.mapped_competitors_10km ?? '—'],
              ['Nearest competitor', bc?.nearest_competitor_km != null ? `${bc.nearest_competitor_km} km (${bc.nearest_competitor || ''})` : '—'],
              ['Data completeness', bc?.data_completeness || '—'],
            ]} />
            {bc?.note && <p className="mt-2 text-xs italic text-gray-400">{bc.note}</p>}
          </Card>

          <Card>
            <CardHeader title="Market Reach" subtitle="Local demand & accessibility (plan §13)" />
            {renderMarketReach(result.market)}
          </Card>

          <Card>
            <CardHeader title="Data Confidence" subtitle="Quality of underlying evidence" />
            {renderDataConfidence(result.data_confidence, s)}
          </Card>

          <Card>
            <CardHeader title="Financial Plan" subtitle={fp.scheme_name || 'Concept loan'} />
            <Rows rows={[
              ['Available capital', `₹${formatINR(fp.capital_available)}`],
              ['Project cost', `₹${formatINR(fp.project_cost)}`],
              ['Loan amount', `₹${formatINR(fp.loan_amount)}`],
              ['Interest / tenure', `${fp.interest_rate ?? '—'}% · ${fp.tenure_years ?? '—'} yr`],
              ['Monthly EMI (est.)', `₹${formatINR(result.repayment?.monthly_emi ?? fp.emi)}`],
              ['Repayment health', result.repayment?.health_label || '—'],
              ['Scheme routed', fp.scheme_name || '—'],
            ]} />
          </Card>
        </div>

        <Card>
          <CardHeader title="Profit Model" subtitle={pm?.label || ''} />
          {pm?.is_estimate && (
            <p className="mb-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-700">
              Estimated operating model — figures are modelled, not actual accounts.
            </p>
          )}
          <div className="grid grid-cols-3 gap-4 text-center">
            <Cell label="Monthly revenue" value={`₹${formatINR(pm?.outputs?.monthly_revenue)}`} />
            <Cell label="Monthly cost" value={`₹${formatINR(pm?.outputs?.monthly_cost)}`} />
            <Cell label="Operating profit" value={`₹${formatINR(pm?.outputs?.operating_profit)}`} />
          </div>
        </Card>

        <Card>
          <CardHeader title="Data Provenance" subtitle="What was used and where it came from" />
          <ul className="space-y-2 text-sm text-gray-600">
            {(result.data_sources || []).map((d, i) => (
              <li key={i} className="rounded-lg bg-gray-50 px-3 py-2">
                <strong className="text-gray-800">{d.name || d.source || 'Source'}</strong>{' '}
                <span className="text-gray-400">·</span> {d.reference || ''}{' '}
                {d.confidence ? <span className="text-gray-400">· confidence {d.confidence}</span> : null}
              </li>
            ))}
          </ul>
          <Disclaimer>Business feasibility and loan estimates are informational and not a guarantee of approval or profit.</Disclaimer>
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

function Empty() {
  return (
    <div className="py-20 text-center text-gray-500">
      <p>Run an analysis to generate a report.</p>
      <a href="/analyze" className="mt-2 inline-block text-brand-600">Analyze now →</a>
    </div>
  )
}

function renderMarketReach(market: any) {
  const mr = market?.market_reach
  if (!mr) {
    return <p className="text-sm text-gray-500">Market reach data not computed for this analysis.</p>
  }
  const signals = mr.commercial_demand_signals || {}
  const acc = mr.market_accessibility || {}
  const signalRows: [string, React.ReactNode][] = Object.entries(signals).map(([k, v]: any) => [
    `Mapped ${k} (${v?.radius_km ?? '?'} km)`,
    v?.count ?? '—',
  ])
  return (
    <div className="text-sm">
      <Rows rows={[
        ['Population baseline', mr.population_baseline != null ? `${mr.population_baseline.toLocaleString('en-IN')} (Census ${mr.population_year ?? '2011'})` : 'Unavailable — historical only'],
        ['Households', mr.households != null ? mr.households.toLocaleString('en-IN') : '—'],
        ['Nearest market', acc.nearest_market_km != null ? `${acc.nearest_market_km} km` : '—'],
        ['Nearest transport', acc.nearest_transport_km != null ? `${acc.nearest_transport_km} km` : '—'],
        ['Markets within 20 km', acc.markets_within_20km ?? '—'],
        ...signalRows,
      ]} />
      {(mr.notes || []).map((n: string, i: number) => (
        <p key={i} className="mt-1 text-[11px] italic text-gray-400">{n}</p>
      ))}
    </div>
  )
}

function renderDataConfidence(dc: any, s: any) {
  const reasons: string[] = dc?.reasons ?? []
  const confReasons: string[] = s?.confidence_factors?.reasons ?? []
  return (
    <div className="text-sm">
      <Rows rows={[
        ['Data confidence', dc?.data_confidence_score != null ? `${dc.data_confidence_score}/100 (${dc.confidence_label || ''})` : '—'],
        ['Evidence confidence', s?.confidence_label ?? '—'],
        ['Coverage', dc?.coverage ?? '—'],
        ['Completeness', dc?.completeness != null ? `${Math.round(dc.completeness * 100)}%` : '—'],
      ]} />
      <div className="mt-2 space-y-1">
        {[...reasons, ...confReasons].map((r, i) => (
          <p key={i} className="rounded bg-gray-50 px-2 py-1 text-xs text-gray-600">• {r}</p>
        ))}
      </div>
    </div>
  )
}
