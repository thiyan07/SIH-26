import { useMemo, useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader, Disclaimer, StatCard, Badge } from '../components/ui'
import { schedule, emi } from '../lib/finance'
import { tr, interpolate, schemeDecisionLabel, type Language } from '../lib/i18n'
import { formatINR } from './Dashboard'
import { LoanComparison } from '../components/LoanComparison'
import { CalendarReminders } from '../components/CalendarReminders'

export function Finance() {
  const { result, setResult, form, lang, selectedSchemeCode, selectedSchemeName } = useAnalysis()
  const fp = result?.financial_plan as any
  const repayment = result?.repayment as any
  const [tabs, setTabs] = useState<'plan' | 'schedule' | 'compare'>('plan')
  const [recalcLoading, setRecalcLoading] = useState(false)

  const months = fp?.tenure_years != null ? fp.tenure_years * 12 : 0
  const moratorium = fp?.moratorium_months ?? 0
  const loan = fp?.loan_amount ?? 0
  const rate = fp?.interest_rate ?? 0
  const fundingGap = fp ? Math.max(0, fp.project_cost - fp.capital_available) : 0
  const isSchemeDriven = selectedSchemeCode && fp?.scheme_code === selectedSchemeCode
  const needsRecalc = selectedSchemeCode && fp?.scheme_code !== selectedSchemeCode

  const handleApplyScheme = async () => {
    if (!selectedSchemeCode || !form || !result) return
    setRecalcLoading(true)
    try {
      const { api } = await import('../lib/api')
      const payload: any = {
        ...form,
        preferred_scheme_code: selectedSchemeCode,
        state: (form as any).state || result.location.state,
        district: (form as any).district || result.location.district,
        block: (form as any).block || result.location.block,
        village: (form as any).village || result.location.village,
        capital_available: (form as any).capital_available || result.financial_plan.capital_available,
        category_code: (form as any).category_code || (result as any).profit_model?.category_code,
      }
      if ((result as any).location?.proposed_latitude) {
        payload.proposed_latitude = (result as any).location.proposed_latitude
        payload.proposed_longitude = (result as any).location.proposed_longitude
      }
      const res = await api.post<any>('/analysis', payload)
      setResult(res)
    } finally { setRecalcLoading(false) }
  }

  // Canonical financial values come from backend unified_financial / loan_explainer — no duplicate frontend formulas.
  const uf = (result as any)?.unified_financial
  const le = (result as any)?.loan_explainer
  const monthlyEmi = (uf?.emi ?? result?.repayment?.monthly_emi ?? fp?.emi ?? emi(loan, rate, months)) || 0
  const rows = useMemo(() => {
    if (le?.repayment_schedule?.rows?.length) {
      return le.repayment_schedule.rows.map((r:any)=>({ month: r.month, payment: r.payment, interest: r.interest, principal: r.principal, balance: r.balance }))
    }
    return schedule(loan, rate, months, moratorium)
  }, [le, loan, rate, months, moratorium])
  const repayHealth = repayment?.health_label || '—'
  const me = result?.monthly_economics as any

  if (!result || !fp) return <Empty lang={lang} />
  const costBreakdown = (result as any).cost_breakdown as {
    category_code: string
    scale: string
    capital_expenditure: Record<string, number>
    working_capital: Record<string, number>
    infrastructure: Record<string, number>
    licensing_compliance: Record<string, number>
    contingency_pct: number
    contingency_amount: number
    total_project_cost: number
    location_factor: number
    notes: string[]
  } | undefined

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-gray-900">{tr('financeTitle', lang)}</h1>
        <div className="flex items-center gap-2">
          {selectedSchemeCode && (
            <Badge color={isSchemeDriven ? 'green' : 'amber'}>{isSchemeDriven ? `Scheme: ${selectedSchemeName}` : `Selected: ${selectedSchemeCode}`}</Badge>
          )}
          <Badge color={fp.scheme_decision === 'Go' || fp.scheme_decision === 'GO' ? 'green' : fp.scheme_decision === 'NO' ? 'red' : 'amber'}>
            {schemeDecisionLabel(fp.scheme_decision, lang)}
          </Badge>
        </div>
      </div>

      {/* Selected scheme drives finance — show BEFORE vs AFTER */}
      {selectedSchemeCode && (
        <Card>
          <CardHeader title="Financing — Before vs After Scheme" subtitle="The selected scheme's actual terms (interest, tenure, moratorium, eligible loan) are applied to your funding gap" />
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <div className="text-xs font-bold uppercase tracking-widest text-gray-500">Before Scheme (Generic)</div>
              <dl className="mt-2 space-y-1 text-sm text-gray-600">
                <div className="flex justify-between"><dt>Project requirement</dt><dd className="font-medium text-gray-900">₹{formatINR(fp.project_cost)}</dd></div>
                <div className="flex justify-between"><dt>Own capital</dt><dd className="font-medium text-gray-900">₹{formatINR(fp.capital_available)}</dd></div>
                <div className="flex justify-between"><dt>Funding gap</dt><dd className="font-medium text-gray-900">₹{formatINR(fundingGap)}</dd></div>
                <div className="flex justify-between"><dt>Assumption</dt><dd className="text-xs text-gray-500">Micro Finance default 6.5% / 3yr (if no scheme)</dd></div>
              </dl>
            </div>
            <div className="rounded-xl border border-brand-200 bg-brand-50 p-4">
              <div className="text-xs font-bold uppercase tracking-widest text-brand-700">After Scheme {isSchemeDriven ? '✓ Applied' : '— Not yet applied'}</div>
              <dl className="mt-2 space-y-1 text-sm">
                <div className="flex justify-between"><dt className="text-brand-700">Selected scheme</dt><dd className="font-bold text-brand-900">{selectedSchemeName || selectedSchemeCode}</dd></div>
                <div className="flex justify-between"><dt>Eligible financing</dt><dd className="font-medium text-gray-900">₹{formatINR(fp.loan_amount)} {fp.max_loan != null && <span className="text-xs text-gray-500">(max ₹{formatINR(fp.max_loan)})</span>}</dd></div>
                <div className="flex justify-between"><dt>Interest</dt><dd className="font-medium text-gray-900">{fp.interest_rate != null ? `${fp.interest_rate}%` : 'Unknown'} {fp.is_assumed && <span className="text-[10px] text-amber-600">(assumed)</span>}</dd></div>
                <div className="flex justify-between"><dt>Tenure</dt><dd className="font-medium text-gray-900">{fp.tenure_years != null ? `${fp.tenure_years} yr` : 'Unknown'} {fp.moratorium_months ? `· ${fp.moratorium_months} mo moratorium (${fp.moratorium_mode})` : ''}</dd></div>
                <div className="flex justify-between"><dt>Monthly EMI</dt><dd className="font-bold text-brand-700">₹{formatINR((result as any)?.unified_financial?.emi || (result as any)?.repayment?.monthly_emi || 0)}</dd></div>
                {fp.shortfall > 0 && <div className="rounded bg-amber-100 px-2 py-1 text-xs text-amber-800">Shortfall: ₹{formatINR(fp.shortfall)} additional own funding required — loan capped by scheme limit</div>}
                {fp.moratorium_months > 0 && <div className="text-xs text-gray-600">Moratorium: {fp.moratorium_months} months — {fp.moratorium_mode === 'interest_only_during_moratorium' ? 'interest-only during moratorium, principal repayment after' : fp.moratorium_mode}</div>}
              </dl>
              {needsRecalc && (
                <button onClick={handleApplyScheme} disabled={recalcLoading} className="mt-3 w-full rounded-lg bg-brand-600 px-4 py-2 text-xs font-bold text-white hover:bg-brand-700 disabled:opacity-50">
                  {recalcLoading ? 'Recalculating…' : `Apply ${selectedSchemeCode} to Finance → Recalculate`}
                </button>
              )}
              {!isSchemeDriven && !needsRecalc && <div className="mt-2 text-xs text-gray-500">Finance currently shows generic terms. Select a scheme on Schemes page to apply its real terms.</div>}
            </div>
          </div>
          <p className="mt-3 text-xs text-gray-500">Financing = min(funding gap ₹{formatINR(fundingGap)}, scheme max ₹{fp.max_loan != null ? formatINR(fp.max_loan) : '∞'}). Never borrows the maximum allowed — only what you actually need.</p>
        </Card>
      )}

      {/* Cost breakdown — business-specific estimator (req 1) */}
      {costBreakdown && (
        <Card>
          <CardHeader title={tr('costBreakdownTitle', lang) as string || 'Project Cost Estimate'} subtitle={`${costBreakdown.category_code} · ${costBreakdown.scale} · location factor ${costBreakdown.location_factor}x`} />
          <div className="space-y-4">
            <div className="rounded-lg bg-teal-50 p-3 text-sm text-teal-800">
              <strong>{tr('youNeedMore', lang) as string || 'You need more to start this business:'}</strong> {`₹${formatINR(costBreakdown.total_project_cost)}`} total
              {` · ${tr('yourMoney', lang) as string || 'Your own money:'} ₹${formatINR(fp.capital_available)}`}
              {` · ${tr('estimatedFinancingNeeded', lang) as string || 'Estimated financing needed:'} ₹${formatINR(fp.required_financing ?? 0)}`}
              {fp.shortfall > 0 && ` · Shortfall ₹${formatINR(fp.shortfall)}`}
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <CostSection title="Shop / Equipment" items={costBreakdown.capital_expenditure} />
              <CostSection title="Working Capital" items={costBreakdown.working_capital} />
              <CostSection title="Infrastructure" items={costBreakdown.infrastructure} />
              <CostSection title="Licensing" items={costBreakdown.licensing_compliance} />
            </div>
            <div className="flex items-center justify-between border-t pt-2 text-sm">
              <span className="text-gray-500">Contingency ({costBreakdown.contingency_pct}%)</span>
              <span className="font-medium">₹{formatINR(costBreakdown.contingency_amount)}</span>
            </div>
            <div className="flex items-center justify-between border-t pt-2 text-base font-bold">
              <span>Total Project Cost</span>
              <span>₹{formatINR(costBreakdown.total_project_cost)}</span>
            </div>
            {costBreakdown.notes.map((n, i) => <p key={i} className="text-xs text-gray-500">{n}</p>)}
          </div>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label={tr('projectCost', lang)} value={`₹${formatINR(fp.project_cost)}`} sub={tr('projectCostSub', lang)} />
        <StatCard label={tr('loanAmount', lang)} value={`₹${formatINR(fp.loan_amount)}`} sub={`${tr('ownContribution', lang)} ₹${formatINR(fp.own_contribution ?? 0)}`} />
        <StatCard label={tr('monthlyEMI', lang)} value={`₹${formatINR(monthlyEmi)}`} />
        <StatCard label={tr('repayHealth', lang)} value={repayHealth === 'High' || repayHealth === 'High-Risk' || repayHealth === 'High risk' ? tr('highRisk', lang) : repayHealth} />
      </div>

      <CalendarReminders />
      {me && (
        <Card>
          <CardHeader title={tr('monthlyCashflow', lang)} subtitle={tr('cashflowSub', lang)} />
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-5">
            <div className="rounded-lg bg-gray-50 p-3">
              <div className="text-[11px] text-gray-500">{tr('revenue', lang)}</div>
              <div className="text-base font-bold text-gray-900">₹{formatINR(me.monthly_revenue)}</div>
            </div>
            <div className="rounded-lg bg-gray-50 p-3">
              <div className="text-[11px] text-gray-500">{tr('grossProfit', lang)}</div>
              <div className="text-base font-bold text-gray-900">₹{formatINR(me.gross_profit)}{me.gross_margin_pct != null ? <span className="text-[10px] font-normal text-gray-500"> ({me.gross_margin_pct}%)</span> : null}</div>
            </div>
            <div className="rounded-lg bg-gray-50 p-3">
              <div className="text-[11px] text-gray-500">{tr('operatingProfit', lang)}</div>
              <div className="text-base font-bold text-gray-900">₹{formatINR(me.operating_profit)}</div>
            </div>
            <div className="rounded-lg bg-brand-50 p-3">
              <div className="text-[11px] text-gray-500">{tr('cashSurplus', lang)}</div>
              <div className="text-base font-bold text-gray-900">₹{formatINR(me.cash_surplus)}{me.cash_surplus_pct != null ? <span className="text-[10px] font-normal text-gray-500"> ({me.cash_surplus_pct}%)</span> : null}</div>
            </div>
            <div className="rounded-lg bg-gray-50 p-3">
              <div className="text-[11px] text-gray-500">{tr('breakEvenRevenue', lang)}</div>
              <div className="text-base font-bold text-gray-900">
                {me.break_even_state && me.break_even_state !== 'insufficient_data' ? `₹${formatINR(me.break_even_revenue)}` : tr('breakEvenInsufficient', lang)}
              </div>
            </div>
          </div>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title={tr('schemeDerivation', lang)} subtitle={tr('schemeDerivationSub', lang)} />
          <Rows rows={[
            [tr('capitalAvailable', lang), `₹${formatINR(fp.capital_available)}`],
            [tr('scheme', lang), fp.scheme_name || '—'],
            [tr('schemeCode', lang), fp.scheme_code || '—'],
            [tr('interestRate', lang), fp.interest_rate != null ? `${fp.interest_rate}% ${tr('perAnnum', lang)}` : '—'],
            [tr('tenure', lang), fp.tenure_years != null ? `${fp.tenure_years} ${tr('years', lang)}` : '—'],
            [tr('moratorium', lang), fp.moratorium_months != null ? `${fp.moratorium_months} ${tr('months', lang)} (${fp.moratorium_mode})` : '—'],
            [tr('maxLoanable', lang), fp.max_loan != null ? `₹${formatINR(fp.max_loan)}` : '—'],
            [tr('reference', lang), fp.source_document || '—'],
          ]} />
          {fp.scheme_reason && (
            <p className="mt-3 rounded-lg bg-gray-50 p-2 text-xs text-gray-600">{fp.scheme_reason}</p>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <div className="mb-3 flex gap-2">
            <Tab active={tabs === 'plan'} onClick={() => setTabs('plan')}>{tr('planNote', lang)}</Tab>
            <Tab active={tabs === 'schedule'} onClick={() => setTabs('schedule')}>{tr('fullSchedule', lang)}</Tab>
            <Tab active={tabs === 'compare' as any} onClick={() => setTabs('compare' as any)}>Compare 3</Tab>
          </div>
          {tabs === 'plan' ? (
            <div className="space-y-3 text-sm text-gray-600">
              <p>
                {interpolate(tr('planText', lang), {
                  capital: `₹${formatINR(fp.capital_available)}`,
                  cost: `₹${formatINR(fp.project_cost)}`,
                  own: `₹${formatINR(fp.own_contribution ?? 0)}`,
                  req: `₹${formatINR(fp.required_financing ?? 0)}`,
                  loan: `₹${formatINR(fp.loan_amount)}`,
                  rate,
                  years: fp.tenure_years ?? '',
                })}
                {moratorium > 0 ? interpolate(tr('moratoriumPeriodText', lang), { n: moratorium, mode: fp.moratorium_mode || 'grace' }) : ''}.
              </p>
              {fp.shortfall != null && fp.shortfall > 0 && (
                <p className="rounded-lg bg-amber-50 p-2 text-amber-800">
                  <strong>{interpolate(tr('contributionShortfall', lang), { amount: `₹${formatINR(fp.shortfall)}` })}</strong>. {fp.shortfall_reason || tr('addOwnCapital', lang)}
                </p>
              )}
              <p>
                {interpolate(tr('estimatedInstalment', lang), { amount: `₹${formatINR(monthlyEmi)}` })}
              </p>
              <p className="rounded-lg bg-brand-50 p-2 text-brand-800">
                {interpolate(tr('repayHealthLabel', lang), { health: repayHealth })}{' '}
                {repayment?.coverage_ratio != null ? `${(repayment.coverage_ratio * 100).toFixed(0)}%` : '—'}
              </p>
              <ul className="list-disc space-y-1 pl-5">
                {(fp.notes || []).map((n: any, i: number) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
              <Disclaimer>
                {tr('financeDisclaimer', lang)}
              </Disclaimer>
            </div>
          ) : tabs === 'schedule' ? (
            <ScheduleTable rows={rows} lang={lang} />
          ) : (
            <LoanComparison />
          )}
        </Card>
      </div>
    </div>
  )
}

function ScheduleTable({ rows, lang }: { rows: { month: number; payment: number; interest: number; principal: number; balance: number }[]; lang: Language }) {
  const preview = rows.slice(0, 12)
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-gray-500">
              <th className="py-2 pr-4">{tr('month', lang)}</th>
              <th className="py-2 pr-4">{tr('payment', lang)}</th>
              <th className="py-2 pr-4">{tr('interest', lang)}</th>
              <th className="py-2 pr-4">{tr('principal', lang)}</th>
              <th className="py-2">{tr('balance', lang)}</th>
            </tr>
          </thead>
          <tbody>
            {preview.map((r) => (
              <tr key={r.month} className="border-b border-gray-50">
                <td className="py-1.5 pr-4 text-gray-500">{r.month}</td>
                <td className="py-1.5 pr-4">{r.payment > 0 ? `₹${formatINR(r.payment)}` : '—'}</td>
                <td className="py-1.5 pr-4">₹{formatINR(r.interest)}</td>
                <td className="py-1.5 pr-4">₹{formatINR(r.principal)}</td>
                <td className="py-1.5">₹{formatINR(r.balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-gray-500">{interpolate(tr('showingFirst12', lang), { total: rows.length })}</p>
    </div>
  )
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1 text-sm font-medium ${
        active ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
    >
      {children}
    </button>
  )
}

function CostSection({ title, items }: { title: string; items: Record<string, number> }) {
  const entries = Object.entries(items)
  if (entries.length === 0) return null
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">{title}</h4>
      <dl className="divide-y divide-gray-100">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between gap-3 py-1.5 text-sm">
            <dt className="min-w-0 flex-1 break-words text-gray-500">{k}</dt>
            <dd className="shrink-0 font-medium text-gray-900">₹{formatINR(v)}</dd>
          </div>
        ))}
      </dl>
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

function Empty({ lang }: { lang: Language }) {
  return (
    <div className="py-20 text-center text-gray-500">
      <p>{tr('runAnalysisPlan', lang)}</p>
      <a href="/analyze" className="mt-2 inline-block text-brand-600">{tr('analyzeNow', lang)}</a>
    </div>
  )
}
