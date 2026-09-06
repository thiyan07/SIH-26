import type { ReactNode } from 'react'
import { Sidebar, MobileNav } from './Sidebar'
import { TopBar } from './TopBar'
import { useAnalysis } from '../../lib/analysisStore'
import { tr } from '../../lib/i18n'

export function AppShell({ children, hideChrome }: { children: ReactNode; hideChrome?: boolean }) {
  const { lang } = useAnalysis()
  if (hideChrome) return <>{children}</>
  return (
    <div className="min-h-screen app-bg">
      <TopBar />
      <MobileNav lang={lang} />
      <div className="mx-auto flex max-w-[1600px]">
        <Sidebar lang={lang} />
        <main className="min-w-0 flex-1 px-3 py-5 sm:px-6 sm:py-6">{children}</main>
      </div>
      <footer className="border-t border-white/20 bg-gradient-to-r from-slate-900 via-brand-900 to-slate-900 py-5 text-center">
        <div className="text-xs font-medium text-white/80">{tr('footer', lang)}</div>
        <div className="mt-1 text-[10px] tracking-widest text-white/50">295 villages • 5,012 businesses • 24 schemes • MapCN + Three.js • SIH 2026</div>
      </footer>
    </div>
  )
}
