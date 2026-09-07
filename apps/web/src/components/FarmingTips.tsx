import { useAnalysis } from '../lib/analysisStore'

const TIPS: Record<string, string[]> = {
  dairy: ['Keep shed dry before rain — mastitis risk rises 30% in damp', 'Stock fodder before Thu rain, prices up 8%'],
  poultry: ['Heat 38°C+ — increase ventilation, add electrolytes', 'Monsoon: vaccinate against Newcastle'],
  grocery: ['Stock before weekend market rush, demand +22%', 'Keep cold chain for milk 4°C'],
  restaurant: ['Weekend rush Sat-Sun — prep 1.5x stock', 'Rain → delivery demand up 18%, keep Swiggy active'],
  default: ['Check 7-day forecast before stocking perishables', 'Store grains <14% moisture to avoid fungus'],
}

export function FarmingTips() {
  const { result } = useAnalysis()
  const cat = result?.profit_model?.category_code || 'default'
  const tips = TIPS[cat] || TIPS.default
  const forecast = (result as any)?.weather?.risk?.factors || []
  const hasRain = forecast.some((f:any)=> f.factor.includes('flood') || f.factor.includes('drought'))
  return (
    <div data-testid="farming-tips" className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-950/30">
      <div className="text-xs font-bold uppercase tracking-widest text-emerald-700 dark:text-emerald-300">🌱 Farming Tips • {cat}</div>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-emerald-900 dark:text-emerald-100">
        {tips.map((t,i)=><li key={i}>{t}</li>)}
        {hasRain && <li className="font-semibold">Weather alert: prepare for rain — cover feed & stock</li>}
      </ul>
      <div className="mt-2 text-[11px] text-emerald-700/70 dark:text-emerald-300/70">Based on live weather + seasonal model — not guaranteed</div>
    </div>
  )
}
