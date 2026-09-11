import { useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { api } from '../lib/api'
import { Card, CardHeader } from './ui'

export function AssumptionEditor() {
  const { result, setResult } = useAnalysis()
  const me = (result as any)?.monthly_economics
  const assumptions = me?.assumptions

  const [customers, setCustomers] = useState<string>('')
  const [ticket, setTicket] = useState<string>('')
  const [days, setDays] = useState<string>('')
  const [cogs, setCogs] = useState<string>('')
  const [opex, setOpex] = useState<string>('')
  const [loading, setLoading] = useState(false)

  if (!result || !me) return null

  const defaults = assumptions?.defaults || {}
  const overrides = assumptions?.overrides || {}

  const handleApply = async () => {
    const overrides: Record<string, any> = {}
    if (customers) overrides.customers_per_day = parseFloat(customers)
    if (ticket) overrides.avg_transaction_value = parseFloat(ticket)
    if (days) overrides.operating_days = parseInt(days, 10)
    if (cogs) overrides.cogs_pct = parseFloat(cogs)
    if (opex) overrides.monthly_fixed_expenses = parseFloat(opex)

    // Also handle revenue override if customers and ticket and days are all provided
    if (customers && ticket && days) {
      overrides.monthly_revenue = parseFloat(customers) * parseFloat(ticket) * parseInt(days, 10)
    }

    setLoading(true)
    try {
      // Re-run analysis with overrides
      const req = {
        state: result.location.state,
        district: result.location.district,
        block: result.location.block,
        village: result.location.village,
        proposed_latitude: result.location.proposed_latitude,
        proposed_longitude: result.location.proposed_longitude,
        capital_available: (result as any).financial_plan?.capital_available || 30000,
        category_code: (result as any).cost_breakdown?.category_code || 'grocery',
        preferred_scale: (result as any).cost_breakdown?.scale || 'micro',
        business_model: (result as any).business_setup_plan?.model || undefined,
        language: 'en',
        assumption_overrides: overrides,
      }
      const newResult = await api.post('/analysis', req)
      setResult(newResult as any)
    } catch (e) {
      console.error('Failed to apply assumptions', e)
      alert('Failed to apply assumptions: ' + (e as any).message)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setCustomers('')
    setTicket('')
    setDays('')
    setCogs('')
    setOpex('')
  }

  return (
    <Card>
      <CardHeader title="Edit Assumptions" subtitle="Override default estimates with your local knowledge — all dependent calculations will update" />
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <label className="text-xs text-gray-500">Customers / day (default {defaults.customers_per_day ?? '—'} ESTIMATED)</label>
          <input
            type="number"
            value={customers}
            onChange={e => setCustomers(e.target.value)}
            placeholder={String(defaults.customers_per_day ?? '')}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          {overrides.customers_per_day != null && <div className="text-[11px] text-amber-600">Override: {overrides.customers_per_day} (was {defaults.customers_per_day})</div>}
        </div>
        <div>
          <label className="text-xs text-gray-500">Avg. transaction ₹ (default {defaults.avg_transaction_value ?? '—'})</label>
          <input
            type="number"
            value={ticket}
            onChange={e => setTicket(e.target.value)}
            placeholder={String(defaults.avg_transaction_value ?? '')}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500">Operating days / month (default {defaults.operating_days ?? '—'})</label>
          <input
            type="number"
            value={days}
            onChange={e => setDays(e.target.value)}
            placeholder={String(defaults.operating_days ?? '')}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500">COGS % (default {defaults.cogs_pct ?? '—'}%)</label>
          <input
            type="number"
            value={cogs}
            onChange={e => setCogs(e.target.value)}
            placeholder={String(defaults.cogs_pct ?? '')}
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500">Monthly fixed expenses ₹ (default from template)</label>
          <input
            type="number"
            value={opex}
            onChange={e => setOpex(e.target.value)}
            placeholder="e.g. 12000"
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        <button
          onClick={handleApply}
          disabled={loading}
          className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-bold text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {loading ? 'Applying…' : 'Apply & Recalculate'}
        </button>
        <button onClick={handleReset} className="rounded-lg border border-slate-200 px-4 py-2 text-sm">Reset</button>
      </div>
      <p className="mt-2 text-[11px] italic text-gray-500">
        Defaults are ESTIMATED demo assumptions per category. Your overrides are preserved as OVERRIDE and will be shown as such. All dependent values (Revenue → Cash Surplus → Break-even → Viability) update consistently.
      </p>
    </Card>
  )
}
