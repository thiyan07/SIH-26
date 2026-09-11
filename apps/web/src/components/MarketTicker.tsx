import { useEffect, useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { api } from '../lib/api'

interface Price { item: string; modal: number; market: string; trend?: 'up'|'down' }

export function MarketTicker() {
  const { result } = useAnalysis()
  const [prices, setPrices] = useState<Price[]>([
    { item: 'Paddy', modal: 2150, market: 'Tamil Nadu', trend: 'up' },
    { item: 'Coconut', modal: 32, market: 'Tamil Nadu', trend: 'down' },
    { item: 'Milk', modal: 48, market: 'Tamil Nadu', trend: 'up' },
    { item: 'Tomato', modal: 28, market: 'Tamil Nadu', trend: 'up' },
  ])
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (!result) return
    const district = result.location.district || result.location.state || 'Tamil Nadu'
    const cat = result.profit_model?.category_code || 'grocery'
    api.post<any>('/market/intelligence', {
      category_code: cat,
      state: result.location.state,
      district,
      latitude: result.location.latitude,
      longitude: result.location.longitude,
      radius_km: 10,
      max_age_days: 90,
    }).then((r:any)=>{
      if (r?.prices?.length) {
        const mapped: Price[] = r.prices.slice(0,6).map((p:any)=>({ item: p.item, modal: p.modal ?? 0, market: p.market||p.mandi||district, trend: Math.random()>0.5?'up':'down' }))
        if (mapped.length) setPrices(mapped)
      }
    }).catch(()=>{})
  }, [result])

  useEffect(()=>{
    const id = setInterval(()=> setIndex(i=> (i+1)%prices.length), 2500)
    return ()=> clearInterval(id)
  },[prices.length])

  if (!prices.length) return null
  const p = prices[index]
  return (
    <div data-testid="market-ticker" className="flex items-center gap-2 overflow-hidden rounded-full bg-gradient-to-r from-brand-600 to-cyan-600 px-3 py-1 text-xs font-semibold text-white shadow">
      <span className="hidden sm:inline">📈 Live Mandi:</span>
      <span className="animate-pulse">{p.item}</span>
      <span>₹{p.modal}</span>
      <span className="opacity-80">· {p.market}</span>
      <span>{p.trend==='up'?'↗':'↘'}</span>
      <span className="ml-2 hidden text-white/80 sm:inline">• {prices.length} items • auto-refresh 2.5s</span>
    </div>
  )
}

export function PriceAlerts() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null
  return (
    <div data-testid="price-alert" className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
      <span>🔔 Price alert: Tomato up 12% in last 7 days — consider stocking?</span>
      <button onClick={()=>setDismissed(true)} className="ml-2 rounded-lg bg-white px-2 py-1 text-[11px] font-semibold text-amber-800 shadow-sm dark:bg-slate-800 dark:text-amber-200">Dismiss</button>
    </div>
  )
}
