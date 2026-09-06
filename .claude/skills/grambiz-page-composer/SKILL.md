---
name: grambiz-page-composer
description: Page composition and navigation for GramBiz AI. Use when adding a new route, restructuring the sidebar/topbar, or aligning a page to the AppShell layout.
---

# Grambiz Page Composer Skill

## Layout
- `src/components/layout/AppShell.tsx` wraps all authenticated routes
- `src/components/layout/TopBar.tsx` — logo, command palette (Ctrl+K), lang switch, analysis badge
- `src/components/layout/Sidebar.tsx` — grouped nav (Plan / Discover / Money / Output)
- `src/components/PageHeader.tsx` — `PageHeader` + `SubNav` for page titles
- `src/components/Layout.tsx` — legacy wrapper delegating to AppShell (keep for imports)

## Adding a new page
1. Create `src/pages/MyPage.tsx`:
```tsx
import { PageHeader } from '../components/PageHeader'
import { Card, CardHeader } from '../components/ui'
export function MyPage(){ return <div className="space-y-6"><PageHeader eyebrow="Discover" title="My Page" desc="One-line purpose" /><Card><CardHeader title="…" />…</Card></div> }
```
2. Register in `src/App.tsx`:
```tsx
import { MyPage } from './pages/MyPage'
<Route path="/my-page" element={<Guarded><MyPage /></Guarded>} />
```
3. Add to `Sidebar.tsx` `ITEMS` array with `group` and `icon`.

## Alignment rules
- Every page starts with `PageHeader` — never a raw `<h1>`
- Page content uses `space-y-6` at top level, cards use `grid gap-4 md:grid-cols-2/3/4`
- Mobile nav is auto from `Sidebar.ITEMS` — no duplicate mobile list
- Keep `App.tsx` routes guarded via `ErrorBoundary` per path

## Navigation groups
- Plan: Analyze, Dashboard
- Discover: Map, Market
- Money: Finance, Simulator, Schemes
- Output: Report, Data, Loan Explainer
