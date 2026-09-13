import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAnalysis } from '../lib/analysisStore'
import { api } from '../lib/api'
import { Card, CardHeader, Badge } from '../components/ui'
import { tr } from '../lib/i18n'

type Plan = any

function INR(n: number | undefined | null): string {
  if (n == null || Number.isNaN(n)) return '—'
  return Math.round(n).toLocaleString('en-IN')
}

export function BusinessSetup() {
  const { result, setResult, lang, setBusinessSetupConfirmed, setBudgetAllocation } = useAnalysis()
  const navigate = useNavigate()
  const [plan, setPlan] = useState<Plan | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const analysisId = (result as any)?.analysis_id

  useEffect(() => {
    if (!result || !analysisId) {
      setPlan((result as any)?.business_setup_plan || null)
      return
    }
    setLoading(true)
    api.get(`/business-setup/plan?analysis_id=${analysisId}`)
      .then((r: any) => {
        setPlan(r.plan)
        if (r.updated_financial_plan && r.updated_cost_breakdown && result) {
          const updated: any = {
            ...result,
            cost_breakdown: r.updated_cost_breakdown,
            financial_plan: { ...result.financial_plan, ...r.updated_financial_plan },
            business_setup_plan: r.plan,
          }
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
  }, [analysisId])

  if (!result) {
    return (
      <div className="py-20 text-center text-gray-500">
        <p>{tr("runAnalysisFirstSetup", lang)}</p>
        <a href="/analyze" className="mt-2 inline-block text-brand-600">Analyze now</a>
      </div>
    )
  }

  const p: Plan = plan || (result as any)?.business_setup_plan
  if (!p) return <div className="p-6 text-sm text-gray-500">{tr("runAnalysisFirstSetup", lang)}</div>

  const requiredItems = p.items?.filter((i:any)=> i.status==='REQUIRED') || []
  const recommendedItems = p.items?.filter((i:any)=> i.status==='RECOMMENDED') || []
  const optionalItems = p.items?.filter((i:any)=> i.status==='OPTIONAL') || []

  // Suggested amount split
  const totalReq = p.total_initial_requirement || 0
  const startupReq = p.startup_cost || 0
  const inventoryReq = p.initial_inventory || 0
  const otherReq = (p.working_capital || 0) + (p.contingency || 0)

  const handleConfirm = (ok: boolean) => {
    setConfirming(true)
    // Persist budget allocation and confirmation through analysisStore (and backend where needed)
    const allocation = {
      startup: startupReq,
      inventory: inventoryReq,
      other: otherReq,
      total: totalReq,
    }
    setBudgetAllocation(allocation as any)
    setBusinessSetupConfirmed(ok)
    if (ok) {
      navigate('/market')
    } else {
      navigate('/analyze')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{tr("businessFeasibilityTitle", lang)}</h1>
        <p className="text-sm text-gray-500">{tr("businessFeasibilitySub", lang)}</p>
      </div>

      {/* What You Need */}
      <Card>
        <CardHeader title={tr("whatYouNeedToStart", lang)} subtitle={tr("requiredRecommendedOptional", lang)} />
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-green-700">{tr("required", lang)}</div>
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
            <div className="text-xs font-bold uppercase tracking-widest text-amber-700">{tr("recommended", lang)}</div>
            <ul className="mt-2 space-y-1.5">
              {recommendedItems.map((it:any,i:number)=> (
                <li key={i} className="flex justify-between rounded-lg bg-amber-50 px-3 py-2 text-xs">
                  <span>{it.name}</span><span className="font-semibold">₹{INR(it.estimated_cost)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-widest text-slate-500">{tr("optional", lang)}</div>
            <ul className="mt-2 space-y-1.5">
              {optionalItems.map((it:any,i:number)=> (
                <li key={i} className="flex justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs text-gray-600">
                  <span>{it.name}</span><span>₹{INR(it.estimated_cost)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="mt-3 text-[11px] italic text-gray-500">All setup items are modelled estimates; verify with local quotes. Provenance: {p.provenance}</p>
      </Card>

      {/* Startup Requirement */}
      <Card>
        <CardHeader title={tr("startupRequirement", lang)} subtitle={tr("setupInventoryWorkingSubtitle", lang)} />
        <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <Stat label={tr("setupCost", lang)} value={`₹${INR(p.startup_cost)}`} />
          <Stat label={tr("initialInventory", lang)} value={`₹${INR(p.initial_inventory)}`} />
          <Stat label={tr("workingCapital", lang)} value={`₹${INR(p.working_capital)}`} />
          <Stat label={tr("contingency", lang)} value={`${p.contingency_pct}% · ₹${INR(p.contingency)}`} />
        </div>
        <div className="mt-3 rounded-xl bg-slate-900 px-4 py-3 text-white">
          <div className="text-xs uppercase tracking-widest text-white/60">Estimated initial requirement</div>
          <div className="text-2xl font-black">₹{INR(p.total_initial_requirement)} <span className="text-xs font-normal text-white/60">ESTIMATED</span></div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg bg-gray-50 p-3">{tr("yourCapital", lang)} <b>₹{INR((result as any)?.financial_plan?.capital_available)}</b></div>
          <div className="rounded-lg bg-gray-50 p-3">{tr("financingGap", lang)} <b>₹{INR((result as any)?.financial_plan?.required_financing)}</b> · scheme {(result as any)?.financial_plan?.scheme_name || '—'}</div>
        </div>
      </Card>

      {/* Initial Inventory / Raw Materials - kept as required */}
      <Card>
        <CardHeader title="Initial Inventory / Raw Materials" subtitle="Stock needed to start sales" />
        <div className="grid gap-2 md:grid-cols-2">
          {p.inventory_plan?.slice(0,4).map((inv:any,i:number)=> (
            <div key={i} className={`rounded-lg p-3 text-xs ${inv.priority==='HIGH'?'bg-green-50 border border-green-200': inv.priority==='MEDIUM'?'bg-amber-50':'bg-slate-50'}`}>
              <div className="flex items-center gap-2"><Badge color={inv.priority==='HIGH'?'green':inv.priority==='MEDIUM'?'amber':'gray'}>{inv.priority}</Badge><span className="font-semibold">{inv.category}</span></div>
              <div className="mt-1 text-gray-600">{inv.items}</div><div className="text-[10px] text-gray-500">{inv.seasonality}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Suggested Amount Split + Confirmation - NEW */}
      <Card>
        <CardHeader title="Suggested Budget Split" subtitle="How your startup budget is allocated" />
        <div className="grid gap-3 text-sm md:grid-cols-3">
          <div className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-center">
            <div className="text-xs font-bold uppercase tracking-widest text-teal-700">Startup Requirements</div>
            <div className="mt-1 text-xl font-black text-gray-900">₹{INR(startupReq)}</div>
            <div className="text-xs text-gray-500">Shop, equipment, licenses</div>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-center">
            <div className="text-xs font-bold uppercase tracking-widest text-amber-700">Initial Inventory</div>
            <div className="mt-1 text-xl font-black text-gray-900">₹{INR(inventoryReq)}</div>
            <div className="text-xs text-gray-500">Raw materials, stock</div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-center">
            <div className="text-xs font-bold uppercase tracking-widest text-slate-700">Other Essential</div>
            <div className="mt-1 text-xl font-black text-gray-900">₹{INR(otherReq)}</div>
            <div className="text-xs text-gray-500">Working capital + contingency</div>
          </div>
        </div>
        <div className="mt-4 rounded-xl bg-slate-900 px-4 py-3 text-white">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-widest text-white/60">Total Required</span>
            <span className="text-lg font-black">₹{INR(totalReq)}</span>
          </div>
        </div>
        <div className="mt-6">
          <h3 className="text-sm font-bold text-gray-900">Is this budget split okay?</h3>
          <p className="mt-1 text-xs text-gray-500">Confirm to proceed to Market Intelligence, or return to Analyze to change your inputs.</p>
          <div className="mt-4 flex gap-3">
            <button onClick={() => handleConfirm(true)} disabled={confirming} className="flex-1 rounded-xl bg-brand-600 px-6 py-3 text-sm font-bold text-white hover:bg-brand-700 disabled:opacity-50">Yes, Continue →</button>
            <button onClick={() => handleConfirm(false)} disabled={confirming} className="flex-1 rounded-xl border border-slate-200 bg-white px-6 py-3 text-sm font-bold text-slate-700 hover:bg-slate-50">Change Business Analysis</button>
          </div>
        </div>
      </Card>
      {loading && <div className="text-xs text-gray-400">Updating…</div>}
    </div>
  )
}

function Stat({ label, value }: { label:string; value:string }) {
  return <div><div className="text-[11px] text-gray-500">{label}</div><div className="font-bold text-gray-900">{value}</div></div>
}
