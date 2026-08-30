import { useMemo, useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader, Disclaimer, StatCard, Badge } from '../components/ui'
import { schedule, emi } from '../lib/finance'
import { formatINR } from './Dashboard'

export function Finance() {
  const { result } = useAnalysis()
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

  if (!result || !fp) return <Empty />

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-gray-900">Financial Plan & Loan Structure</h1>
        <Badge color={fp.scheme_decision === 'Go' || fp.scheme_decision === 'GO' ? 'green' : fp.scheme_decision === 'NO' ? 'red' : 'amber'}>
          {fp.scheme_decision}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Project cost" value={`₹${formatINR(fp.project_cost)}`} sub="Total financed + own margin" />
        <StatCard label="Loan amount" value={`₹${formatINR(fp.loan_amount)}`} sub={`${fp.margin_pct}% own margin`} />
        <StatCard label="Monthly EMI (est.)" value={`₹${formatINR(monthlyEmi)}`} />
        <StatCard label="Repayment health" value={repayHealth === 'High' || repayHealth === 'High-Risk' || repayHealth === 'High risk' ? 'High risk' : repayHealth} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Scheme Derivation" subtitle="Why this loan is (or isn’t) available" />
          <Rows rows={[
            ['Capital available', `₹${formatINR(fp.capital_available)}`],
            ['Scheme', fp.scheme_name || '—'],
            ['Scheme code', fp.scheme_code || '—'],
            ['Interest rate', fp.interest_rate != null ? `${fp.interest_rate}% p.a.` : '—'],
            ['Tenure', fp.tenure_years != null ? `${fp.tenure_years} years` : '—'],
            ['Moratorium', fp.moratorium_months != null ? `${fp.moratorium_months} months (${fp.moratorium_mode})` : '—'],
            ['Max loanable', fp.max_loan != null ? `₹${formatINR(fp.max_loan)}` : '—'],
            ['Reference', fp.source_document || '—'],
          ]} />
          {fp.scheme_reason && (
            <p className="mt-3 rounded-lg bg-gray-50 p-2 text-xs text-gray-600">{fp.scheme_reason}</p>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <div className="mb-3 flex gap-2">
            <Tab active={tabs === 'plan'} onClick={() => setTabs('plan')}>Plan note</Tab>
            <Tab active={tabs === 'schedule'} onClick={() => setTabs('schedule')}>Full schedule</Tab>
          </div>
          {tabs === 'plan' ? (
            <div className="space-y-3 text-sm text-gray-600">
              <p>
                With <strong>₹{formatINR(fp.capital_available)}</strong> available and a project cost of{' '}
                <strong>₹{formatINR(fp.project_cost)}</strong>, the bank would fund{' '}
                <strong>₹{formatINR(fp.loan_amount)}</strong> at <strong>{rate}%</strong> over{' '}
                <strong>{fp.tenure_years} years</strong>
                {moratorium > 0 ? ` with a ${moratorium}-month ${fp.moratorium_mode || 'grace'} period` : ''}.
              </p>
              <p>
                Estimated monthly instalment ≈ <strong>₹{formatINR(monthlyEmi)}</strong>. The profit model projects a monthly
                operating cash surplus; whether it can safely cover this instalment is summarised by the repayment health label.
              </p>
              <p className="rounded-lg bg-brand-50 p-2 text-brand-800">
                Repayment health: <strong>{repayHealth}</strong>. Coverage ratio:{' '}
                {repayment?.coverage_ratio != null ? `${(repayment.coverage_ratio * 100).toFixed(0)}%` : '—'}
              </p>
              <ul className="list-disc space-y-1 pl-5">
                {(fp.notes || []).map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
              <Disclaimer>
                This is a self-financed estimate calculated from the plan and profit model. Actual loan approval, rate and
                tenure depend on the lending institution and current scheme terms.
              </Disclaimer>
            </div>
          ) : (
            <ScheduleTable rows={rows} />
          )}
        </Card>
      </div>
    </div>
  )
}

function ScheduleTable({ rows }: { rows: { month: number; payment: number; interest: number; principal: number; balance: number }[] }) {
  const preview = rows.slice(0, 12)
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-gray-500">
              <th className="py-2 pr-4">Month</th>
              <th className="py-2 pr-4">Payment</th>
              <th className="py-2 pr-4">Interest</th>
              <th className="py-2 pr-4">Principal</th>
              <th className="py-2">Balance</th>
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
      <p className="mt-2 text-xs text-gray-400">Showing first 12 months of {rows.length}. Scroll financial tab to see full-year view.</p>
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

function Empty() {
  return (
    <div className="py-20 text-center text-gray-500">
      <p>Run an analysis to see the financial plan.</p>
      <a href="/analyze" className="mt-2 inline-block text-brand-600">Analyze now →</a>
    </div>
  )
}
