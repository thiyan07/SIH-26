import { useState, useMemo } from 'react'
import { emi } from '../lib/finance'
import { formatINR } from '../pages/Dashboard'
import { Card, CardHeader } from './ui'

type Loan = { loan: number; rate: number; years: number; name: string }

export function LoanComparison() {
  const [loans, setLoans] = useState<Loan[]>([
    { name: 'Bank A', loan: 200000, rate: 8.0, years: 5 },
    { name: 'Bank B', loan: 200000, rate: 9.5, years: 5 },
    { name: 'MFI', loan: 150000, rate: 11, years: 3 },
  ])
  const update = (idx: number, patch: Partial<Loan>) => setLoans(prev=> prev.map((l,i)=> i===idx ? { ...l, ...patch } : l))
  const rows = useMemo(()=> loans.map(l=>{
    const months = l.years*12
    const monthly = emi(l.loan, l.rate, months)
    const total = monthly*months
    return { ...l, monthly, total, interest: total - l.loan }
  }), [loans])
  const cheapest = [...rows].sort((a,b)=>a.total-b.total)[0]
  return (
    <Card data-testid="loan-comparison">
      <CardHeader title="Loan Comparison (3-way)" subtitle="Compare banks side-by-side" />
      <div className="grid gap-3 md:grid-cols-3">
        {rows.map((r,i)=>(
          <div key={i} data-testid={`loan-card-${i}`} className={`rounded-xl border p-3 ${r.name===cheapest?.name ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-950/30' : 'border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800'}`}>
            <input value={r.name} onChange={e=>update(i,{name:e.target.value})} className="w-full rounded-lg border border-slate-200 px-2 py-1 text-sm font-semibold dark:border-slate-600 dark:bg-slate-900 dark:text-white" />
            <div className="mt-2 space-y-2">
              <label className="block text-xs text-slate-600 dark:text-slate-300">Loan ₹<input type="range" min={50000} max={500000} step={10000} value={r.loan} onChange={e=>update(i,{loan:Number(e.target.value)})} className="w-full accent-brand-600" /><span className="font-semibold">₹{formatINR(r.loan)}</span></label>
              <label className="block text-xs text-slate-600 dark:text-slate-300">Rate {r.rate}%<input type="range" min={5} max={15} step={0.1} value={r.rate} onChange={e=>update(i,{rate:Number(e.target.value)})} className="w-full accent-brand-600" /></label>
              <label className="block text-xs text-slate-600 dark:text-slate-300">Years {r.years}<input type="range" min={1} max={10} value={r.years} onChange={e=>update(i,{years:Number(e.target.value)})} className="w-full accent-brand-600" /></label>
            </div>
            <div className="mt-3 space-y-1 text-xs">
              <div className="flex justify-between"><span>EMI</span><b>₹{formatINR(Math.round(r.monthly))}</b></div>
              <div className="flex justify-between"><span>Interest</span><span>₹{formatINR(Math.round(r.interest))}</span></div>
              <div className="flex justify-between"><span>Total</span><b>₹{formatINR(Math.round(r.total))}</b></div>
              {r.name===cheapest?.name && <div className="mt-1 rounded-full bg-emerald-600 px-2 py-1 text-center text-xs font-bold text-white">Cheapest</div>}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
