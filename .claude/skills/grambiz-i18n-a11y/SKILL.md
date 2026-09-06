---
name: grambiz-i18n-a11y
description: i18n, accessibility and language switching for GramBiz AI. Use when adding user-facing strings, translating, or fixing a11y.
---

# Grambiz i18n & A11y Skill

## i18n
- Source: `src/lib/i18n.ts` — `dict` with `en|ta|hi` per key
- Store: `src/lib/analysisStore.tsx` — `lang` + `setLang`
- Usage:
```tsx
import { tr, interpolate, recommendationLabel } from '../lib/i18n'
tr('navDashboard', lang)
interpolate(tr('forProjectCost', lang), { cost: '₹2,80,000' })
```
- Add new key to `dict` in `i18n.ts` with all three languages — never inline English strings
- Use `tr()` for every user-visible string, including placeholders and table headers

## Language switcher
- `TopBar.tsx` and `Sidebar` read `useAnalysis().lang` — keep single source of truth
- Persist if needed via `localStorage` (currently in-memory only)

## A11y
- All interactive elements have `focus-visible:ring-brand-600/20` via `ui.tsx` Button
- Use `Badge` for status, not color alone — includes text label
- `ScoreBar` includes `title` hint for screen readers via `…`
- Tables need `<th scope="col">` — DataTable does this; custom tables should too
- Map pins need `aria-label` — BusinessMap handles it
- Test with keyboard (Tab / Shift+Tab) and `Ctrl+K` command palette

## Checklist
- [ ] New strings added to `dict` (en/ta/hi)
- [ ] No hardcoded English in JSX
- [ ] `lang` passed from `useAnalysis()` to `tr()`
- [ ] Focus states verified
