# Frontend Restructure — GramBiz AI (2026-09-06)

## Goals
- Beautiful, consistent UI across all 11 routes
- Aligned navigation / IA so every feature is discoverable
- Reusable primitives + skills for future UI work

## What changed

### 1. Design system (`tailwind.config.js` + `index.css`)
- HSL CSS variables (`--background`, `--primary`, `--radius`, etc.) + Tailwind `extend.colors` mapping
- Brand palette shifted to teal `brand.50..950` (`#0d9488` primary), `shadow.soft/card/glow`, `fade-in` animation
- Global mesh `app-bg` (teal/cyan radial gradients), glass utility, custom scrollbar, focus ring
- Typography: `Inter` + `Fraunces` display + `Noto Sans Tamil/Devanagari` fallbacks (added to `index.html`)

### 2. Layout restructure
```
src/components/layout/
  AppShell.tsx   — TopBar + Sidebar + main + footer (app-bg)
  TopBar.tsx     — logo, Ctrl+K command palette, lang switch, analysis badge
  Sidebar.tsx    — grouped nav (Plan/Discover/Money/Output) + mobile horizontal scroll
src/components/Layout.tsx — legacy wrapper delegating to AppShell (keeps old imports)
src/components/PageHeader.tsx — PageHeader + SubNav primitives
```
- Sidebar groups: **Plan** (Analyze, Dashboard) · **Discover** (Map, Market) · **Money** (Finance, Simulator, Schemes) · **Output** (Report, Data, Loan Explainer)
- TopBar exposes search (Ctrl+K) jumping to any route; shows `● Analysis ready` when `result` exists
- Mobile nav is single source from `Sidebar.ITEMS`

### 3. Landing redesign (`src/pages/Landing.tsx`)
- Dark hero with mesh + blurred glow, pulse badge, 4-step mini cards
- Two-column hero: copy + Globe preview with 3 stat tiles
- 6-feature grid (mapping, score, finance, schemes, climate, multilingual) + How-it-works bento + SIH callout

### 4. UI primitives (`src/components/ui.tsx`)
- `Button` variants `primary|secondary|soft|outline|ghost` + `sm|md|lg` + active scale
- `Card` (`rounded-2xl border-slate-200/70 shadow-soft`, optional `hover`), `CardHeader` with action slot
- `Badge` (ringed pastels), `StatCard`, `Metric`, `ScoreBar`, `Section`, `EmptyState`, `Disclaimer`
- `ui/data-table.tsx` — searchable, sortable, paginated table

### 5. Feature alignment
All routes remain under `src/App.tsx` guarded by `ErrorBoundary`:
`/` · `/analyze` · `/dashboard` · `/market` · `/map` · `/finance` · `/simulator` · `/report` · `/schemes` · `/data-sources` · `/loan-explainer`
No route removed; navigation is now grouped and discoverable on desktop (sidebar) + mobile (horizontal pills) + command palette.

### 6. Skills for future UI work (`.claude/skills/`)
| Skill | Purpose |
|-------|---------|
| `grambiz-design-system` | Tokens, Tailwind, `index.css`, `app-bg` |
| `grambiz-ui-primitives` | Button/Card/Badge/Metric/DataTable usage |
| `grambiz-page-composer` | Adding routes, AppShell, PageHeader |
| `grambiz-data-viz` | Recharts, ScoreDonut, BusinessMap, finance helpers |
| `grambiz-i18n-a11y` | `tr()`, `interpolate`, lang switch, a11y checklist |

Each skill has a `SKILL.md` with when-to-use, code snippets and checklists.

## Verification
```bash
cd apps/web
npm run typecheck  # tsc -b — passes
npm run build     # vite build — 7s, chunks gzipped
npm run lint      # eslint — 2 warnings only (pre-existing)
```

## Next recommended polish (optional)
- Wrap `Dashboard`/`Market`/`Finance` headers with `PageHeader` for full header parity
- Add `darkMode: 'class'` + toggle in `TopBar` using existing HSL variables
- Extract `Analyze`'s long form into subcomponents (`AdvisoryPanel`, `LocationPickerCard`, `CapitalCard`)
