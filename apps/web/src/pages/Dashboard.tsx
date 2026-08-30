import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { useAnalysis } from '../lib/analysisStore'
import { LINK_BRAND } from '../lib/theme'
import { Badge, Card, CardHeader, Disclaimer, ScoreBar, StatCard } from '../components/ui'
import { ScoreDonut } from '../components/ScoreDonut'
import { tr, recommendationLabel, type Language } from '../lib/i18n'

const RECO_COLOR: Record<string, string> = { GO: 'green', MODIFY: 'amber', AVOID: 'red' }

export function Dashboard() {
  const { result, lang } = useAnalysis()
  if (!result) return <NoResult lang={lang} />

  const { opportunity_score: score, recommendation, financial_plan: fp, profit_model: pm, business_competition: bc } = result
  const bars = [
    { label: tr('demand', lang), value: score.demand_score },
    { label: tr('competition', lang), value: score.competition_score },
    { label: tr('accessibility', lang), value: score.accessibility_score },
    { label: tr('financialFit', lang), value: score.financial_fit_score },
    { label: tr('risk', lang), value: score.risk_score },
  ]
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Business Opportunity Report</h1>
          <p className="text-sm text-gray-500">
            {result.location.village || result.location.block || ''} · {result.location.district}, {result.location.state} · pins {showPins(result.location)}
            {pm?.is_estimate ? ' · estimated operating model' : ''}
          </p>
        </div>
        <Badge color={RECO_COLOR[recommendation.label] || 'gray'}>
          {recommendationLabel(recommendation.label, lang)}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title={tr('opportunity', lang) + ' Score'} subtitle={`Confidence: ${score.confidence_label}`} />
          <div className="flex items-center gap-6">
            <ScoreDonut value={score.overall_score} size={150} />
            <div className="flex-1">
              {bars.map((b) => (
                <ScoreBar key={b.label} label={b.label} value={b.value} color={b.value >= 50 ? 'green' : b.value >= 35 ? 'amber' : 'red'} />
              ))}
            </div>
          </div>
          <div className="mt-2 rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
            <strong className="text-gray-700">Interpretation:</strong> {recommendation.reason}
          </div>
          <ConfidenceExplanation score={score} dataConfidence={result.data_confidence} />
        </Card>

        <div className="grid grid-cols-2 gap-4">
          <StatCard
            label="Mapped competitors (5 km)"
            value={bc?.mapped_competitors_5km ?? '-'}
            sub={bc?.nearest_competitor_km != null ? `Nearest ${bc.nearest_competitor_km} km away` : 'No near competitor'}
          />
          <StatCard
            label="Mapped competitors (10 km)"
            value={bc?.mapped_competitors_10km ?? '-'}
            sub={bc?.data_completeness || ''}
          />
          <StatCard
            label="Project cost"
            value={`₹${formatINR(fp.project_cost)}`}
            sub={fp.scheme_name ? `Scheme: ${fp.scheme_name}` : 'Concept loan'}
          />
          <StatCard label="Loan amount" value={`₹${formatINR(fp.loan_amount)}`} sub={`Margin ${fp.margin_pct}% owned`} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Weather & Climate Evidence" subtitle={weatherSummary(result)} />
          <WeatherPanel weather={result.weather} />
        </Card>

        <Card>
          <CardHeader title="Profit & Payment Model" subtitle={pm?.label} />
          {pm && (
            <div className="grid grid-cols-3 gap-3 text-center">
              <MiniStat label="Monthly revenue" value={pm.outputs?.monthly_revenue} symbol="₹" />
              <MiniStat label="Monthly cost" value={pm.outputs?.monthly_cost} symbol="₹" />
              <MiniStat label="Gross margin" value={pm.outputs?.operating_profit} suffix="% / monthly ₹" />
            </div>
          )}
          <div className="mt-4">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={incomeCostData(pm)} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="Monthly output" fill={LINK_BRAND} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Disclaimer>
            Operating figures are estimates modelled from local prices and mapped demand, not the entrepreneur's actual
            accounts. Validate with a loan officer before committing.
          </Disclaimer>
        </Card>

        <Card>
          <CardHeader title="Financial Plan" subtitle={fp.scheme_name || 'Micro finance / term'} />
          <Rows
            rows={[
              ['Capital available', `₹${formatINR(fp.capital_available)}`],
              ['Project cost', `₹${formatINR(fp.project_cost)}`],
              ['Bank loan', `₹${formatINR(fp.loan_amount)}`],
              ['Interest rate (p.a.)', fp.interest_rate != null ? `${fp.interest_rate}%` : '—'],
              ['Tenure', fp.tenure_years != null ? `${fp.tenure_years} yr` : '—'],
              ['Moratorium', fp.moratorium_months != null ? `${fp.moratorium_months} mo (${fp.moratorium_mode || 'grace'})` : '—'],
              ['Monthly EMI (est.)', fp.emi != null ? `₹${formatINR(fp.emi)}` : result.repayment?.monthly_emi != null ? `₹${formatINR(result.repayment.monthly_emi)}` : '—'],
              ['Scheme decision', fp.scheme_decision || '—'],
            ]}
          />
          {fp.scheme_reason && note(fp.scheme_reason)}
        </Card>
      </div>
    </div>
  )
}

function weatherSummary(result: any): string {
  const w = result?.weather
  if (!w) return 'No live rows stored'
  if (!w.available) return 'UNAVAILABLE within 5 km — default risk adjustment applied'
  return `${w.records?.length || 0} rows · risk +${w.risk?.risk_delta ?? 0} to risk score`
}

const RISK_COLOR: Record<string, string> = {
  heat_stress: 'amber',
  drought: 'red',
  flood_risk: 'blue',
}

function WeatherPanel({ weather }: { weather?: any }) {
  const records = weather?.records || []
  const latest = records[records.length - 1]
  const factors = weather?.risk?.factors || null

  const latestRow =
    latest && latest.value != null ? (
      <div className="text-sm">
        Latest recorded indicator: <strong>{latest.indicator}</strong> = {latest.value}
        {latest.unit ? ` ${latest.unit}` : ''}
        {latest.date ? ` on ${String(latest.date).slice(0, 10)}` : ''}
      </div>
    ) : null

  return (
    <div className="space-y-2 text-xs text-gray-600">
      {!weather?.available && (
        <div className="rounded-lg bg-gray-50 p-2">
          No weather points within 5 km for this location. Treated as weather UNAVAILABLE (+5 to risk).
        </div>
      )}
      {latestRow && <div className="rounded-lg bg-gray-50 p-2">{latestRow}</div>}
      {!factors && weather?.available && (
        <div className="rounded-lg bg-green-50 p-2 text-green-700">No climate risk flags from stored records.</div>
      )}
      {factors && (
        <ul className="space-y-1.5">
          {factors.map((f: any) => (
            <li key={f.factor} className="flex items-center justify-between rounded-lg bg-gray-50 p-2">
              <span>
                <Badge color={RISK_COLOR[f.factor] || 'gray'}>{f.factor.replace('_', ' ')}</Badge>{' '}
                <span className="capitalize">{f.level}</span>
              </span>
              <span className="font-medium text-gray-800">+{f.risk_delta}</span>
            </li>
          ))}
        </ul>
      )}
      {factors && <p className="text-[11px] italic text-gray-400">Stored weather rows power the risk score; no values are invented.</p>}
    </div>
  )
}

function NoResult({ lang }: { lang: Language }) {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <div className="text-4xl">🌾</div>
      <h2 className="mt-4 text-xl font-bold text-gray-900">No analysis yet</h2>
      <p className="mt-2 text-sm text-gray-500">Run an analysis to see your opportunity report and financial plan.</p>
      <a href="/analyze" className="mt-4 inline-block rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-700">
        {tr('analyzeBusiness', lang)}
      </a>
    </div>
  )
}

function Rows({ rows }: { rows: [string, string][] }) {
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

function MiniStat({ label, value, symbol, suffix }: { label: string; value?: number; symbol?: string; suffix?: string }) {
  return (
    <div className="rounded-lg bg-brand-50 p-3">
      <div className="text-[11px] text-gray-500">{label}</div>
      <div className="text-base font-bold text-gray-900">
        {symbol || ''}
        {value != null ? formatINR(value) : '—'}
        {suffix ? <span className="text-[10px] font-normal text-gray-400"> {suffix}</span> : null}
      </div>
    </div>
  )
}

function incomeCostData(pm: any) {
  if (!pm?.outputs) return []
  return [
    { name: 'Revenue', 'Monthly output': Math.round(pm.outputs.monthly_revenue || 0) },
    { name: 'Costs', 'Monthly output': Math.round(pm.outputs.monthly_cost || 0) },
  ]
}

function showPins(loc: any): string {
  const p = loc.latitude != null && loc.longitude != null ? `${loc.latitude.toFixed(3)}, ${loc.longitude.toFixed(3)}` : 'no coordinates'
  const prec = loc.geo_precision || ''
  return `${p} · ${prec}`
}

function note(text: string) {
  return <p className="mt-2 rounded-lg bg-gray-50 p-2 text-xs text-gray-600">{text}</p>
}

function ConfidenceExplanation({ score, dataConfidence }: { score: any; dataConfidence?: any }) {
  const confidenceReasons: string[] = score?.confidence_factors?.reasons ?? []
  const qualityReasons: string[] = dataConfidence?.reasons ?? []
  const positive = confidenceReasons.filter((r) => /recent|point-level|high|complete|current/i.test(r))
  const limitations = confidenceReasons.filter((r) => /old|ageing|approximate|incomplete|missing|insufficient|unknown|low/i.test(r))
  return (
    <div className="mt-3 rounded-xl border border-brand-100 bg-brand-50/50 p-3 text-xs text-gray-700">
      <div className="mb-1 flex items-center gap-2">
        <span className="font-semibold text-gray-800">Why this score?</span>
        {dataConfidence && (
          <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-gray-500">
            Data confidence {dataConfidence.data_confidence_score ?? '—'}/100 ({dataConfidence.confidence_label || ''})
          </span>
        )}
      </div>
      {(positive.length > 0 || qualityReasons.length > 0) && (
        <div className="mb-2">
          <div className="mb-0.5 font-medium text-green-700">Positive signals</div>
          <ul className="list-inside list-disc space-y-0.5">
            {positive.map((r, i) => <li key={i}>{r}</li>)}
            {qualityReasons.filter((r) => /recent|current|complete|point/i.test(r)).map((r, i) => <li key={`q${i}`}>{r}</li>)}
          </ul>
        </div>
      )}
      {(limitations.length > 0 || qualityReasons.some((r) => /old|incomplete|approximate|missing/i.test(r))) && (
        <div>
          <div className="mb-0.5 font-medium text-amber-700">Limitations</div>
          <ul className="list-inside list-disc space-y-0.5">
            {limitations.map((r, i) => <li key={i}>{r}</li>)}
            {qualityReasons.filter((r) => /old|incomplete|approximate|missing|unknown|low|demo/i.test(r)).map((r, i) => <li key={`q${i}`}>{r}</li>)}
          </ul>
        </div>
      )}
      {confidenceReasons.length === 0 && <p className="text-gray-500">Explanation not available.</p>}
    </div>
  )
}

export function formatINR(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (Math.abs(n) >= 1) return Math.round(n).toLocaleString('en-IN')
  return String(n)
}
