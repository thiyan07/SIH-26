import { useMemo, useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader, Disclaimer, StatCard, Badge } from '../components/ui'
import { schedule, emi } from '../lib/finance'
import { tr, interpolate, schemeDecisionLabel, type Language } from '../lib/i18n'
import { formatINR } from './Dashboard'

export function Finance() {
  const { result, lang } = useAnalysis()
  const fp = result?.financial_plan
  const repayment = result?.repayment
  const [tabs, setTabs] = useState<'plan' | 'schedule'>('plan')

  const months = fp?.tenure_years != null ? fp.tenure_years * 12 : 0
  const moratorium = fp?.moratorium_months ?? 0
  const loan = fp?.loan_amount ?? 0
  const rate = fp?.interest_rate ?? 0

  const monthlyEmi = useMemo(
    () => (result?.repayment?.monthly_emi ?? fp?.emi ?? emi(loan, rate, months)) || 0,
    [result, fp, loan, rate, months],
  )
  const rows = useMemo(() => schedule(loan, rate, months, moratorium), [loan, rate, months, moratorium])
  const repayHealth = repayment?.health_label || '—'
  const me = result?.monthly_economics as any

  if (!result || !fp) return <Empty lang={lang} />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-gray-900">{tr('financeTitle', lang)}</h1>
          <Badge color={fp.scheme_decision === 'Go' || fp.scheme_decision === 'GO' ? 'green' : fp.scheme_decision === 'NO' ? 'red' : 'amber'}>
          {schemeDecisionLabel(fp.scheme_decision, lang)}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label={tr('projectCost', lang)} value={`₹${formatINR(fp.project_cost)}`} sub={tr('projectCostSub', lang)} />
        <StatCard label={tr('loanAmount', lang)} value={`₹${formatINR(fp.loan_amount)}`} sub={`${tr('ownContribution', lang)} ₹${formatINR(fp.own_contribution ?? 0)}`} />
        <StatCard label={tr('monthlyEMI', lang)} value={`₹${formatINR(monthlyEmi)}`} />
        <StatCard label={tr('repayHealth', lang)} value={repayHealth === 'High' || repayHealth === 'High-Risk' || repayHealth === 'High risk' ? tr('highRisk', lang) : repayHealth} />
      </div>

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
              <div className="text-base font-bold text-gray-900">₹{formatINR(me.gross_profit)}{me.gross_margin_pct != null ? <span className="text-[10px] font-normal text-gray-400"> ({me.gross_margin_pct}%)</span> : null}</div>
            </div>
            <div className="rounded-lg bg-gray-50 p-3">
              <div className="text-[11px] text-gray-500">{tr('operatingProfit', lang)}</div>
              <div className="text-base font-bold text-gray-900">₹{formatINR(me.operating_profit)}</div>
            </div>
            <div className="rounded-lg bg-brand-50 p-3">
              <div className="text-[11px] text-gray-500">{tr('cashSurplus', lang)}</div>
              <div className="text-base font-bold text-gray-900">₹{formatINR(me.cash_surplus)}{me.cash_surplus_pct != null ? <span className="text-[10px] font-normal text-gray-400"> ({me.cash_surplus_pct}%)</span> : null}</div>
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
                {(fp.notes || []).map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
              <Disclaimer>
                {tr('financeDisclaimer', lang)}
              </Disclaimer>
            </div>
          ) : (
            <ScheduleTable rows={rows} lang={lang} />
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
      <p className="mt-2 text-xs text-gray-400">{interpolate(tr('showingFirst12', lang), { total: rows.length })}</p>
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
