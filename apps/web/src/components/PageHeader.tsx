import type { ReactNode } from 'react'

export function PageHeader({ eyebrow, title, desc, action }: { eyebrow?: string; title: string; desc?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        {eyebrow && <div className="text-[11px] font-bold uppercase tracking-widest text-brand-700">{eyebrow}</div>}
        <h1 className="text-xl font-extrabold tracking-tight text-slate-900 sm:text-2xl">{title}</h1>
        {desc && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-500">{desc}</p>}
      </div>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  )
}

export function SubNav({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-1.5 rounded-2xl bg-slate-100 p-1.5">{children}</div>
}
