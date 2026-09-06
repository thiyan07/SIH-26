import { NavLink } from 'react-router-dom'
import { tr, type Language } from '../../lib/i18n'

type Item = { to: string; labelKey: string; icon: string; desc: string; group: string }

const ITEMS: Item[] = [
  { to: '/analyze', labelKey: 'navAnalyze', icon: '🧭', desc: 'Feasibility', group: 'Plan' },
  { to: '/dashboard', labelKey: 'navDashboard', icon: '📊', desc: 'Score & ROI', group: 'Plan' },
  { to: '/map', labelKey: 'navMap', icon: '🗺️', desc: 'Live map', group: 'Discover' },
  { to: '/market', labelKey: 'navMarket', icon: '🏪', desc: 'Prices & peers', group: 'Discover' },
  { to: '/finance', labelKey: 'navFinance', icon: '💳', desc: 'Loan plan', group: 'Money' },
  { to: '/simulator', labelKey: 'navSimulator', icon: '🎛️', desc: 'What-if', group: 'Money' },
  { to: '/schemes', labelKey: 'navSchemes', icon: '🏛️', desc: 'Subsidies', group: 'Money' },
  { to: '/report', labelKey: 'navReport', icon: '📄', desc: 'Printable', group: 'Output' },
  { to: '/data-sources', labelKey: 'navData', icon: '🔗', desc: 'Provenance', group: 'Output' },
  { to: '/loan-explainer', labelKey: 'navLoanExplainer', icon: '🎓', desc: 'Learn', group: 'Output' },
  { to: '/compare', labelKey: 'navCompare' as any, icon: '⚖️', desc: 'Village vs', group: 'Output' },
  { to: '/history', labelKey: 'navHistory' as any, icon: '🕘', desc: 'Past runs', group: 'Output' },
]

const GROUPS = ['Plan','Discover','Money','Output'] as const

export function Sidebar({ lang, collapsed }: { lang: Language; collapsed?: boolean }) {
  return (
    <aside className={`${collapsed ? 'w-[72px]' : 'w-[270px]'} hidden shrink-0 flex-col border-r border-slate-200/70 bg-white lg:flex`}>
      <div className="space-y-6 p-4">
        {GROUPS.map(g => (
          <div key={g}>
            {!collapsed && <div className="mb-2 px-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">{g}</div>}
            <div className="space-y-1">
              {ITEMS.filter(i=>i.group===g).map(n => (
                <NavLink key={n.to} to={n.to}
                  className={({isActive}) => `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all ${isActive ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'} ${collapsed ? 'justify-center' : ''}`}>
                  <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm ${collapsed ? '' : 'bg-white/10'} border border-transparent shadow-sm`}>{n.icon}</span>
                  {!collapsed && <div className="min-w-0 text-left">
                    <div className="font-semibold leading-none">{tr(n.labelKey as any, lang)}</div>
                    <div className={`text-xs leading-none ${n.to==='/analyze' ? '' : 'opacity-60'}`}>{n.desc}</div>
                  </div>}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </div>
      {!collapsed && (
        <div className="mt-auto p-4">
          <div className="rounded-2xl bg-gradient-to-br from-brand-600 to-cyan-600 p-4 text-white shadow-lg">
            <div className="text-xs font-bold uppercase tracking-widest text-white/80">Need help?</div>
            <div className="mt-1 text-sm font-semibold leading-tight">Describe your business in Tamil, Hindi or English — AI will pre-fill everything.</div>
            <a href="/analyze" className="mt-3 inline-flex rounded-lg bg-white px-3 py-1.5 text-xs font-bold text-brand-700">Try advisory →</a>
          </div>
        </div>
      )}
    </aside>
  )
}

export function MobileNav({ lang }: { lang: Language }) {
  // horizontal scroll on mobile
  return (
    <div className="flex gap-1.5 overflow-x-auto px-2 pb-2 lg:hidden">
      {ITEMS.map(n=>(
        <NavLink key={n.to} to={n.to} className={({isActive})=>`whitespace-nowrap rounded-full px-3.5 py-2 text-xs font-semibold transition-all flex items-center gap-1.5 ${isActive ? 'bg-slate-900 text-white shadow' : 'bg-slate-100 text-slate-600'}`}>
          <span>{n.icon}</span>{tr(n.labelKey as any, lang)}
        </NavLink>
      ))}
    </div>
  )
}
