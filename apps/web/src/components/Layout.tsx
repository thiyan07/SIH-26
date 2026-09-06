import type { ReactNode } from 'react'
import { AppShell } from './layout/AppShell'

// Backward-compatible wrapper — delegates to new AppShell
export function Layout({ children, hideNav }: { children: ReactNode; hideNav?: boolean }) {
  return <AppShell hideChrome={hideNav}>{children}</AppShell>
}
