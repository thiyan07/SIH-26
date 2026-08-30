import { useMemo, useState } from 'react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts'
import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader, Disclaimer, StatCard } from '../components/ui'
import { emi, schedule } from '../lib/finance'
import { formatINR } from './Dashboard'

export function Simulator() {
  const { result } = useAnalysis()
  const fp = result?.financial_plan
  const [loan, setLoan] = useState(fp?.loan_amount ?? 250000)
  const [rate, setRate] = useState(fp?.interest_rate ?? 8)
  const [years, setYears] = useState(fp?.tenure_years ?? 5)
  const [moratorium, setMoratorium] = useState(fp?.moratorium_months ?? 0)

  const months = years * 12
  const monthlyEmi = useMemo(() => emi(loan, rate, months), [loan, rate, months])
  const totalInterest = monthlyEmi * months - loan
  const rows = useMemo(() => schedule(loan, rate, months, moratorium), [loan, rate, months, moratorium])
  const chart = rows.map((r) => ({ month: r.month, balance: r.balance, principal: Math.round(r.principal) }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Loan What-if Simulator</h1>
        <p className="text-sm text-gray-500">Adjust loan size, interest and tenure to see EMI and repayment balance.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title="Parameters" subtitle="Slide to explore" />
          <Slider label="Loan amount" value={loan} display={`₹${formatINR(loan)}`} min={10000} max={2000000} step={5000} onChange={setLoan} />
          <Slider label="Interest rate" value={rate} display={`${rate}% p.a.`} min={4} max={15} step={0.1} onChange={setRate} />
          <Slider label="Tenure" value={years} display={`${years} years`} min={1} max={15} step={1} onChange={setYears} />
          <Slider label="Moratorium (grace)" value={moratorium} display={`${moratorium} months`} min={0} max={12} step={1} onChange={setMoratorium} />
          <Disclaimer>Illustrative only — actual loan parameters are set by the lending institution.</Disclaimer>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Outcome" />
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="Monthly EMI" value={`₹${formatINR(monthlyEmi)}`} />
            <StatCard label="Total interest" value={`₹${formatINR(totalInterest)}`} />
            <StatCard label="Total payable" value={`₹${formatINR(loan + totalInterest)}`} />
          </div>
          <div className="mt-5">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={rows} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} label={{ value: 'Month', fontSize: 11, position: 'insideBottom', offset: -2 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="balance" name="Outstanding balance" stroke="#0d9488" strokeWidth={2} />
                <Line type="monotone" dataKey="payment" name="Payment (incl. interest)" stroke="#f59e0b" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {chart.length > 0 && (
            <p className="mt-2 text-xs text-gray-400">
              Principal repayment begins after the {moratorium}-month grace period; during grace, accrued interest is added to balance.
            </p>
          )}
        </Card>
      </div>
    </div>
  )
}

function Slider({ label, value, display, min, max, step, onChange }: {
  label: string
  value: number
  display: string
  min: number
  max: number
  step: number
  onChange: (v: number) => void
}) {
  return (
    <div className="mb-5">
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-gray-600">{label}</span>
        <span className="font-semibold text-gray-900">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
      />
    </div>
  )
}
