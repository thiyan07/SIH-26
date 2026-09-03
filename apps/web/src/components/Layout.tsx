import { NavLink, Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { tr, type Language } from '../lib/i18n'

const NAV = [
  { to: '/analyze', label: 'navAnalyze' as const },
  { to: '/dashboard', label: 'navDashboard' as const },
  { to: '/market', label: 'navMarket' as const },
  { to: '/map', label: 'navMap' as const },
  { to: '/finance', label: 'navFinance' as const },
  { to: '/simulator', label: 'navSimulator' as const },
  { to: '/report', label: 'navReport' as const },
  { to: '/schemes', label: 'navSchemes' as const },
  { to: '/data-sources', label: 'navData' as const },
  { to: '/loan-explainer', label: 'navLoanExplainer' as const },
]

export function Layout({ children, hideNav }: { children: ReactNode; hideNav?: boolean }) {
  const { lang, setLang } = useAnalysis()
  return (
    <div className="min-h-full">
      {!hideNav && (
        <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
            <Link to="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">G</span>
              <div className="leading-tight">
                <div className="text-sm font-bold text-gray-900">GramBiz AI</div>
                <div className="hidden text-[10px] text-gray-500 sm:block">{tr('subtitle', lang)}</div>
              </div>
            </Link>
            <div className="flex items-center gap-1 overflow-x-auto">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  className={({ isActive }) =>
                    `whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                      isActive ? 'bg-brand-50 text-brand-700' : 'text-gray-600 hover:bg-gray-100'
                    }`
                  }
                >
                  {tr(n.label, lang)}
                </NavLink>
              ))}
            </div>
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as Language)}
              className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700"
            >
              <option value="en">English</option>
              <option value="ta">தமிழ்</option>
              <option value="hi">हिंदी</option>
            </select>
          </div>
        </header>
      )}
      <main className={hideNav ? '' : 'mx-auto max-w-7xl px-4 py-6'}>{children}</main>
      {!hideNav && (
        <footer className="mt-8 border-t border-gray-200 bg-white py-4 text-center text-xs text-gray-400">
          {tr('footer', lang)}
        </footer>
      )}
    </div>
  )
}
