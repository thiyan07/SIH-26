import { useAnalysis } from '../lib/analysisStore'
import { formatINR } from '../pages/Dashboard'

export function CalendarReminders() {
  const { result } = useAnalysis()
  const fp = result?.financial_plan
  if (!fp || !fp.loan_amount) return null
  const emi = (result as any)?.repayment?.monthly_emi ?? fp.emi ?? 0
  const nextDue = new Date()
  nextDue.setMonth(nextDue.getMonth()+1)
  nextDue.setDate(5)
  const gcalDate = nextDue.toISOString().replace(/[-:]/g,'').split('.')[0] + 'Z'
  const endDate = new Date(nextDue.getTime() + 60*60*1000).toISOString().replace(/[-:]/g,'').split('.')[0] + 'Z'
  const gcalUrl = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(`GramBiz EMI ₹${formatINR(emi)} due`)}&dates=${gcalDate}/${endDate}&details=${encodeURIComponent(`Loan ₹${formatINR(fp.loan_amount)} @ ${fp.interest_rate}% for ${fp.tenure_years}y. Pay before 5th to avoid penalty.`)}`
  const dates = Array.from({length:3}, (_,i)=>{
    const d = new Date()
    d.setMonth(d.getMonth()+1+i)
    d.setDate(5)
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  })
  return (
    <div data-testid="calendar-reminders" className="rounded-2xl border border-indigo-200 bg-indigo-50 p-4 dark:border-indigo-800 dark:bg-indigo-950/30">
      <div className="text-xs font-bold uppercase tracking-widest text-indigo-700 dark:text-indigo-300">📅 EMI Reminders</div>
      <div className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">Next EMI: 5th of each month • ₹{formatINR(emi)}</div>
      <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-slate-600 dark:text-slate-300">
        {dates.map(d=> <li key={d}>{d} — ₹{formatINR(emi)}</li>)}
      </ul>
      <a data-testid="gcal-link" href={gcalUrl} target="_blank" rel="noreferrer" className="mt-3 inline-flex rounded-xl bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-indigo-700">Add to Google Calendar →</a>
      <p className="mt-1 text-[11px] text-indigo-700/70 dark:text-indigo-300/70">Local reminder only — no data leaves your device</p>
    </div>
  )
}
