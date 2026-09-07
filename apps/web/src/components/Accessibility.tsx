import { useEffect, useState } from 'react'

export function AccessibilityBar() {
  const [font, setFont] = useState<number>(()=>{
    const v = localStorage.getItem('grambiz.fontScale')
    return v ? Number(v) : 100
  })
  const [highContrast, setHighContrast] = useState(()=>{
    return localStorage.getItem('grambiz.highContrast') === '1'
  })
  useEffect(()=>{
    document.documentElement.style.fontSize = `${font}%`
    localStorage.setItem('grambiz.fontScale', String(font))
  },[font])
  useEffect(()=>{
    document.documentElement.classList.toggle('high-contrast', highContrast)
    localStorage.setItem('grambiz.highContrast', highContrast ? '1' : '0')
  },[highContrast])
  return (
    <div data-testid="accessibility-bar" className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 text-xs dark:border-slate-700 dark:bg-slate-800">
      <span className="font-semibold text-slate-700 dark:text-slate-200">Accessibility:</span>
      <button data-testid="font-decrease" onClick={()=>setFont(f=>Math.max(80, f-10))} className="rounded-lg border border-slate-200 px-2 py-1 dark:border-slate-600">A-</button>
      <span className="text-slate-600 dark:text-slate-300">{font}%</span>
      <button data-testid="font-increase" onClick={()=>setFont(f=>Math.min(130, f+10))} className="rounded-lg border border-slate-200 px-2 py-1 dark:border-slate-600">A+</button>
      <button data-testid="high-contrast-toggle" onClick={()=>setHighContrast(v=>!v)} className={`rounded-lg px-2 py-1 font-semibold ${highContrast ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}>High Contrast</button>
      <span className="ml-auto text-[11px] text-slate-500">Press ? for shortcuts</span>
    </div>
  )
}
