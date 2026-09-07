import { useEffect, useMemo, useState } from 'react'
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend, BarChart, Bar } from 'recharts'
import { useAnalysis } from '../lib/analysisStore'
import { Card, CardHeader, Disclaimer, StatCard } from '../components/ui'
import { emi, schedule } from '../lib/finance'
import { tr, interpolate } from '../lib/i18n'
import { formatINR } from './Dashboard'
import { downloadCSV } from '../lib/export'

export function Simulator() {
  const { result, lang } = useAnalysis()
  const fp = result?.financial_plan
  const [loan, setLoan] = useState(fp?.loan_amount ?? 250000)
  const [rate, setRate] = useState(fp?.interest_rate ?? 8)
  const [years, setYears] = useState(fp?.tenure_years ?? 5)
  const [moratorium, setMoratorium] = useState(fp?.moratorium_months ?? 0)
  const [chartMode, setChartMode] = useState<'line'|'bar'>('line')
  const [scenarioB, setScenarioB] = useState<{loan:number;rate:number;years:number}|null>(null)

  // persist scenario
  useEffect(()=>{
    const raw = localStorage.getItem('grambiz.simulator')
    if (raw) try { const p = JSON.parse(raw); setLoan(p.loan ?? loan); setRate(p.rate ?? rate); setYears(p.years ?? years) } catch {}
  },[])
  useEffect(()=>{ localStorage.setItem('grambiz.simulator', JSON.stringify({ loan, rate, years, moratorium })) }, [loan, rate, years, moratorium])

  const months = years * 12
  const monthlyEmi = useMemo(() => emi(loan, rate, months), [loan, rate, months])
  const totalInterest = monthlyEmi * months - loan
  const rows = useMemo(() => schedule(loan, rate, months, moratorium), [loan, rate, months, moratorium])
  const chart = rows.map((r) => ({ month: r.month, balance: r.balance, principal: Math.round(r.principal) }))
  const surplus = (result as any)?.monthly_economics?.cash_surplus ?? null
  const affordable = surplus != null ? monthlyEmi <= surplus : null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{tr('loanSimulator', lang)}</h1>
        <p className="text-sm text-gray-500">{tr('loanSimulatorSub', lang)}</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title={tr('parameters', lang)} subtitle={tr('slideToExplore', lang)} />
          <Slider label={tr('loanAmount', lang)} value={loan} display={`₹${formatINR(loan)}`} min={10000} max={2000000} step={5000} onChange={setLoan} />
          <Slider label={tr('interestRate', lang)} value={rate} display={`${rate}% ${tr('perAnnum', lang)}`} min={4} max={15} step={0.1} onChange={setRate} />
          <Slider label={tr('tenure', lang)} value={years} display={`${years} ${tr('years', lang)}`} min={1} max={15} step={1} onChange={setYears} />
          <Slider label={tr('moratoriumGrace', lang)} value={moratorium} display={`${moratorium} ${tr('months', lang)}`} min={0} max={12} step={1} onChange={setMoratorium} />
          <Disclaimer>{tr('simulatorDisclaimer', lang)}</Disclaimer>
        </Card>

        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between">
            <CardHeader title={tr('outcome', lang)} />
            <div className="flex gap-1">
              <button data-testid="chart-line" onClick={()=>setChartMode('line')} className={`rounded-lg px-2 py-1 text-xs ${chartMode==='line'?'bg-brand-600 text-white':'bg-slate-100 text-slate-600'}`}>Line</button>
              <button data-testid="chart-bar" onClick={()=>setChartMode('bar')} className={`rounded-lg px-2 py-1 text-xs ${chartMode==='bar'?'bg-brand-600 text-white':'bg-slate-100 text-slate-600'}`}>Bar</button>
              <button data-testid="save-scenario" onClick={()=>setScenarioB({ loan, rate, years })} className="rounded-lg bg-amber-500 px-2 py-1 text-xs font-semibold text-white">Save Scenario</button>
              <button data-testid="export-sim" onClick={()=>downloadCSV(`simulator-${Date.now()}.csv`, [['Month','Payment','Interest','Principal','Balance'], ...rows.slice(0,12).map(r=>[r.month,r.payment,r.interest,r.principal,r.balance])])} className="rounded-lg border border-slate-200 px-2 py-1 text-xs">CSV</button>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <StatCard label={tr('monthlyEMI', lang)} value={`₹${formatINR(monthlyEmi)}`} />
            <StatCard label={tr('totalInterest', lang)} value={`₹${formatINR(totalInterest)}`} />
            <StatCard label={tr('totalPayable', lang)} value={`₹${formatINR(loan + totalInterest)}`} />
          </div>
          {affordable !== null && (
            <div data-testid="affordability" className={`mt-3 rounded-xl px-3 py-2 text-xs font-semibold ${affordable ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' : 'bg-red-50 text-red-700 ring-1 ring-red-200'}`}>
              {affordable ? `✅ Affordable — EMI fits within surplus ₹${formatINR(surplus)}` : `⚠️ EMI exceeds surplus ₹${formatINR(surplus)} — consider lower loan or longer tenure`}
            </div>
          )}
          {scenarioB && (
            <div data-testid="scenario-compare" className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-2 text-xs">
              <div className="font-semibold text-amber-800">Scenario B: loan ₹{formatINR(scenarioB.loan)} @ {scenarioB.rate}% for {scenarioB.years}y</div>
              <div className="text-amber-700">Diff EMI: ₹{formatINR(Math.abs(emi(scenarioB.loan, scenarioB.rate, scenarioB.years*12) - monthlyEmi))} {emi(scenarioB.loan, scenarioB.rate, scenarioB.years*12) > monthlyEmi ? 'higher' : 'lower'}</div>
              <button onClick={()=>setScenarioB(null)} className="mt-1 text-[11px] text-amber-700 underline">Clear</button>
            </div>
          )}
          <div className="mt-5" data-testid="sim-chart">
            {chartMode==='line' ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={rows} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} label={{ value: tr('month', lang), fontSize: 11, position: 'insideBottom', offset: -2 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="balance" name={tr('outstandingBalance', lang)} stroke="#0d9488" strokeWidth={2} />
                <Line type="monotone" dataKey="payment" name={tr('paymentInclInterest', lang)} stroke="#f59e0b" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={rows.slice(0,12)} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="payment" fill="#0d9488" radius={[4,4,0,0]} />
                <Bar dataKey="interest" fill="#f59e0b" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
            )}
          </div>
          {chart.length > 0 && (
            <p className="mt-2 text-xs text-gray-500">
              {interpolate(tr('graceNote', lang), { moratorium })}
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
