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
import { tr, interpolate, recommendationLabel, type Language } from '../lib/i18n'

const RECO_COLOR: Record<string, string> = { GO: 'green', MODIFY: 'amber', AVOID: 'red' }

export function Dashboard() {
  const { result, lang } = useAnalysis()
  if (!result) return <NoResult lang={lang} />

  const { opportunity_score: score, recommendation, financial_plan: fp, profit_model: pm, business_competition: bc } = result
  const me = result.monthly_economics
  const si = result.seasonal_intelligence
  const wi = result.weather_intelligence
  const prs = result.product_recommendations
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
          <h1 className="text-2xl font-bold text-gray-900">{tr('reportTitle', lang)}</h1>
          <p className="text-sm text-gray-500">
            {result.location.village || result.location.block || ''} · {result.location.district}, {result.location.state} · {tr('pinsLabel', lang)} {showPins(result.location, lang)}
            {pm?.is_estimate ? ` · ${tr('estimatedOperatingModel', lang)}` : ''}
          </p>
        </div>
        <Badge color={RECO_COLOR[recommendation.label] || 'gray'}>
          {recommendationLabel(recommendation.label, lang)}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title={tr('opportunityScore', lang)} subtitle={`${tr('confidence', lang)}: ${score.confidence_label}`} />
          <div className="flex items-center gap-6">
            <ScoreDonut value={score.overall_score} size={150} />
            <div className="flex-1">
              {bars.map((b) => (
                <ScoreBar key={b.label} label={b.label} value={b.value} color={b.value >= 50 ? 'green' : b.value >= 35 ? 'amber' : 'red'} />
              ))}
            </div>
          </div>
          <div className="mt-2 rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
            <strong className="text-gray-700">{tr('interpretation', lang)}</strong> {recommendation.reason}
          </div>
          <ConfidenceExplanation score={score} dataConfidence={result.data_confidence} lang={lang} />
        </Card>

        <div className="grid grid-cols-3 gap-4">
          <StatCard
            label={tr('competitors5km', lang)}
            value={bc?.mapped_competitors_5km ?? '-'}
            sub={bc?.nearest_competitor_km != null ? `${tr('nearestPrefix', lang)} ${bc.nearest_competitor_km} ${tr('km', lang)}` : tr('noNearCompetitor', lang)}
          />
          <StatCard
            label={tr('competitors5to10km', lang)}
            value={bc?.mapped_competitors_5km != null && bc?.mapped_competitors_10km != null ? bc.mapped_competitors_10km - bc.mapped_competitors_5km : '-'}
            sub={tr('additionalInRing', lang)}
          />
          <StatCard
            label={tr('competitors10km', lang)}
            value={bc?.mapped_competitors_10km ?? '-'}
            sub={bc?.data_completeness || ''}
          />
          <StatCard
            label={tr('projectCost', lang)}
            value={`₹${formatINR(fp.project_cost)}`}
            sub={fp.scheme_name ? `${tr('scheme', lang)}: ${fp.scheme_name}` : tr('conceptLoan', lang)}
          />
          <StatCard label={tr('loanAmount', lang)} value={`₹${formatINR(fp.loan_amount)}`} sub={`${tr('ownContributionShort', lang)} ₹${formatINR(fp.own_contribution ?? 0)}`} />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title={tr('weatherClimate', lang)} subtitle={weatherSummary(result, lang)} />
          <WeatherPanel weather={result.weather} lang={lang} />
          {wi && (
            <div className="mt-3 border-t border-gray-100 pt-3">
              {wi.relevant ? (
                <div className="flex items-center gap-2 text-xs text-gray-600">
                  <span>{tr('categoryClimateSensitivity', lang)}</span>
                  <Badge color={sensitivityColor(wi.sensitivity)}>{wi.sensitivity || '—'}</Badge>
                </div>
              ) : (
                <p className="text-[11px] italic text-gray-400">{tr('weatherFlagsNotSurfaced', lang)}</p>
              )}
              {wi.reason && <p className="mt-1 text-[11px] italic text-gray-400">{wi.reason}</p>}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title={tr('profitPaymentModel', lang)} subtitle={me ? tr('estimatedCashflowChain', lang) : pm?.label} />
          {me ? (
            <div className="space-y-2 text-sm">
              <div className="rounded-lg bg-gray-50 p-3 text-[11px] font-medium uppercase tracking-wide text-gray-500">{tr('estimatedMonthlyLedger', lang)}</div>
              <LedgerRow label={tr('revenue', lang)} value={me.monthly_revenue} />
              <LedgerRow label={tr('cogs', lang)} value={me.cogs} />
              <LedgerRow label={tr('grossProfit', lang)} value={me.gross_profit} suffix={me.gross_margin_pct != null ? `(${me.gross_margin_pct}%)` : undefined} bold />
              <LedgerRow label={tr('operatingExpenses', lang)} value={me.opex} suffix={me.opex_pct != null ? `(${me.opex_pct}%)` : undefined} />
              <LedgerRow label={tr('operatingProfit', lang)} value={me.operating_profit} suffix={me.operating_margin_pct != null ? `(${me.operating_margin_pct}%)` : undefined} bold />
              <LedgerRow label={tr('loanEmi', lang)} value={me.emi} />
              <LedgerRow label={tr('cashSurplus', lang)} value={me.cash_surplus} suffix={me.cash_surplus_pct != null ? `(${me.cash_surplus_pct}%)` : undefined} highlight={me.cash_surplus != null && me.cash_surplus >= 0} />
              <div className="border-t border-gray-100 pt-2">
                {me.break_even_state && me.break_even_state !== 'insufficient_data' ? (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">{tr('breakEvenRevenue', lang)}</span>
                    <span className="font-medium text-gray-900">₹{formatINR(me.break_even_revenue)}</span>
                  </div>
                ) : (
                  <div className="text-xs text-gray-400">{tr('breakEvenInsufficient', lang)}</div>
                )}
              </div>
              {me.notes?.length > 0 && (
                <div className="mt-1 space-y-0.5">
                  {me.notes.map((n: string, i: number) => <p key={i} className="text-[11px] italic text-gray-400">{n}</p>)}
                </div>
              )}
            </div>
          ) : pm ? (
            <div className="grid grid-cols-3 gap-3 text-center">
              <MiniStat label={tr('monthlyRevenue', lang)} value={pm.outputs?.monthly_revenue} symbol="₹" />
              <MiniStat label={tr('monthlyCost', lang)} value={pm.outputs?.monthly_cost} symbol="₹" />
              <MiniStat label={tr('grossMargin', lang)} value={pm.outputs?.operating_profit} suffix={tr('percentMonthlyInr', lang)} />
            </div>
          ) : null}
          <div className="mt-4">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={incomeCostData(me || pm, lang)} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey={tr('monthlyOutput', lang)} fill={LINK_BRAND} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <Disclaimer>{tr('estimateOperating', lang)}</Disclaimer>
        </Card>

        <Card>
          <CardHeader title={tr('financialPlan', lang)} subtitle={fp.scheme_name || tr('microFinanceTerm', lang)} />
          <Rows
            rows={[
              [tr('capitalAvailable', lang), `₹${formatINR(fp.capital_available)}`],
              [tr('projectCost', lang), `₹${formatINR(fp.project_cost)}`],
              [tr('bankLoan', lang), `₹${formatINR(fp.loan_amount)}`],
              [tr('interestRatePA', lang), fp.interest_rate != null ? `${fp.interest_rate}%` : '—'],
              [tr('tenure', lang), fp.tenure_years != null ? `${fp.tenure_years} ${tr('yr', lang)}` : '—'],
              [tr('moratorium', lang), fp.moratorium_months != null ? `${fp.moratorium_months} ${tr('mo', lang)} (${fp.moratorium_mode || 'grace'})` : '—'],
              [tr('monthlyEMI', lang), fp.emi != null ? `₹${formatINR(fp.emi)}` : result.repayment?.monthly_emi != null ? `₹${formatINR(result.repayment.monthly_emi)}` : '—'],
              [tr('schemeDecision', lang), fp.scheme_decision || '—'],
            ]}
          />
          {fp.scheme_reason && note(fp.scheme_reason)}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title={tr('seasonalDemand', lang)} subtitle={si ? tr('estimatedSeasonality', lang) : undefined} />
          {si ? (
            <div className="space-y-2 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge color={seasonLabelColor(si.current_label)}>{si.current_label || '—'} {tr('season', lang)}</Badge>
                <span className="text-xs text-gray-500">
                  {monthName(si.current_month, lang)} · {tr('index', lang)} {si.current_index ?? '—'}
                </span>
                <Badge color={riskColor(si.cash_flow_risk)}>{si.cash_flow_risk || '—'} {tr('cashflowRisk', lang)}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-gray-50 p-2">
                  <div className="text-gray-500">{tr('peakMonth', lang)}</div>
                  <div className="font-semibold text-gray-900">{monthName(si.peak_month, lang)}{si.peak_index != null ? ` · ${si.peak_index}` : ''}</div>
                </div>
                <div className="rounded-lg bg-gray-50 p-2">
                  <div className="text-gray-500">{tr('lowMonth', lang)}</div>
                  <div className="font-semibold text-gray-900">{monthName(si.low_month, lang)}{si.low_index != null ? ` · ${si.low_index}` : ''}</div>
                </div>
              </div>
              {si.cash_flow_risk_reason && <p className="text-xs text-gray-600">{si.cash_flow_risk_reason}</p>}
              {si.inventory_implication && (
                <div className="rounded-lg bg-brand-50 p-2 text-xs text-brand-800">
                  <strong>{tr('inventory', lang)}</strong>{si.inventory_implication}
                  {si.stock_buffer_factor != null ? ` (${tr('buffer', lang)} ×${si.stock_buffer_factor})` : ''}
                </div>
              )}
              {si.recommendation && <p className="text-xs text-gray-700">{si.recommendation}</p>}
              {si.note && <p className="text-[11px] italic text-gray-400">{si.note}</p>}
            </div>
          ) : (
            <p className="text-sm text-gray-500">{tr('noSeasonalIntelligence', lang)}</p>
          )}
        </Card>

        <Card>
          <CardHeader title={tr('productRecommendations', lang)} subtitle={tr('estimatedFocusProducts', lang)} />
          {prs && prs.length > 0 ? (
            <ul className="space-y-2">
              {prs.map((p: any, i: number) => (
                <li key={i} className="rounded-lg bg-gray-50 p-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-900">{p.product || tr('product', lang)}</span>
                    <div className="flex items-center gap-1.5">
                      <Badge color={relevanceColor(p.relevance)}>{p.relevance || '—'}</Badge>
                      <span className="text-[10px] text-gray-400">{p.confidence || '—'} {tr('confidence', lang)}</span>
                    </div>
                  </div>
                  {p.reason && <p className="mt-1 text-xs text-gray-600">{p.reason}</p>}
                  {p.evidence && <p className="mt-1 text-[11px] italic text-gray-400">{p.evidence}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">{tr('noProductRecs', lang)}</p>
          )}
        </Card>
      </div>
    </div>
  )
}

function weatherSummary(result: any, lang: Language): string {
  const w = result?.weather
  if (!w) return tr('noLiveRowsStored', lang)
  if (!w.available) return tr('weatherUnavailableDefault', lang)
  return `${interpolate(tr('weatherRows', lang), { n: w.records?.length || 0 })} · +${w.risk?.risk_delta ?? 0}`
}

const RISK_COLOR: Record<string, string> = {
  heat_stress: 'amber',
  drought: 'red',
  flood_risk: 'blue',
}

function WeatherPanel({ weather, lang }: { weather?: any; lang: Language }) {
  const records = weather?.records || []
  const latest = records[records.length - 1]
  const factors = weather?.risk?.factors || null

  const latestRow =
    latest && latest.value != null ? (
      <div className="text-sm">
        {tr('latestRecordedIndicator', lang)}: <strong>{latest.indicator}</strong> = {latest.value}
        {latest.unit ? ` ${latest.unit}` : ''}
        {latest.date ? ` ${tr('onPrefix', lang)} ${String(latest.date).slice(0, 10)}` : ''}
      </div>
    ) : null

  return (
    <div className="space-y-2 text-xs text-gray-600">
      {!weather?.available && (
        <div className="rounded-lg bg-gray-50 p-2">
          {tr('noWeatherWithin5km', lang)}
        </div>
      )}
      {latestRow && <div className="rounded-lg bg-gray-50 p-2">{latestRow}</div>}
      {!factors && weather?.available && (
        <div className="rounded-lg bg-green-50 p-2 text-green-700">{tr('noClimateRiskFlags', lang)}</div>
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
      {factors && <p className="text-[11px] italic text-gray-400">{tr('storedWeatherRows', lang)}</p>}
    </div>
  )
}

function NoResult({ lang }: { lang: Language }) {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <div className="text-4xl">🌾</div>
      <h2 className="mt-4 text-xl font-bold text-gray-900">{tr('noAnalysisYet', lang)}</h2>
      <p className="mt-2 text-sm text-gray-500">{tr('noAnalysisDesc', lang)}</p>
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

function LedgerRow({ label, value, suffix, bold, highlight }: { label: string; value?: number; suffix?: string; bold?: boolean; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className={`text-gray-500 ${bold ? 'font-semibold text-gray-700' : ''}`}>{label}</span>
      <span className={`font-medium text-gray-900 ${bold ? 'font-semibold' : ''} ${highlight ? 'text-green-700' : ''}`}>
        ₹{formatINR(value)}
        {suffix ? <span className="text-[10px] font-normal text-gray-400"> {suffix}</span> : null}
      </span>
    </div>
  )
}

function incomeCostData(meOrPm: any, lang: Language) {
  if (!meOrPm) return []
  const outputKey = tr('monthlyOutput', lang)
  if (meOrPm.monthly_revenue != null) {
    return [
      { name: tr('revenue', lang), [outputKey]: Math.round(meOrPm.monthly_revenue || 0) },
      { name: tr('opex', lang), [outputKey]: Math.round(meOrPm.opex || 0) },
      { name: tr('cashSurplusChart', lang), [outputKey]: Math.round(meOrPm.cash_surplus || 0) },
    ]
  }
  if (meOrPm.outputs) {
    return [
      { name: tr('revenue', lang), [outputKey]: Math.round(meOrPm.outputs.monthly_revenue || 0) },
      { name: tr('costs', lang), [outputKey]: Math.round(meOrPm.outputs.monthly_cost || 0) },
    ]
  }
  return []
}

function showPins(loc: any, lang: Language): string {
  const p = loc.latitude != null && loc.longitude != null ? `${loc.latitude.toFixed(3)}, ${loc.longitude.toFixed(3)}` : tr('noCoordinates', lang)
  const prec = loc.geo_precision || ''
  return `${p} · ${prec}`
}

function note(text: string) {
  return <p className="mt-2 rounded-lg bg-gray-50 p-2 text-xs text-gray-600">{text}</p>
}

function ConfidenceExplanation({ score, dataConfidence, lang }: { score: any; dataConfidence?: any; lang: Language }) {
  const confidenceReasons: string[] = score?.confidence_factors?.reasons ?? []
  const qualityReasons: string[] = dataConfidence?.reasons ?? []
  const positive = confidenceReasons.filter((r) => /recent|point-level|high|complete|current/i.test(r))
  const limitations = confidenceReasons.filter((r) => /old|ageing|approximate|incomplete|missing|insufficient|unknown|low/i.test(r))
  return (
    <div className="mt-3 rounded-xl border border-brand-100 bg-brand-50/50 p-3 text-xs text-gray-700">
      <div className="mb-1 flex items-center gap-2">
        <span className="font-semibold text-gray-800">{tr('whyThisScore', lang)}</span>
        {dataConfidence && (
          <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-gray-500">
            {tr('dataConfidenceScore', lang)} {dataConfidence.data_confidence_score ?? '—'}/100 ({dataConfidence.confidence_label || ''})
          </span>
        )}
      </div>
      {(positive.length > 0 || qualityReasons.length > 0) && (
        <div className="mb-2">
          <div className="mb-0.5 font-medium text-green-700">{tr('positiveSignals', lang)}</div>
          <ul className="list-inside list-disc space-y-0.5">
            {positive.map((r, i) => <li key={i}>{r}</li>)}
            {qualityReasons.filter((r) => /recent|current|complete|point/i.test(r)).map((r, i) => <li key={`q${i}`}>{r}</li>)}
          </ul>
        </div>
      )}
      {(limitations.length > 0 || qualityReasons.some((r) => /old|incomplete|approximate|missing/i.test(r))) && (
        <div>
          <div className="mb-0.5 font-medium text-amber-700">{tr('limitations', lang)}</div>
          <ul className="list-inside list-disc space-y-0.5">
            {limitations.map((r, i) => <li key={i}>{r}</li>)}
            {qualityReasons.filter((r) => /old|incomplete|approximate|missing|unknown|low|demo/i.test(r)).map((r, i) => <li key={`q${i}`}>{r}</li>)}
          </ul>
        </div>
      )}
      {confidenceReasons.length === 0 && <p className="text-gray-500">{tr('explanationNotAvailable', lang)}</p>}
    </div>
  )
}

export function formatINR(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (Math.abs(n) >= 1) return Math.round(n).toLocaleString('en-IN')
  return String(n)
}

function monthName(m: number | undefined | null, lang: Language = 'en'): string {
  if (m == null || m < 0 || m > 11) return '—'
  return tr('monthNames', lang).split(',')[m]
}

function sensitivityColor(v: string | undefined): any {
  return v === 'VERY HIGH' || v === 'HIGH' ? 'red' : v === 'MEDIUM' ? 'amber' : 'gray'
}

function seasonLabelColor(v: string | undefined): any {
  return v === 'PEAK' ? 'green' : v === 'HIGH' ? 'blue' : v === 'SOFT' ? 'amber' : v === 'LOW' ? 'gray' : 'gray'
}

function riskColor(v: string | undefined): any {
  return v === 'HIGH' ? 'red' : v === 'MEDIUM' ? 'amber' : 'gray'
}

function relevanceColor(v: string | undefined): any {
  return v === 'high' ? 'green' : v === 'medium' ? 'amber' : 'gray'
}
