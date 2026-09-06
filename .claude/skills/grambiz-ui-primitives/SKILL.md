---
name: grambiz-ui-primitives
description: Reusable UI primitives for GramBiz AI. Use when building or editing buttons, cards, badges, metrics, empty states, or data tables. Ensures consistent spacing, a11y and hover/focus states.
---

# Grambiz UI Primitives Skill

## Sources
- `apps/web/src/components/ui.tsx` — Button, Card, CardHeader, Badge, StatCard, Metric, ScoreBar, Section, EmptyState
- `apps/web/src/components/ui/data-table.tsx` — DataTable with search/sort/pagination

## Button
```tsx
<Button variant="primary|secondary|soft|outline|ghost" size="sm|md|lg">Label</Button>
```
- Primary = brand fill, Soft = slate-900 fill, Outline = white + border
- Always use `size="sm"` for table actions, `lg` for hero CTAs

## Card
```tsx
<Card hover> <CardHeader title="…" subtitle="…" action={…} /> {children} </Card>
```
- Default: `rounded-2xl border-slate-200/70 shadow-soft`
- `hover` adds `hover:shadow-card hover:-translate-y-0.5`

## Badge
```tsx
<Badge color="green|amber|red|gray|blue|brand">GO</Badge>
```
- Colors are ringed pastels — never use raw bg without `ring-1 ring-inset`

## Stat / Metric
```tsx
<StatCard label="Project cost" value="₹2,80,000" sub="Scheme: PMMY" badge={<Badge>…</Badge>} />
<Metric label="Coverage" value="82%" hint="of relevant commodities" trend="up" />
```

## EmptyState
```tsx
<EmptyState icon="🗺️" title="No analysis yet" desc="Run analysis…" action={<Button>Analyze</Button>} />
```

## DataTable
```tsx
<DataTable data={rows} columns={[{key:'name', header:'Name', sortable:true}]} pageSize={10} />
```

## Rules
- Never recreate a button/card inline — import from `ui.tsx`
- Keep `tabular` class on numeric values for alignment
- Ensure focus ring (`focus-visible:ring-brand-600/20`) is preserved
