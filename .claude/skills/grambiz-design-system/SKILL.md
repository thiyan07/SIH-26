---
name: grambiz-design-system
description: Design tokens, theming and global styling for GramBiz AI frontend. Use when updating colors, typography, spacing, shadows, or Tailwind config. Covers CSS variables, Tailwind extension and the app-bg mesh.
---

# Grambiz Design System Skill

## When to use
- Changing brand palette, radius, shadows, or typography
- Adding dark mode or new semantic tokens
- Editing `tailwind.config.js` or `src/index.css`

## Tokens
Located in `apps/web/src/index.css` (`:root` HSL variables) and `apps/web/tailwind.config.js` (`extend.colors`, `extend.boxShadow`, `extend.animation`).

| Token | Value | Usage |
|-------|-------|-------|
| `--primary` | 173 80% 32% (brand-600) | Primary buttons, active nav |
| `--background` / `--foreground` | white / slate-900 | Page bg / text |
| `--radius` | 0.85rem | Card / button rounding |
| `brand.600` | #0d9488 | Charts (`LINK_BRAND`), badges |
| `shadow.soft` / `shadow.card` | subtle | Cards, hover |

## Rules
1. Never hardcode hex in components — use `bg-brand-600`, `text-slate-900`, `border-slate-200/70`, etc.
2. Use `className="app-bg"` on the top-level shell (`AppShell.tsx`) — it renders the teal/cyan mesh.
3. Add new colors as HSL CSS variables first, then expose via Tailwind `extend.colors`.
4. Keep `Inter` for UI, `Fraunces` (optional) for display headings, `Noto Sans Tamil/Devanagari` as fallbacks — already in `index.html`.
5. Verify with `npm run build` — Tailwind purges via `content: ['./index.html','./src/**/*.{ts,tsx}']`.

## Quick edits
```ts
// tailwind.config.js — add a new semantic
colors: { success: { DEFAULT: 'hsl(142 70% 45%)' } }

// index.css
:root { --success: 142 70% 45%; }
```

## Checklist
- [ ] Tokens in both `index.css` and `tailwind.config.js`
- [ ] No raw hex in new components
- [ ] `app-bg` preserved on shell
- [ ] `npm run typecheck` passes
