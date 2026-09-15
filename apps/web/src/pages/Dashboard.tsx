import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { useNavigate } from 'react-router-dom'
import { useAnalysis } from '../lib/analysisStore'
import { LINK_BRAND } from '../lib/theme'
import { Badge, Card, CardHeader, Disclaimer } from '../components/ui'
import { Spotlight } from '../components/aceternity/BackgroundBeams'
import { tr, interpolate, recommendationLabel, schemeDecisionLabel, type Language } from '../lib/i18n'

const RECO_COLOR: Record<string, string> = { GO: 'green', MODIFY: 'amber', AVOID: 'red' }

export function Dashboard() {
  const { result, lang } = useAnalysis()
  const navigate = useNavigate()
  if (!result) return <NoResult lang={lang} />

  const { recommendation, financial_plan: fp, profit_model: pm } = result
  const me = result.monthly_economics
  const si = result.seasonal_intelligence
  const prs = result.product_recommendations
  // AI Suggested Opportunities removed - no longer shown on Dashboard per requirements

  return (
    <div className="space-y-6">
      <Spotlight>
        <div className="flex flex-col gap-3 rounded-xl border border-teal-100 bg-gradient-to-br from-white via-teal-50/50 to-cyan-50/30 p-4 px-4 sm:px-6 box-border sm:flex-row sm:items-center sm:justify-between dark:border-teal-800/40 dark:from-slate-800 dark:via-teal-950/25 dark:to-slate-900">
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
          <Card className={`border-2 ${v.decision === 'GO' ? 'border-green-200 bg-green-50/40 dark:border-green-800/50 dark:bg-green-950/25' : v.decision === 'AVOID' ? 'border-red-200 bg-red-50/40 dark:border-red-800/50 dark:bg-red-950/25' : 'border-amber-200 bg-amber-50/40 dark:border-amber-800/50 dark:bg-amber-950/25'}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-xs font-bold uppercase tracking-widest text-gray-500 dark:text-slate-400">{tr('finalDecision', lang)}</div>
                <div className={`mt-1 text-3xl font-black tracking-tight ${v.decision === 'GO' ? 'text-green-700 dark:text-green-300' : v.decision === 'AVOID' ? 'text-red-700 dark:text-red-300' : 'text-amber-700 dark:text-amber-300'}`}>{v.decision}</div>
                <div className="mt-1 text-xs text-gray-500 dark:text-slate-400">{interpolate(tr('scoreConfidence', lang), { score: v.score, conf: v.confidence, raw: v.confidence_score })}</div>
              </div>
              <Badge color={color}>{v.decision}</Badge>
            </div>
            <p className="mt-3 text-sm text-gray-700 dark:text-slate-300">{translateDynamic(v.reason, lang)}</p>
            {/* 2. WHY — top 3 reasons */}
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div className="rounded-lg bg-white p-3 dark:bg-slate-800 dark:border dark:border-slate-700/40">
                <div className="text-xs font-semibold text-green-700 dark:text-green-300">{tr('topPositives', lang)}</div>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-gray-700 dark:text-slate-300">
                  {(v.top_positive_factors || []).slice(0,3).map((f:string,i:number)=><li key={i}>{translateDynamic(f, lang)}</li>)}
                </ul>
              </div>
              <div className="rounded-lg bg-white p-3 dark:bg-slate-800 dark:border dark:border-slate-700/40">
                <div className="text-xs font-semibold text-red-700 dark:text-red-300">{tr('topNegatives', lang)}</div>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-gray-700 dark:text-slate-300">
                  {(v.top_negative_factors || []).slice(0,3).map((f:string,i:number)=><li key={i}>{translateDynamic(f, lang)}</li>)}
                </ul>
              </div>
            </div>
            {v.recommended_actions?.length ? (
              <div className="mt-3 rounded-lg bg-white p-3 dark:bg-slate-800 dark:border dark:border-slate-700/40">
                <div className="text-xs font-semibold text-gray-700 dark:text-slate-200">{tr('recommendedActions', lang)}</div>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-gray-700 dark:text-slate-300">
                  {v.recommended_actions.slice(0,3).map((a:string,i:number)=><li key={i}>{translateDynamic(a, lang)}</li>)}
                </ul>
              </div>
            ): null}
            <div className="mt-4 border-t border-gray-100 pt-4 dark:border-slate-700/50">
              <div className="text-sm font-semibold text-gray-900 dark:text-white">{tr('wantToTryDifferent', lang)}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <a href="/analyze" className="rounded-xl bg-brand-600 px-5 py-2 text-sm font-bold text-white hover:bg-brand-700">{tr('backToAnalyze', lang)}</a>
                <a href="/" className="rounded-xl border border-slate-200 bg-white px-5 py-2 text-sm font-bold text-slate-700 hover:bg-slate-50 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200">{tr('exitToHome', lang)}</a>
              </div>
            </div>
          </Card>
        )
      })()}

      {/* 3. LOCATION — exact point + competition + accessibility */}
      {(() => {
        const ls = (result as any).location_suitability
        if (!ls) return null
        return (
          <Card>
            <CardHeader title={tr('locationSuitability', lang)} subtitle={`${ls.suitability_score}/100 · confidence ${ls.confidence}`} />
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-lg bg-green-50 p-3">
                <div className="text-xs font-semibold text-green-800">{tr('strengths', lang)}</div>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-gray-700">
                  {ls.strengths.map((s:string,i:number)=><li key={i}>{translateBackend(s, lang)}</li>)}
                </ul>
              </div>
              <div className="rounded-lg bg-amber-50 p-3">
                <div className="text-xs font-semibold text-amber-800">{tr('concerns', lang)}</div>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-gray-700">
                  {ls.concerns.map((s:string,i:number)=><li key={i}>{translateBackend(s, lang)}</li>)}
                </ul>
              </div>
            </div>
            <div className="mt-2 text-xs text-gray-500">{result.location.village || result.location.block} · {result.location.district} · {result.location.uses_proposed_location ? interpolate(tr('exactLocation', lang), { coords: `${Number(result.location.proposed_latitude).toFixed(4)}, ${Number(result.location.proposed_longitude).toFixed(4)}` }) : interpolate(tr('centroidLocation', lang), { coords: `${Number(result.location.latitude).toFixed(4)}, ${Number(result.location.longitude).toFixed(4)}` }) } · {result.location.geo_precision}</div>
            <p className="mt-1 text-[11px] italic text-gray-500">{translateBackend(ls.note, lang)}</p>
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
                  {(me.notes || []).map((n: string, i: number) => <p key={i} className="text-[11px] italic text-gray-500">{translateBackend(n, lang)}</p>)}
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
          <CardHeader title={tr('financialPlan', lang)} subtitle={fp.scheme_name || (fp.scheme_decision === 'no_scheme_selected' ? tr('noSchemeSelectedConcept', lang) : fp.scheme_decision === 'no_supported_scheme' ? tr('noSupportedSchemeCost', lang) : tr('microFinanceTerm', lang))} />
          <Rows
            rows={[
              [tr('capitalAvailable', lang), `₹${formatINR(fp.capital_available)}`],
              [tr('projectCost', lang), `₹${formatINR(fp.project_cost)}`],
              [tr('bankLoan', lang), fp.loan_amount != null && fp.loan_amount > 0 ? `₹${formatINR(fp.loan_amount)}` : fp.scheme_code ? `₹${formatINR(fp.loan_amount)}` : `— (${tr('selectSchemeShort', lang)})`],
              [tr('interestRatePA', lang), fp.interest_rate != null ? `${fp.interest_rate}%` : '—'],
              [tr('tenure', lang), fp.tenure_years != null ? `${fp.tenure_years} ${tr('yr', lang)}` : '—'],
              [tr('moratorium', lang), fp.moratorium_months != null ? `${fp.moratorium_months} ${tr('mo', lang)} (${fp.moratorium_mode || 'grace'})` : '—'],
              [tr('monthlyEMI', lang), fp.emi != null && fp.emi > 0 ? `₹${formatINR(fp.emi)}` : result.repayment?.monthly_emi != null && result.repayment.monthly_emi > 0 ? `₹${formatINR(result.repayment.monthly_emi)}` : '—'],
              [tr('schemeDecision', lang), fp.scheme_decision ? schemeDecisionLabel(fp.scheme_decision, lang) : '—'],
            ]}
          />
          {fp.scheme_reason && note(translateBackend(fp.scheme_reason, lang))}
          {(fp.scheme_decision === 'no_scheme_selected' || !fp.scheme_code) && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              {interpolate(tr('noSchemeSelectedCost', lang), { cost: `₹${formatINR(fp.project_cost)}` })} {tr('pleaseSelectScheme', lang)} <a href="/schemes" className="font-bold underline">{tr('schemesPageLink', lang)}</a> {tr('toSeeInterestTenure', lang)}
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
                  {si.peak_reason && <div className="mt-1 text-[11px] leading-snug text-gray-600">{translateSeasonalReason(si.peak_reason, lang)}</div>}
                </div>
                <div className="box-border rounded-lg bg-gray-50 p-3 px-4">
                  <div className="break-words whitespace-normal text-gray-500">{tr('lowMonth', lang)}</div>
                  <div className="break-words whitespace-normal font-semibold text-gray-900">{monthName(si.low_month, lang)}{si.low_index != null ? ` · ${si.low_index}` : ''}</div>
                  {si.low_reason && <div className="mt-1 text-[11px] leading-snug text-gray-600">{translateSeasonalReason(si.low_reason, lang)}</div>}
                </div>
              </div>
              {si.peak_explanation && <div className="rounded-lg bg-amber-50 p-2.5 text-xs text-amber-900">📌 {interpolate(tr('peakInMonth', lang), { month: monthName(si.peak_month, lang), index: si.peak_index ?? '' })} {translateSeasonalReason(si.peak_reason, lang)}</div>}
              {si.low_explanation && <div className="rounded-lg bg-gray-50 p-2.5 text-xs text-gray-600">🔽 {interpolate(tr('lowInMonth', lang), { month: monthName(si.low_month, lang), index: si.low_index ?? '' })} {translateSeasonalReason(si.low_reason, lang)}</div>}
              {si.cash_flow_risk_reason && <p className="text-xs text-gray-600">{translateSeasonalReason(si.cash_flow_risk_reason, lang)}</p>}
              {si.inventory_implication && (
                <div className="box-border rounded-lg bg-brand-50 p-3 px-4 break-words whitespace-normal text-xs text-brand-800">
                  <strong>{tr('inventory', lang)}</strong>{translateInventory(si.inventory_implication, si, lang)}
                  {si.stock_buffer_factor != null ? ` (${tr('buffer', lang)} ×${si.stock_buffer_factor})` : ''}
                </div>
              )}
              {si.recommendation && <p className="text-xs text-gray-700">{translateBackend(si.recommendation, lang)}</p>}
              {si.note && <p className="text-[11px] italic text-gray-500">{translateBackend(si.note, lang)}</p>}
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
                    <span className="break-words whitespace-normal font-medium text-gray-900">{translateProductName(p.product, lang)}</span>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge color={relevanceColor(p.relevance)}>{p.relevance || '—'}</Badge>
                      <span className="break-words whitespace-normal text-[10px] text-gray-500">{p.confidence || '—'} {tr('confidence', lang)}</span>
                    </div>
                  </div>
                  {p.reason && <p className="mt-1 break-words whitespace-normal text-xs text-gray-600">{translateProductReason(p.reason, lang)}</p>}
                  {p.evidence && <p className="mt-1 break-words whitespace-normal text-[11px] italic text-gray-500">{translateBackend(p.evidence, lang)}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">{tr('noProductRecs', lang)}</p>
          )}
        </Card>
      </div>

      {(() => {
        const sf = (result as any).scale_fit
        if (!sf) return null
        return (
          <Card>
            <CardHeader title={tr('businessScaleFitTitle', lang)} subtitle={sf.reason || ''} />
            <div className="grid gap-2 md:grid-cols-3">
              {sf.scales.map((s:any)=>(
                <div key={s.scale} className={`rounded-lg p-3 text-xs ${s.scale===sf.recommended_scale?'bg-teal-50 border border-teal-200':'bg-gray-50'}`}>
                  <div className="font-bold capitalize">{s.scale} {s.scale===sf.recommended_scale?'★':''}</div>
                  <div>{interpolate(tr('scaleProjectAmount', lang), { amount: formatINR(s.project_cost) })}</div>
                  <div>{interpolate(tr('scaleGapAmount', lang), { amount: formatINR(s.required_financing) })}</div>
                  <div>{interpolate(tr('scaleSchemeEmi', lang), { scheme: s.scheme || '—', emi: formatINR(s.emi), health: s.repayment_health || '—' })}</div>
                  {s.cash_surplus!=null && <div>{interpolate(tr('scaleCashSurplus', lang), { amount: formatINR(s.cash_surplus) })}</div>}
                  <div className="mt-1 text-[10px] text-gray-500">{interpolate(tr('fitLabel', lang), { score: s.fit_score })}</div>
                </div>
              ))}
            </div>
            {sf.recommended_scale && <p className="mt-2 text-sm font-semibold text-teal-700">{interpolate(tr('recommendedScale', lang), { scale: sf.recommended_scale })} <span className="text-xs font-normal text-gray-600">{interpolate(tr('bestFitForCapital', lang), { capital: formatINR(sf.capital_available) })}</span></p>}
          </Card>
        )
      })()}

      {/* 7. RISK / CONSTRAINTS — what is limiting */}
      {(() => {
        const c = (result as any).constraints
        if (!c || !c.constraints?.length) return null
        return (
          <Card>
            <CardHeader title={tr('whatIsLimiting', lang)} subtitle={interpolate(tr('constraintCount', lang), { count: c.count, severity: c.top_constraint?.severity || '' })} />
            <div className="space-y-2">
              {c.constraints.slice(0,5).map((con:any,i:number)=>(
                <div key={i} className="rounded-lg bg-gray-50 p-3">
                  <div className="flex items-center gap-2">
                    <Badge color={con.severity==='HIGH'?'red':con.severity==='MEDIUM'?'amber':'gray'}>{con.severity}</Badge>
                    <span className="text-sm font-semibold text-gray-800">{translateConstraintFactor(con.factor, lang)}</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-600">{translateBackend(con.detail, lang)}</div>
                  {con.evidence && <div className="text-[11px] italic text-gray-500">{tr('evidenceLabel', lang)} {translateBackend(con.evidence, lang)}</div>}
                  {con.action && <div className="mt-1 text-xs text-teal-700">{interpolate(tr('actionPrefix', lang), { action: translateBackend(con.action, lang) })}</div>}
                </div>
              ))}
            </div>
          </Card>
        )
      })()}

      {/* Go to Business Setup — final CTA at absolute end */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-900">{tr('businessSetupTitle', lang)}</div>
            <p className="mt-1 text-xs leading-relaxed text-gray-500">{tr('businessSetupDesc', lang)}</p>
          </div>
          <button onClick={() => navigate('/business-setup')} className="rounded-xl bg-brand-600 px-6 py-2.5 text-sm font-bold text-white hover:bg-brand-700">{tr('goToBusinessSetup', lang)} →</button>
        </div>
      </Card>

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

function translateDynamic(text: string, lang: Language): string {
  if (!text || lang === 'en') return text
  const map: Record<string, keyof typeof import('../lib/i18n').dict> = {
    'Repayment health is High Risk and business shows negative cash surplus': 'dynRepaymentHighRisk',
    'Adequate local demand (100/100)': 'dynAdequateDemand',
    'Good accessibility (80/100)': 'dynGoodAccessibility',
    'Consider an alternate business category or location with stronger demand and lower competition.': 'dynConsiderAlternate',
  }
  const key = map[text]
  if (key) return tr(key, lang)
  return translateBackend(text, lang)
}

function translateBackend(text: string, lang: Language): string {
  if (!text || lang === 'en') return text
  const map: Record<string, keyof typeof import('../lib/i18n').dict> = {
    // Seasonal notes & risks
    'Seasonal indexes are modelled from the category\'s festival, harvest and school calendar. Validate with local records.': 'seasonalNoteModel',
    'Demand swings notably across the year; working capital and cash flow are exposed to seasonal troughs.': 'seasonalRiskHigh',
    'Moderate seasonal variation; buffer stock/credit care is advisable before peaks.': 'seasonalRiskMedium',
    'Demand is broadly stable through the year.': 'seasonalRiskLow',
    // Seasonal peak / low reasons (full strings from _PEAK_REASONS / _LOW_REASONS)
    'Diwali (Nov) and post-harvest (Oct) bring higher rural incomes and festival stocking by households.': 'seasonalPeakGrocery',
    'November festival season (Diwali) lifts sweet/milk demand; summer heat mildly depresses fluid milk sales.': 'seasonalPeakDairy',
    'Festival and wedding season in Oct–Nov raises demand for chicken and eggs.': 'seasonalPeakPoultry',
    'Pre-wedding and Pongal/Diwali festival buying (Jun, Oct) drives tailoring and garment sales.': 'seasonalPeakTextile',
    'Mango and agricultural harvest in Aug raises raw-material supply for processing and packed-food demand.': 'seasonalPeakFoodProcessing',
    'Festival and harvest bonus months (Oct–Nov) raise out-of-home eating near markets.': 'seasonalPeakRestaurant',
    'Kharif harvest marketing (Aug–Sep) concentrates cash inflow and input buying.': 'seasonalPeakAgriculture',
    'Post-harvest and pre-festival orders (Aug–Sep) lift demand from rural buyers.': 'seasonalPeakManufacturing',
    'Festival gifting (Sep) and tourist season drive craft purchases.': 'seasonalPeakHandicrafts',
    'Festival bonuses (Sep–Oct) modestly lift discretionary electronics buying.': 'seasonalPeakMobileShop',
    'Monsoon-related fever and winter cold (Aug, Jan) lift mild seasonal illness demand.': 'seasonalPeakPharmacy',
    'Local events and festival calendar modestly lift footfall.': 'seasonalPeakOther',
    'Lean post-festival months (Jan–Feb) after household stocking subsides.': 'seasonalLowGrocery',
    'Summer (Jun–Jul) heat raises spoilage and lowers fluid milk appetite; fodder cost rises.': 'seasonalLowDairy',
    'Hot pre-monsoon (Mar–Apr) mildly softens poultry appetite.': 'seasonalLowPoultry',
    'Post-festival lull (Apr) with few weddings and low replacement demand.': 'seasonalLowTextile',
    'Lean pre-harvest (Jan–Feb) when raw material is scarce.': 'seasonalLowFoodProcessing',
    'Quiet Jan–Feb before harvest incomes arrive.': 'seasonalLowRestaurant',
    'Lean pre-sowing (Jan–Feb) when no crop income is realised.': 'seasonalLowAgriculture',
    'Lean Jan–Feb before rural cash flows pick up.': 'seasonalLowManufacturing',
    'Lean Jan when festival gifting is over.': 'seasonalLowHandicrafts',
    'No strong seasonality — stable through most months.': 'seasonalLowMobileShop',
    'Mild summer (May) sees fewer seasonal illnesses.': 'seasonalLowPharmacy',
    'Demand is broadly even across the year.': 'seasonalLowOther',
    // Generic backend strings
    'Location-specific evidence unavailable.': 'locationNoteFallback',
    // Location suitability strengths / concerns (Dashboard Location Suitability)
    'Good accessibility (near market/transport)': 'lsStrengthAccess',
    'Low to moderate competition in catchment': 'lsStrengthCompetition',
    'Strong surrounding population evidence': 'lsStrengthPopulation',
    'Nearby market/transport infrastructure': 'lsStrengthInfra',
    'No strong location advantages identified in current evidence': 'lsStrengthNoAdv',
    'Limited accessibility — distant from market hub': 'lsConcernAccess',
    'High mapped competition — site selection will matter': 'lsConcernCompetition',
    'Weak demand evidence for this catchment': 'lsConcernDemand',
    'Limited market evidence for this category/location': 'lsConcernMarket',
    'No major location concerns detected': 'lsConcernNoConcerns',
    'Derived from existing competition, accessibility, demand and market evidence (not a separate model).': 'lsNoteDerived',
    'Population is historical Census 2011 baseline — not current.': 'lsReasonHistorical',
    'Competition data completeness is low.': 'lsReasonLowCompetition',
  }
  const key = map[text]
  if (key) return tr(key, lang)
  // fallback: try substring match for composite strings containing known phrase
  for (const [eng, k] of Object.entries(map)) {
    if (text.includes(eng) && eng.length > 20) {
      return text.replace(eng, tr(k as any, lang))
    }
  }
  return text
}

function translateSeasonalReason(text: string, lang: Language): string {
  return translateBackend(text, lang)
}

function translateProductName(text: string, lang: Language): string {
  if (!text || lang === 'en') return text
  const map: Record<string, keyof typeof import('../lib/i18n').dict> = {
    'Festive essentials (oils, grains, sweets)': 'productFestiveEssentials',
    'Fresh milk & dairy': 'productFreshMilkDairy',
    'Packaged snacks & beverages': 'productPackagedSnacks',
    'Household consumables (soap, detergent)': 'productHouseholdConsumables',
    'Curd & paneer': 'productCurdPaneer',
    'Ghee (festive)': 'productGheeFestive',
    'Fresh milk (daily supply)': 'productFreshMilkDaily',
    'Broiler chicken (live/dressed)': 'productBroiler',
    'Eggs (tray/retail)': 'productEggs',
    'Festive & wedding wear': 'productFestiveWeddingWear',
    'School uniforms': 'productSchoolUniforms',
    'Everyday casuals/work wear': 'productEverydayCasuals',
    'Mango pulp / pickle (seasonal)': 'productMangoPulp',
    'Millet and spice packs': 'productMilletSpice',
    'Meals / biryani (evening)': 'productMealsBiryani',
    'Tea, coffee and snacks': 'productTeaCoffee',
    'Sowing-season seeds & inputs': 'productSowingSeeds',
    'Post-harvest storage & packaging': 'productPostHarvest',
    'Fertilizer top-up': 'productFertilizerTopup',
    'Fever/cold essentials (paracetamol, ORS)': 'productFeverCold',
    'Chronic care (BP, diabetes)': 'productChronicCare',
    'Recharges & accessories': 'productRecharges',
    'Repairs & servicing': 'productRepairs',
    'Job-work for local agri/fabrication': 'productJobWork',
    'Spare parts & fabrication': 'productSpareParts',
    'Festive gift sets': 'productFestiveGift',
    'Everyday decor utility': 'productEverydayDecor',
    'Haircut & grooming': 'productHaircut',
    'Bridal/occasion packages': 'productBridal',
    'Core service / core product': 'productCoreService',
  }
  const key = map[text]
  if (key) return tr(key, lang)
  return text
}

function translateProductReason(text: string, lang: Language): string {
  if (!text || lang === 'en') return text
  const map: Record<string, keyof typeof import('../lib/i18n').dict> = {
    'Households stock oils and staples ahead of Diwali/Pongal — campus and nearby provision stores report 20-30% lift in Oct-Nov.': 'productReasonFestiveEssentials',
    'Cooling dairy sees peak demand in hot months (Apr-Jun) when curd consumption rises.': 'productReasonCurdPaneer',
    'Ghee demand lifts around festivals and weddings (Oct-Nov, Jun) for sweets and rituals.': 'productReasonGhee',
    'Core daily income; tie up with 2-3 village collection points for steady supply.': 'productReasonFreshMilkDaily',
  }
  const key = map[text]
  if (key) return tr(key, lang)
  return translateBackend(text, lang)
}

function translateConstraintFactor(text: string, lang: Language): string {
  if (!text || lang === 'en') return text
  const map: Record<string, keyof typeof import('../lib/i18n').dict> = {
    'Insufficient own capital': 'factorInsufficientCapital',
    'Financing cap exceeded': 'factorFinancingCap',
    'High competition': 'factorHighCompetition',
    'Moderate competition': 'factorModerateCompetition',
    'Weak market evidence': 'factorWeakMarket',
    'Low gross margin': 'factorLowGrossMargin',
    'High operating expenses': 'factorHighOpex',
    'Poor repayment capacity': 'factorPoorRepayment',
    'Moderate repayment capacity': 'factorModerateRepayment',
    'Seasonal risk': 'factorSeasonalRisk',
    'Location accessibility': 'factorLocationAccess',
    'Weak health infrastructure': 'factorWeakHealth',
    'Insufficient data confidence': 'factorInsufficientData',
  }
  const key = map[text]
  if (key) return tr(key, lang)
  return text
}

function translateInventory(text: string, si: any, lang: Language): string {
  if (!text || lang === 'en') return text
  // Check stable case
  if (text.startsWith('Demand is stable through the year')) {
    const reason = translateSeasonalReason(si?.peak_reason || '', lang)
    return `${tr('seasonalInventoryStable', lang)} ${reason}`.trim()
  }
  if (text.includes('Demand peaks in')) {
    const peakReason = translateSeasonalReason(si?.peak_reason || '', lang)
    const month = monthName(si?.peak_month, lang)
    const idx = si?.peak_index ?? ''
    const buf = si?.stock_buffer_factor ?? ''
    const prefix = interpolate(tr('seasonalInventoryPrefix', lang), { month, index: idx })
    const suffix = interpolate(tr('seasonalInventorySuffix', lang), { buffer: buf })
    return `${prefix} ${peakReason} ${suffix}`.trim()
  }
  return translateBackend(text, lang)
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
