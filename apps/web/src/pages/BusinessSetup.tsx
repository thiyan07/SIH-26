import { useEffect, useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { api } from '../lib/api'
import { Card, CardHeader, Badge } from '../components/ui'

type Plan = any

function INR(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  return Math.round(n).toLocaleString('en-IN')
}

export function BusinessSetup() {
  const { result, setResult } = useAnalysis()
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState<string | undefined>(undefined)
  const [versions, setVersions] = useState<any[]>([])

  const analysisId = (result as any)?.analysis_id

  useEffect(() => {
    if (!result || !analysisId) {
      setPlan((result as any)?.business_setup_plan || null)
      return
    }
    setLoading(true)
    api.get(`/business-setup/plan?analysis_id=${analysisId}${model ? `&model=${model}` : ''}`)
      .then((r: any) => {
        setPlan(r.plan)
        // Keep Finance and Setup in sync: when model changes, update the canonical analysis result
        // so Finance's project_cost / financing gap / EMI match Setup's total_initial_requirement
        if (r.updated_financial_plan && r.updated_cost_breakdown && result) {
          const updated: any = {
            ...result,
            cost_breakdown: r.updated_cost_breakdown,
            financial_plan: { ...result.financial_plan, ...r.updated_financial_plan },
            business_setup_plan: r.plan,
          }
          // Also sync unified_financial if present
          if (result.unified_financial && r.updated_financial_plan) {
            updated.unified_financial = {
              ...result.unified_financial,
              project_cost: r.updated_financial_plan.project_cost,
              loan_amount: r.updated_financial_plan.loan_amount,
              financing_required: r.updated_financial_plan.required_financing,
              own_capital: r.updated_financial_plan.own_contribution,
              emi: r.updated_financial_plan.emi,
            }
          }
          if (r.updated_repayment) {
            updated.repayment = { ...result.repayment, ...r.updated_repayment }
          }
          setResult(updated)
        }
      })
      .catch(() => setPlan((result as any)?.business_setup_plan || null))
      .finally(() => setLoading(false))
    api.get(`/business-setup/plan/versions/${analysisId}`).then((r:any)=> setVersions(r.versions || [])).catch(()=>{})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysisId, model])

  if (!result) {
    return (
      <div className="py-20 text-center text-gray-500">
        <p>Run an analysis first to see your setup plan.</p>
        <a href="/analyze" className="mt-2 inline-block text-brand-600">Analyze now</a>
      </div>
    )
  }

  const p: Plan = plan || (result as any)?.business_setup_plan
  if (!p) return <div className="p-6 text-sm text-gray-500">No setup plan available.</div>

  const requiredItems = p.items?.filter((i:any)=> i.status==='REQUIRED') || []
  const recommendedItems = p.items?.filter((i:any)=> i.status==='RECOMMENDED') || []
  const optionalItems = p.items?.filter((i:any)=> i.status==='OPTIONAL') || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Business Setup & Operating Plan</h1>
        <p className="text-sm text-gray-500">What you need to start and operate — all numbers from deterministic engines, labelled ESTIMATED when not from real local evidence.</p>
      </div>

      {/* Your Business */}
      <Card>
        <CardHeader title="Your Business" subtitle={`${p.category_code} · ${p.model} · ${p.scale} · location factor ${p.location_factor}x`} />
        <div className="flex flex-wrap gap-2 text-xs">
          {p.available_models?.map((m:any)=> (
            <button key={m.code} onClick={()=> setModel(m.code)} className={`rounded-full px-3 py-1.5 font-semibold ${p.model===m.code ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-700'}`}>{m.label}</button>
          ))}
        </div>
        {versions.length > 1 && (
          <div className="mt-3 text-xs text-gray-500">Plan versions: {versions.map((v:any)=> `v${v.version} (${v.scale} · ${new Date(v.created_at).toLocaleDateString()})`).join(' • ')}</div>
        )}
        <div className="mt-3 text-xs text-gray-500">{p.location_note} <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">{p.data_status}</span></div>
      </Card>

      {/* What You Need */}
      <Card>
        <CardHeader title="What You Need to Start" subtitle="Required / Recommended / Optional — trim optional to lower cost" />
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-green-700">Required</div>
            <ul className="mt-2 space-y-1.5">
              {requiredItems.map((it:any,i:number)=> (
                <li key={i} className="flex justify-between rounded-lg bg-green-50 px-3 py-2 text-xs">
                  <span>{it.name} <span className="text-[10px] text-gray-500">({it.quantity_or_unit})</span></span>
                  <span className="font-semibold">₹{INR(it.estimated_cost)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-amber-700">Recommended</div>
            <ul className="mt-2 space-y-1.5">
              {recommendedItems.map((it:any,i:number)=> (
                <li key={i} className="flex justify-between rounded-lg bg-amber-50 px-3 py-2 text-xs">
                  <span>{it.name}</span><span className="font-semibold">₹{INR(it.estimated_cost)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-slate-500">Optional</div>
            <ul className="mt-2 space-y-1.5">
              {optionalItems.map((it:any,i:number)=> (
                <li key={i} className="flex justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs text-gray-600">
                  <span>{it.name}</span><span>₹{INR(it.estimated_cost)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="mt-3 text-[11px] italic text-gray-500">All setup items are ESTIMATED demo costs; verify with local quotes. Provenance: {p.provenance}</p>
      </Card>

      {/* Startup Requirement */}
      <Card>
        <CardHeader title="Startup Requirement" subtitle="Setup + inventory + working capital — same total as Finance" />
        <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <Stat label="Setup cost" value={`₹${INR(p.startup_cost)}`} />
          <Stat label="Initial inventory" value={`₹${INR(p.initial_inventory)}`} />
          <Stat label="Working capital" value={`₹${INR(p.working_capital)}`} />
          <Stat label="Contingency" value={`${p.contingency_pct}% · ₹${INR(p.contingency)}`} />
        </div>
        <div className="mt-3 rounded-xl bg-slate-900 px-4 py-3 text-white">
          <div className="text-xs uppercase tracking-widest text-white/60">Estimated initial requirement</div>
          <div className="text-2xl font-black">₹{INR(p.total_initial_requirement)} <span className="text-xs font-normal text-white/60">ESTIMATED</span></div>
        </div>
        {/* Lean option */}
        {p.lean_option && (
          <div className="mt-4 rounded-xl border border-teal-200 bg-teal-50 p-4">
            <div className="text-sm font-bold text-teal-800">Start-Lean Option</div>
            <div className="mt-1 text-xs text-gray-700">Lean total ₹{INR(p.lean_option.lean_total)} · financing ₹{INR(p.lean_option.financing_needed)} (you have ₹{INR((result as any)?.financial_plan?.capital_available)}). Removed: {p.lean_option.removed_or_reduced.join(', ') || '—'}</div>
            <div className="mt-1 text-[11px] text-gray-500">{p.lean_option.note}</div>
          </div>
        )}
        <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg bg-gray-50 p-3">Your capital <b>₹{INR((result as any)?.financial_plan?.capital_available)}</b></div>
          <div className="rounded-lg bg-gray-50 p-3">Financing gap <b>₹{INR((result as any)?.financial_plan?.required_financing)}</b> · scheme {(result as any)?.financial_plan?.scheme_name || '—'}</div>
        </div>
      </Card>

      {/* How to Operate */}
      <Card>
        <CardHeader title="How to Operate" subtitle="Monthly costs and targets — same as Finance & Profit" />
        <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          {p.monthly_operating_requirements?.slice(0,4).map((r:any,i:number)=> (
            <div key={i} className="rounded-lg bg-gray-50 p-3"><div className="text-[11px] text-gray-500">{r.name}</div><div className="font-bold">₹{INR(r.estimated_cost)}</div><div className="text-[10px] text-gray-500">{r.unit} · ESTIMATED</div></div>
          ))}
        </div>
        {p.operating_targets?.monthly_revenue != null && (
          <div className="mt-4 rounded-lg bg-white p-3 border">
            <div className="text-xs font-semibold">Operating targets</div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-3">
              <div>Monthly revenue <b>₹{INR(p.operating_targets.monthly_revenue)}</b></div>
              <div>Daily needed <b>₹{INR(p.operating_targets.daily_sales_needed)}</b>/day ({p.operating_targets.operating_days}d)</div>
              <div>Break-even <b>₹{INR(p.operating_targets.break_even_revenue)}</b> → <b>₹{INR(p.operating_targets.break_even_daily)}</b>/day</div>
              {p.operating_targets.daily_customers_needed != null && <div>Customers/day <b>{p.operating_targets.daily_customers_needed}</b></div>}
              {p.operating_targets.orders_per_week != null && <div>Orders/week <b>{p.operating_targets.orders_per_week}</b></div>}
              {p.operating_targets.litres_per_day_needed != null && <div>Litres/day <b>{p.operating_targets.litres_per_day_needed}</b></div>}
            </div>
            <p className="mt-2 text-[11px] italic text-gray-500">{p.operating_targets.note} If daily sales stay below break-even for a sustained period, costs and debt may not be covered.</p>
          </div>
        )}
        {/* Inventory plan */}
        <div className="mt-4">
          <div className="text-xs font-semibold">Initial inventory / raw materials</div>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {p.inventory_plan?.map((inv:any,i:number)=> (
              <div key={i} className={`rounded-lg p-3 text-xs ${inv.priority==='HIGH'?'bg-green-50 border border-green-200': inv.priority==='MEDIUM'?'bg-amber-50':'bg-slate-50'}`}>
                <div className="flex items-center gap-2"><Badge color={inv.priority==='HIGH'?'green':inv.priority==='MEDIUM'?'amber':'gray'}>{inv.priority}</Badge><span className="font-semibold">{inv.category}</span></div>
                <div className="mt-1 text-gray-600">{inv.items}</div><div className="text-[10px] text-gray-500">{inv.seasonality}</div>
              </div>
            ))}
          </div>
        </div>
        {/* Working capital buffer */}
        <div className="mt-4 rounded-lg bg-amber-50 p-3 text-xs">
          <div className="font-semibold">Recommended working-capital reserve: ₹{INR(p.planned_values?.planned_working_capital || p.working_capital)}</div>
          <div className="text-gray-600">Covers first months of operating costs + EMI and seasonal buffer. Modelled estimate, not government requirement.</div>
        </div>
      </Card>

      {/* What to Sell */}
      <Card>
        <CardHeader title="What to Sell / Offer" subtitle="Priorities from seasonal intelligence & market evidence" />
        <ul className="space-y-2">
          {p.product_mix?.map((pr:any,i:number)=> (
            <li key={i} className="flex items-start justify-between rounded-lg bg-gray-50 p-3">
              <div>
                <div className="text-sm font-semibold">{pr.product} <span className="ml-2 text-[10px]">{pr.season}</span></div>
                <div className="text-xs text-gray-600">{pr.reason}</div>
                <div className="text-[11px] italic text-gray-500">{pr.evidence} · {pr.provenance || 'ESTIMATED'}</div>
              </div>
              <Badge color={pr.relevance==='high'?'green':pr.relevance==='medium'?'amber':'gray'}>{pr.relevance}</Badge>
            </li>
          ))}
        </ul>
      </Card>

      {/* Risks */}
      <Card>
        <CardHeader title="Operating Risks & Actions" subtitle="Tied to detected risks only" />
        {p.risks?.length ? (
          <ul className="space-y-2">
            {p.risks.map((r:any,i:number)=> (
              <li key={i} className="rounded-lg bg-red-50 p-3 text-xs"><span className="font-bold">{r.risk} ({r.level})</span> → {r.action}<div className="text-[10px] text-gray-500">{r.provenance}</div></li>
            ))}
          </ul>
        ) : <div className="text-xs text-gray-500">No elevated risks detected from current evidence. Stay alert to competition and seasonal dips.</div>}
        <div className="mt-3 rounded-lg bg-gray-50 p-3 text-xs">
          <div className="font-semibold">Sourcing needs</div>
          {p.sourcing_needs?.map((s:any,i:number)=> (
            <div key={i} className="flex justify-between py-1 border-b border-gray-100 last:border-0"><span>{s.need} · {s.type}</span><Badge color="gray">{s.status}</Badge></div>
          ))}
          <div className="mt-1 text-[11px] italic text-gray-500">Supplier discovery can be connected when verified supplier data is available.</div>
        </div>
      </Card>

      {/* KPIs */}
      <Card>
        <CardHeader title="Track After Launch — KPIs" subtitle="Compare plan vs actual; future ExpenseTracker will populate actuals" />
        <div className="grid gap-2 md:grid-cols-2">
          {p.kpis?.map((k:any,i:number)=> (
            <div key={i} className="rounded-lg bg-white border p-3 text-xs"><div className="font-semibold">{k.kpi} <span className="text-gray-500">({k.unit})</span></div><div className="text-gray-600">{k.why}</div></div>
          ))}
        </div>
        <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs">
          <div className="font-semibold">Planned values (for plan vs actual)</div>
          <div className="mt-1 grid grid-cols-2 gap-2">
            <div>Revenue ₹{INR(p.planned_values?.planned_revenue)}</div>
            <div>COGS ₹{INR(p.planned_values?.planned_cogs)}</div>
            <div>Opex ₹{INR(p.planned_values?.planned_opex)}</div>
            <div>Gross margin {p.planned_values?.planned_gross_margin ?? '—'}%</div>
            <div>Operating profit ₹{INR(p.planned_values?.planned_operating_profit)}</div>
            <div>Cash surplus ₹{INR(p.planned_values?.planned_cash_surplus)}</div>
          </div>
          <div className="mt-2 text-[11px] text-gray-500">Variance = (Actual − Planned)/Planned. ExpenseTracker will later supply actuals.</div>
        </div>
      </Card>

      <div className="text-[11px] italic text-gray-500">Data status: {p.data_status} · {p.assumptions.join(' ')} Confidence: {p.confidence}</div>
      {loading && <div className="text-xs text-gray-400">Updating…</div>}
    </div>
  )
}

function Stat({ label, value }: { label:string; value:string }) {
  return <div><div className="text-[11px] text-gray-500">{label}</div><div className="font-bold text-gray-900">{value}</div></div>
}
