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
import { Badge, Card, CardHeader, Disclaimer } from '../components/ui'
import { Spotlight } from '../components/aceternity/BackgroundBeams'
import { tr, recommendationLabel, type Language } from '../lib/i18n'

const RECO_COLOR: Record<string, string> = { GO: 'green', MODIFY: 'amber', AVOID: 'red' }

export function Dashboard() {
  const { result, lang } = useAnalysis()
  if (!result) return <NoResult lang={lang} />

  const { recommendation, financial_plan: fp, profit_model: pm } = result
  const me = result.monthly_economics
  const si = result.seasonal_intelligence
  const prs = result.product_recommendations
  // AI Suggested Opportunities removed - no longer shown on Dashboard per requirements

  return (
    <div className="space-y-6">
      <Spotlight>
        <div className="flex flex-col gap-3 rounded-xl border border-teal-100 bg-gradient-to-br from-white via-teal-50/50 to-cyan-50/30 p-4 px-4 sm:px-6 box-border sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0 flex-1">
            <h1 className="break-words text-2xl font-bold tracking-tight text-gray-900">{tr('reportTitle', lang)}</h1>
            <p className="break-words text-sm leading-relaxed text-gray-500">
              {result.location.village || result.location.block || ''} · {result.location.district}, {result.location.state} · {tr('pinsLabel', lang)} {showPins(result.location, lang)}
              {pm?.is_estimate ? ` · ${tr('estimatedOperatingModel', lang)}` : ''}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Badge color={RECO_COLOR[recommendation.label] || 'gray'}>
              {recommendationLabel(recommendation.label, lang)}
            </Badge>
          </div>
        </div>
      </Spotlight>

      {/* 1. FINAL DECISION — deterministic GO/MODIFY/AVOID */}
      {(() => {
        const v = (result as any).viability
        if (!v) return null
        const color = v.decision === 'GO' ? 'green' : v.decision === 'AVOID' ? 'red' : 'amber'
        return (
          <Card className={`border-2 ${v.decision === 'GO' ? 'border-green-200 bg-green-50/40' : v.decision === 'AVOID' ? 'border-red-200 bg-red-50/40' : 'border-amber-200 bg-amber-50/40'}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs font-bold uppercase tracking-widest text-gray-500">Final Decision</div>
                <div className={`mt-1 text-3xl font-black tracking-tight ${v.decision === 'GO' ? 'text-green-700' : v.decision === 'AVOID' ? 'text-red-700' : 'text-amber-700'}`}>{v.decision}</div>
                <div className="mt-1 text-xs text-gray-500">Score {v.score}/100 · confidence {v.confidence} ({v.confidence_score}/100)</div>
              </div>
              <Badge color={color}>{v.decision}</Badge>
            </div>
            <p className="mt-3 text-sm text-gray-700">{v.reason}</p>
            {/* 2. WHY — top 3 reasons */}
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg bg-white p-3">
                <div className="text-xs font-semibold text-green-700">Top positives</div>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-gray-700">
                  {(v.top_positive_factors || []).slice(0,3).map((f:string,i:number)=><li key={i}>{f}</li>)}
                </ul>
              </div>
              <div className="rounded-lg bg-white p-3">
                <div className="text-xs font-semibold text-red-700">Top negatives</div>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-gray-700">
                  {(v.top_negative_factors || []).slice(0,3).map((f:string,i:number)=><li key={i}>{f}</li>)}
                </ul>
              </div>
            </div>
            {v.recommended_actions?.length ? (
              <div className="mt-3 rounded-lg bg-white p-3">
                <div className="text-xs font-semibold text-gray-700">Recommended actions</div>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-gray-700">
                  {v.recommended_actions.slice(0,3).map((a:string,i:number)=><li key={i}>{a}</li>)}
                </ul>
              </div>
            ): null}
            {v.decision === 'AVOID' && (
              <div className="mt-4 flex flex-wrap gap-3">
                <a href="/analyze" className="rounded-xl bg-brand-600 px-6 py-3 text-sm font-bold text-white hover:bg-brand-700 shadow">Go to Analyze & Change Input →</a>
                <a href="/" className="rounded-xl border border-slate-200 bg-white px-6 py-3 text-sm font-bold text-slate-700 hover:bg-slate-50">Exit</a>
              </div>
            )}
          </Card>
        )
      })()}

      {/* 3. LOCATION — exact point + competition + accessibility */}
      {(() => {
        const ls = (result as any).location_suitability
        if (!ls) return null
        return (
          <Card>
            <CardHeader title="Location Suitability" subtitle={`${ls.suitability_score}/100 · confidence ${ls.confidence}`} />
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-lg bg-green-50 p-3">
                <div className="text-xs font-semibold text-green-800">Strengths</div>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-gray-700">
                  {ls.strengths.map((s:string,i:number)=><li key={i}>{s}</li>)}
                </ul>
              </div>
              <div className="rounded-lg bg-amber-50 p-3">
                <div className="text-xs font-semibold text-amber-800">Concerns</div>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-gray-700">
                  {ls.concerns.map((s:string,i:number)=><li key={i}>{s}</li>)}
                </ul>
              </div>
            </div>
            <div className="mt-2 text-xs text-gray-500">{result.location.village || result.location.block} · {result.location.district} · {result.location.uses_proposed_location ? `Exact: ${Number(result.location.proposed_latitude).toFixed(4)}, ${Number(result.location.proposed_longitude).toFixed(4)} (uses exact proposed location)` : `Centroid: ${Number(result.location.latitude).toFixed(4)}, ${Number(result.location.longitude).toFixed(4)}` } · {result.location.geo_precision}</div>
            <p className="mt-1 text-[11px] italic text-gray-500">{ls.note}</p>
          </Card>
        )
      })()}



      {/* AI Suggested Opportunities removed per product requirements — focus on primary analysis review */}



      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title={tr('profitPaymentModel', lang)} subtitle={me ? tr('estimatedCashflowChain', lang) : pm?.label} />
          {me ? (
            <div className="space-y-2 text-sm">
              <div className="box-border rounded-lg bg-gray-50 p-3 px-4 break-words whitespace-normal text-[11px] font-medium uppercase tracking-wide text-gray-500">{tr('estimatedMonthlyLedger', lang)}</div>
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
                  <div className="text-xs text-gray-500">{tr('breakEvenInsufficient', lang)}</div>
                )}
              </div>
              {(me.notes?.length || 0) > 0 && (
                <div className="mt-1 space-y-0.5">
                  {(me.notes || []).map((n: string, i: number) => <p key={i} className="text-[11px] italic text-gray-500">{n}</p>)}
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
          <CardHeader title={tr('financialPlan', lang)} subtitle={fp.scheme_name || (fp.scheme_decision === 'no_scheme_selected' ? 'No scheme selected — concept financing' : fp.scheme_decision === 'no_supported_scheme' ? 'No supported scheme for this project cost' : tr('microFinanceTerm', lang))} />
          <Rows
            rows={[
              [tr('capitalAvailable', lang), `₹${formatINR(fp.capital_available)}`],
              [tr('projectCost', lang), `₹${formatINR(fp.project_cost)}`],
              [tr('bankLoan', lang), fp.loan_amount != null && fp.loan_amount > 0 ? `₹${formatINR(fp.loan_amount)}` : fp.scheme_code ? `₹${formatINR(fp.loan_amount)}` : '— (select a scheme)'],
              [tr('interestRatePA', lang), fp.interest_rate != null ? `${fp.interest_rate}%` : '—'],
              [tr('tenure', lang), fp.tenure_years != null ? `${fp.tenure_years} ${tr('yr', lang)}` : '—'],
              [tr('moratorium', lang), fp.moratorium_months != null ? `${fp.moratorium_months} ${tr('mo', lang)} (${fp.moratorium_mode || 'grace'})` : '—'],
              [tr('monthlyEMI', lang), fp.emi != null && fp.emi > 0 ? `₹${formatINR(fp.emi)}` : result.repayment?.monthly_emi != null && result.repayment.monthly_emi > 0 ? `₹${formatINR(result.repayment.monthly_emi)}` : '—'],
              [tr('schemeDecision', lang), fp.scheme_decision || '—'],
            ]}
          />
          {fp.scheme_reason && note(fp.scheme_reason)}
          {(fp.scheme_decision === 'no_scheme_selected' || !fp.scheme_code) && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              Project cost ₹{formatINR(fp.project_cost)} — no scheme selected. Please <a href="/schemes" className="font-bold underline">select a scheme</a> to see scheme-specific financing (interest, tenure, EMI). Showing concept estimates only.
            </div>
          )}
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
                <div className="box-border rounded-lg bg-gray-50 p-3 px-4">
                  <div className="break-words whitespace-normal text-gray-500">{tr('peakMonth', lang)}</div>
                  <div className="break-words whitespace-normal font-semibold text-gray-900">{monthName(si.peak_month, lang)}{si.peak_index != null ? ` · ${si.peak_index}` : ''}</div>
                  {si.peak_reason && <div className="mt-1 text-[11px] leading-snug text-gray-600">{si.peak_reason}</div>}
                </div>
                <div className="box-border rounded-lg bg-gray-50 p-3 px-4">
                  <div className="break-words whitespace-normal text-gray-500">{tr('lowMonth', lang)}</div>
                  <div className="break-words whitespace-normal font-semibold text-gray-900">{monthName(si.low_month, lang)}{si.low_index != null ? ` · ${si.low_index}` : ''}</div>
                  {si.low_reason && <div className="mt-1 text-[11px] leading-snug text-gray-600">{si.low_reason}</div>}
                </div>
              </div>
              {si.peak_explanation && <div className="rounded-lg bg-amber-50 p-2.5 text-xs text-amber-900">📌 {si.peak_explanation}</div>}
              {si.low_explanation && <div className="rounded-lg bg-gray-50 p-2.5 text-xs text-gray-600">🔽 {si.low_explanation}</div>}
              {si.cash_flow_risk_reason && <p className="text-xs text-gray-600">{si.cash_flow_risk_reason}</p>}
              {si.inventory_implication && (
                <div className="box-border rounded-lg bg-brand-50 p-3 px-4 break-words whitespace-normal text-xs text-brand-800">
                  <strong>{tr('inventory', lang)}</strong>{si.inventory_implication}
                  {si.stock_buffer_factor != null ? ` (${tr('buffer', lang)} ×${si.stock_buffer_factor})` : ''}
                </div>
              )}
              {si.recommendation && <p className="text-xs text-gray-700">{si.recommendation}</p>}
              {si.note && <p className="text-[11px] italic text-gray-500">{si.note}</p>}
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
                <li key={i} className="box-border rounded-lg bg-gray-50 p-3 px-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 whitespace-normal">
                    <span className="break-words whitespace-normal font-medium text-gray-900">{p.product || tr('product', lang)}</span>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge color={relevanceColor(p.relevance)}>{p.relevance || '—'}</Badge>
                      <span className="break-words whitespace-normal text-[10px] text-gray-500">{p.confidence || '—'} {tr('confidence', lang)}</span>
                    </div>
                  </div>
                  {p.reason && <p className="mt-1 break-words whitespace-normal text-xs text-gray-600">{p.reason}</p>}
                  {p.evidence && <p className="mt-1 break-words whitespace-normal text-[11px] italic text-gray-500">{p.evidence}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">{tr('noProductRecs', lang)}</p>
          )}
        </Card>
      </div>

      {/* Business Setup + Navigation — side-by-side in one card; hide Business Setup button when AVOID */}
      {(() => {
        const v = (result as any).viability
        if (v?.decision === 'AVOID') return null
        return (
          <Card>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              {/* Left: Business Setup */}
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-gray-900">Business Setup</div>
                <p className="mt-1 text-xs leading-relaxed text-gray-500">Review startup requirements, inventory and recommended budget split.</p>
                <a href="/business-setup" className="mt-3 inline-flex rounded-xl bg-brand-600 px-5 py-2 text-sm font-bold text-white hover:bg-brand-700">Go to Business Setup →</a>
              </div>
              {/* Divider */}
              <div className="hidden sm:block h-20 w-px bg-gray-200" />
              <div className="sm:hidden h-px bg-gray-200" />
              {/* Right: Navigation helpers */}
              <div className="min-w-0 flex-1 sm:text-right">
                <div className="text-sm font-semibold text-gray-900">Want to try different business, location or capital?</div>
                <div className="mt-3 flex flex-wrap gap-2 sm:justify-end">
                  <a href="/analyze" className="rounded-xl bg-brand-600 px-5 py-2 text-sm font-bold text-white hover:bg-brand-700">Back to Analyze & Change Input →</a>
                  <a href="/" className="rounded-xl border border-slate-200 bg-white px-5 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50">Exit to Home</a>
                </div>
              </div>
            </div>
          </Card>
        )
      })()}

      {/* 6. FINANCING — already shown above; working capital & scale fit */}
      {(() => {
        const wc = (result as any).working_capital
        if (!wc) return null
        return (
          <Card>
            <CardHeader title="Working Capital / Survival Buffer" subtitle={`Modelled estimate: ₹${formatINR(wc.estimated_working_capital_requirement)}`} />
            <ul className="space-y-1 text-xs text-gray-600">
              {wc.reasons.map((r:string,i:number)=><li key={i}>• {r}</li>)}
            </ul>
            <p className="mt-2 text-[11px] italic text-gray-500">{wc.disclaimer}</p>
          </Card>
        )
      })()}

      {(() => {
        const sf = (result as any).scale_fit
        if (!sf) return null
        return (
          <Card>
            <CardHeader title="Business Scale Fit" subtitle={sf.reason || ''} />
            <div className="grid gap-2 md:grid-cols-3">
              {sf.scales.map((s:any)=>(
                <div key={s.scale} className={`rounded-lg p-3 text-xs ${s.scale===sf.recommended_scale?'bg-teal-50 border border-teal-200':'bg-gray-50'}`}>
                  <div className="font-bold capitalize">{s.scale} {s.scale===sf.recommended_scale?'★':''}</div>
                  <div>Project ₹{formatINR(s.project_cost)}</div>
                  <div>Gap ₹{formatINR(s.required_financing)}</div>
                  <div>Scheme {s.scheme || '—'} · EMI ₹{formatINR(s.emi)} · {s.repayment_health}</div>
                  {s.cash_surplus!=null && <div>Cash surplus ₹{formatINR(s.cash_surplus)}</div>}
                  <div className="mt-1 text-[10px] text-gray-500">Fit {s.fit_score}/100</div>
                </div>
              ))}
            </div>
            {sf.recommended_scale && <p className="mt-2 text-sm font-semibold text-teal-700">Recommended scale: {sf.recommended_scale} <span className="text-xs font-normal text-gray-600">— best fit for your capital of ₹{formatINR(sf.capital_available)} based on financing gap and repayment health</span></p>}
          </Card>
        )
      })()}

      {/* 7. RISK / CONSTRAINTS — what is limiting */}
      {(() => {
        const c = (result as any).constraints
        if (!c || !c.constraints?.length) return null
        return (
          <Card>
            <CardHeader title="What Is Limiting My Business?" subtitle={`${c.count} constraint(s) · top is ${c.top_constraint?.severity || ''}`} />
            <div className="space-y-2">
              {c.constraints.slice(0,5).map((con:any,i:number)=>(
                <div key={i} className="rounded-lg bg-gray-50 p-3">
                  <div className="flex items-center gap-2">
                    <Badge color={con.severity==='HIGH'?'red':con.severity==='MEDIUM'?'amber':'gray'}>{con.severity}</Badge>
                    <span className="text-sm font-semibold text-gray-800">{con.factor}</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-600">{con.detail}</div>
                  {con.evidence && <div className="text-[11px] italic text-gray-500">Evidence: {con.evidence}</div>}
                  {con.action && <div className="mt-1 text-xs text-teal-700">→ {con.action}</div>}
                </div>
              ))}
            </div>
          </Card>
        )
      })()}



    </div>
  )
}

function NoResult({ lang }: { lang: Language }) {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <div className="text-4xl">🌾</div>
      <h2 className="mt-4 text-xl font-bold text-gray-900">{tr('noAnalysisYet', lang)}</h2>
      <p className="mt-2 text-sm text-gray-500">{tr('noAnalysisDesc', lang)}</p>
      <a href="/analyze" className="mt-4 inline-block rounded-lg bg-teal-600 px-5 py-2 text-sm font-medium text-white hover:bg-teal-700">
        {tr('analyzeBusiness', lang)}
      </a>
    </div>
  )
}



function Rows({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="divide-y divide-gray-100">
      {rows.map(([k, v]) => (
        <div key={k} className="flex min-w-0 flex-wrap items-center justify-between gap-3 whitespace-normal py-2 text-sm box-border px-1">
          <dt className="min-w-0 flex-1 break-words whitespace-normal text-gray-500">{k}</dt>
          <dd className="shrink-0 break-words whitespace-normal text-right font-medium text-gray-900">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function MiniStat({ label, value, symbol, suffix }: { label: string; value?: number; symbol?: string; suffix?: string }) {
  return (
    <div className="min-w-0 box-border rounded-lg bg-teal-50 p-3 px-4">
      <div className="break-words whitespace-normal text-[11px] leading-tight text-gray-500">{label}</div>
      <div className="break-words whitespace-normal text-base font-bold text-gray-900">
        {symbol || ''}
        {value != null ? formatINR(value) : '—'}
        {suffix ? <span className="break-words whitespace-normal text-[10px] font-normal text-gray-500"> {suffix}</span> : null}
      </div>
    </div>
  )
}

function LedgerRow({ label, value, suffix, bold, highlight }: { label: string; value?: number; suffix?: string; bold?: boolean; highlight?: boolean }) {
  return (
    <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 whitespace-normal py-1 box-border px-1">
      <span className={`min-w-0 flex-1 break-words whitespace-normal text-gray-500 ${bold ? 'font-semibold text-gray-700' : ''}`}>{label}</span>
      <span className={`shrink-0 break-words whitespace-normal text-right font-medium text-gray-900 ${bold ? 'font-semibold' : ''} ${highlight ? 'text-green-700' : ''}`}>
        ₹{formatINR(value)}
        {suffix ? <span className="break-words whitespace-normal text-[10px] font-normal text-gray-500"> {suffix}</span> : null}
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
  return <p className="mt-2 box-border break-words whitespace-normal rounded-lg bg-gray-50 p-3 px-4 text-xs leading-relaxed text-gray-600">{text}</p>
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

function seasonLabelColor(v: string | undefined): any {
  return v === 'PEAK' ? 'green' : v === 'HIGH' ? 'blue' : v === 'SOFT' ? 'amber' : v === 'LOW' ? 'gray' : 'gray'
}

function riskColor(v: string | undefined): any {
  return v === 'HIGH' ? 'red' : v === 'MEDIUM' ? 'amber' : 'gray'
}

function relevanceColor(v: string | undefined): any {
  return v === 'high' ? 'green' : v === 'medium' ? 'amber' : 'gray'
}
