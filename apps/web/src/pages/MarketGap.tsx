import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { tr } from '../lib/i18n'
import { Card, CardHeader } from '../components/ui'

export function MarketGap() {
  const { lang } = useAnalysis()
  const { id } = useParams()
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const run = async () => {
    if (!id) return
    setLoading(true)
    try {
      const r: any = await api.post(`/user/businesses/${id}/market-gap`, { radius_m: 1000, categories: ["grocery","restaurant","pharmacy","textile","bakery","hardware"] })
      setResult(r)
    } finally { setLoading(false) }
  }
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title={tr('marketGapTitle', lang)} subtitle={tr('marketGapSubtitle', lang)} />
        <button onClick={run} disabled={loading} className="m-4 rounded-xl bg-brand-600 px-5 py-2 text-sm font-bold text-white disabled:opacity-50">{loading?'Analyzing…':'Analyze 1km radius'}</button>
        {result && (
          <div className="p-4">
            <p className="text-xs text-gray-500">{result.note}</p>
            <ul className="mt-3 divide-y divide-gray-100">
              {result.gaps.map((g:any)=>(
                <li key={g.category} className="flex justify-between py-2 text-sm">
                  <span className="font-medium">{g.category} · {g.count} competitors</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${g.verdict==='saturated'?'bg-red-100 text-red-700': g.verdict==='moderate'?'bg-amber-100 text-amber-700':'bg-green-100 text-green-700'}`}>{g.verdict}</span>
                </li>
              ))}
            </ul>
            <div className="mt-3 space-y-1 text-xs text-gray-600">
              {result.gaps.map((g:any)=> g.limitations?.length ? <div key={g.category}>• {g.category}: {g.limitations.join(' · ')}</div> : null)}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
