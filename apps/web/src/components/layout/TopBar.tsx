import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAnalysis } from '../../lib/analysisStore'
import { tr, type Language } from '../../lib/i18n'
import { useEffect, useState } from 'react'

export function TopBar() {
  const { lang, setLang, result } = useAnalysis()
  const loc = useLocation()
  const nav = useNavigate()
  const [q,setQ] = useState('')
  const [cmdOpen,setCmdOpen] = useState(false)

  // Force light mode — dark variant had white-on-white contrast bugs reported
  useEffect(()=>{
    document.documentElement.classList.remove('dark')
    localStorage.setItem('grambiz.theme', 'light')
  },[])
  // cmd+k
  useEffect(()=>{
    const h=(e:KeyboardEvent)=>{ if((e.metaKey||e.ctrlKey)&& e.key.toLowerCase()==='k'){ e.preventDefault(); setCmdOpen(v=>!v)}}
    window.addEventListener('keydown',h); return ()=>window.removeEventListener('keydown',h)
  },[])

  const breadcrumb = loc.pathname==='/' ? 'Home' : loc.pathname.replace('/','').replace('-',' ').replace(/\b\w/g,c=>c.toUpperCase())

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/60 bg-white dark:border-slate-800 dark:bg-slate-900 [transform:translateZ(0)]">
      <div className="mx-auto flex h-[60px] max-w-[1600px] items-center justify-between gap-3 px-3 sm:px-4">
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-600 to-cyan-600 font-extrabold text-white shadow-md">G</span>
            <div className="hidden leading-tight sm:block">
              <div className="text-sm font-extrabold tracking-tight text-slate-900 dark:text-white">GramBiz AI</div>
              <div className="text-[10px] font-medium text-slate-500 dark:text-slate-500">{tr('subtitle', lang)}</div>
            </div>
            <span className="hidden rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800 lg:inline">SIH 26091</span>
          </Link>
          {loc.pathname!=='/' && <span className="hidden items-center gap-1.5 text-xs text-slate-500 sm:flex"><span className="h-3 w-px bg-slate-200"/> {breadcrumb}</span>}
        </div>

        <div className="flex items-center gap-2">
          {/* command search */}
          <button onClick={()=>setCmdOpen(true)} className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-500 hover:bg-white sm:flex">
            <span className="text-sm">⌘</span> Search <span className="ml-2 hidden rounded bg-white px-1.5 py-0.5 text-[10px] ring-1 ring-slate-200 sm:inline">Ctrl+K</span>
          </button>

          {result && <span className="hidden rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200 sm:inline">● Analysis ready</span>}
          {!result && <span className="hidden rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500 sm:inline">No analysis yet</span>}


          <select value={lang} onChange={e=>setLang(e.target.value as Language)} className="rounded-xl border border-slate-200 bg-white px-2.5 py-2 text-xs font-semibold shadow-sm">
            <option value="en">EN</option><option value="ta">TA</option><option value="hi">HI</option>
          </select>
          <Link to="/analyze" className="hidden rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white shadow hover:bg-slate-800 sm:inline">Analyze →</Link>
        </div>
      </div>
      {cmdOpen && <CommandPalette q={q} setQ={setQ} onClose={()=>setCmdOpen(false)} nav={nav} lang={lang} />}
    </header>
  )
}

function CommandPalette({ q, setQ, onClose, nav, lang }: { q:string; setQ:(s:string)=>void; onClose:()=>void; nav: ReturnType<typeof useNavigate>; lang: Language }) {
  const items = [
    { to: '/analyze', label: tr('navAnalyze', lang), hint: 'New feasibility' },
    { to: '/dashboard', label: tr('navDashboard', lang), hint: 'Score & profit' },
    { to: '/market', label: tr('navMarket', lang), hint: 'Prices & map' },
    { to: '/finance', label: tr('navFinance', lang), hint: 'Loan schedule' },
    { to: '/schemes', label: tr('navSchemes', lang), hint: 'Eligibility' },
    { to: '/report', label: tr('navReport', lang), hint: 'Print / PDF' },
  ].filter(i=> !q || i.label.toLowerCase().includes(q.toLowerCase()))
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/30 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl" onClick={e=>e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b p-3">
          <span className="text-slate-500">⌕</span>
          <input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="Jump to Dashboard, Finance, Schemes..." className="w-full bg-transparent text-sm outline-none placeholder:text-slate-500" />
          <button onClick={onClose} className="rounded-lg bg-slate-100 px-2 py-1 text-xs">ESC</button>
        </div>
        <div className="max-h-72 overflow-auto p-2">
          {items.map(i=>(
            <button key={i.to} onClick={()=>{ nav(i.to); onClose()}} className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left hover:bg-slate-50">
              <span className="text-sm font-semibold text-slate-800">{i.label}</span><span className="text-xs text-slate-500">{i.hint}</span>
            </button>
          ))}
          {items.length===0 && <div className="px-3 py-8 text-center text-sm text-slate-500">No results</div>}
        </div>
      </div>
    </div>
  )
}
