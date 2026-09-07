import { useEffect, useState } from 'react'

const STEPS = [
  { title: 'Welcome to GramBiz AI', desc: 'This 30s tour shows how to get your feasibility score.' },
  { title: '1. Analyze', desc: 'Pick village, set capital & category, drop exact pin and confirm.' },
  { title: '2. Dashboard', desc: 'See opportunity score, profit model and repayment health.' },
  { title: '3. Map & Market', desc: 'Explore competitors, mandis and live prices.' },
  { title: '4. Finance & Report', desc: 'Check EMI, moratorium and export your report.' },
]

export function Tour() {
  const [open, setOpen] = useState(()=>{
    return !localStorage.getItem('grambiz.tourDone')
  })
  const [idx, setIdx] = useState(0)
  const [showHelp, setShowHelp] = useState(false)

  useEffect(()=>{
    const h = (e: KeyboardEvent)=>{
      if (e.key==='?') setShowHelp(v=>!v)
      if (e.key==='Escape') { setOpen(false); setShowHelp(false) }
    }
    window.addEventListener('keydown', h)
    return ()=> window.removeEventListener('keydown', h)
  },[])

  if (!open && !showHelp) {
    return (
      <button data-testid="tour-open" onClick={()=>setOpen(true)} className="fixed bottom-4 left-4 z-30 rounded-full bg-white px-3 py-1.5 text-xs font-semibold shadow-lg ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-white">
        Take Tour
      </button>
    )
  }

  if (showHelp && !open) {
    return (
      <div data-testid="help-modal" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-5 dark:bg-slate-900">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">Keyboard Shortcuts</h3>
          <ul className="mt-3 space-y-1 text-xs text-slate-600 dark:text-slate-300">
            <li><b>Ctrl/Cmd+K</b> — Command palette</li>
            <li><b>?</b> — Toggle this help</li>
            <li><b>Esc</b> — Close modals</li>
          </ul>
          <button onClick={()=>setShowHelp(false)} className="mt-4 rounded-xl bg-slate-900 px-3 py-1.5 text-xs font-bold text-white">Close</button>
        </div>
      </div>
    )
  }

  if (!open) return null
  const s = STEPS[idx]
  return (
    <div data-testid="tour-modal" className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900">
        <div className="text-xs font-bold uppercase tracking-widest text-brand-600">Step {idx+1}/{STEPS.length}</div>
        <h3 className="mt-1 text-lg font-bold text-slate-900 dark:text-white">{s.title}</h3>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{s.desc}</p>
        <div className="mt-4 flex justify-between">
          <button onClick={()=>{
            localStorage.setItem('grambiz.tourDone','1')
            setOpen(false)
          }} className="text-xs text-slate-500">
            Skip tour
          </button>
          <div className="flex gap-2">
            {idx>0 && <button data-testid="tour-prev" onClick={()=>setIdx(i=>i-1)} className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-semibold">Back</button>}
            {idx < STEPS.length-1 ? (
              <button data-testid="tour-next" onClick={()=>setIdx(i=>i+1)} className="rounded-xl bg-brand-600 px-4 py-1.5 text-xs font-bold text-white">Next</button>
            ) : (
              <button data-testid="tour-done" onClick={()=>{
                localStorage.setItem('grambiz.tourDone','1')
                setOpen(false)
              }} className="rounded-xl bg-brand-600 px-4 py-1.5 text-xs font-bold text-white">Done</button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
