import { useEffect, useState } from 'react'

type Day = { date: string; max: number; min: number; rain: number }

export function WeatherForecast({ lat, lon }: { lat: number; lon: number }) {
  const [days, setDays] = useState<Day[] | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=Asia%2FKolkata&forecast_days=7`)
      .then(r => r.json())
      .then(j => {
        const d = j.daily
        if (d) {
          setDays(d.time.map((t: string, i: number) => ({ date: t, max: d.temperature_2m_max[i], min: d.temperature_2m_min[i], rain: d.precipitation_sum[i] })))
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [lat, lon])

  if (loading) return <div className="rounded-xl bg-slate-50 p-3 text-xs text-slate-400">Loading 7-day forecast…</div>
  if (!days) return null
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400">7-day forecast (Open-Meteo)</div>
      <div className="mt-2 grid grid-cols-7 gap-1 text-center text-xs">
        {days.map(d=>(
          <div key={d.date} className="rounded-lg bg-slate-50 p-1.5">
            <div className="font-medium text-slate-700">{new Date(d.date).toLocaleDateString('en-IN', { weekday: 'short' })}</div>
            <div className="text-[10px] text-slate-400">{d.date.slice(5)}</div>
            <div className="mt-1 font-bold text-slate-900">{Math.round(d.max)}°/{Math.round(d.min)}°</div>
            <div className="text-[10px] text-sky-600">{d.rain}mm rain</div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-slate-400">For your exact pinned village — helps you plan stock before rain.</p>
    </div>
  )
}
