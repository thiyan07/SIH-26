---
name: grambiz-data-viz
description: Data visualization for GramBiz AI — Recharts, ScoreDonut, maps and finance schedules. Use when adding charts, score visuals, or geo layers.
---

# Grambiz Data Viz Skill

## Components
- `src/components/ScoreDonut.tsx` — circular overall score (use `value` 0–100, `size` 120–150)
- `src/components/BusinessMap.tsx` — Leaflet + clustering for competitors/markets/infra
- `src/mapcn/*` — MapCN wrapper (MapLibre) — use via `BusinessMap`, not directly
- `src/lib/finance.ts` — `emi()`, `schedule()` for loan math
- `src/lib/theme.ts` — `LINK_BRAND = #0d9488`, `BRAND` palette

## Recharts pattern
```tsx
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
<ResponsiveContainer width="100%" height={220}>
  <BarChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="name" tick={{fontSize:11}} /><YAxis tick={{fontSize:10}} /><Tooltip /><Bar dataKey="value" fill={LINK_BRAND} radius={[4,4,0,0]} /></BarChart>
</ResponsiveContainer>
```

## Rules
- Always use `LINK_BRAND` for primary series, never random hex
- Use `ResponsiveContainer width="100%" height={…}` — never fixed width
- For maps, pass `center={{latitude, longitude}}` and filter `businesses`/`markets` from `result`
- Finance charts derive from `result.financial_plan` + `result.monthly_economics` — never invent numbers
- Add `Disclaimer` below any estimated model

## ScoreDonut
```tsx
<ScoreDonut value={score.overall_score} size={150} />
```

## Schedule table
Use `Page: Finance.tsx:142` `ScheduleTable` as reference — slice first 12 rows, paginate rest.
