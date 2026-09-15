import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useAnalysis } from '../lib/analysisStore'
import { tr } from '../lib/i18n'
import { Card, CardHeader } from '../components/ui'

export function ForecastPage() {
  const { lang } = useAnalysis()
  const { id } = useParams()
  const [forecasts, setForecasts] = useState<any[]>([])
  const [selected, setSelected] = useState<any>(null)
  const load = async () => {
    if (!id) return
    const r: any = await api.get(`/user/businesses/${id}/forecasts`)
    setForecasts(r)
    if (r[0]) {
      const f: any = await api.get(`/user/businesses/${id}/forecasts/${r[0].id}`)
      setSelected(f)
    }
  }
  useEffect(()=>{ load() }, [id])
  const create = async () => {
    if (!id) return
    await api.post(`/user/businesses/${id}/forecasts`, { horizon_months: 6 })
    load()
  }
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title={tr('forecastTitle', lang)} subtitle={tr('forecastSubtitle', lang)} />
        <button onClick={create} className="m-4 rounded-xl bg-brand-600 px-5 py-2 text-sm font-bold text-white">Create Forecast</button>
        {forecasts.length>0 && <div className="px-4 text-xs text-gray-500">{forecasts.length} forecasts — latest: {forecasts[0].model_key} {forecasts[0].target_from}→{forecasts[0].target_to}</div>}
        {selected && (
          <div className="p-4">
            <p className="text-xs text-gray-500">{selected.note}</p>
            <div className="mt-3 grid gap-2">
              {Object.entries(selected.outputs).slice(0,4).map(([k, vals]: any)=>(
                <div key={k} className="rounded-lg bg-gray-50 p-3">
                  <div className="text-xs font-semibold capitalize">{k}</div>
                  <div className="text-xs text-gray-600">{(vals as number[]).join(' → ')}</div>
                  {selected.uncertainty?.[k] && <div className="text-[11px] text-gray-500">p10 {selected.uncertainty[k].p10[0]} · p90 {selected.uncertainty[k].p90[0]} ({selected.uncertainty[k].width})</div>}
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
