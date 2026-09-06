import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'

export function Button({ className = '', variant = 'primary', size = 'md', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'soft'; size?: 'sm' | 'md' | 'lg' }) {
  const base = 'inline-flex items-center justify-center gap-1.5 rounded-xl font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/20 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]'
  const sizes: Record<string,string> = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-sm',
  }
  const variants: Record<string, string> = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700 shadow-sm hover:shadow-md',
    secondary: 'bg-brand-50 text-brand-800 hover:bg-brand-100 border border-brand-100',
    soft: 'bg-slate-900 text-white hover:bg-slate-800 shadow',
    outline: 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 shadow-sm',
    ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  }
  return <button className={`${base} ${sizes[size]} ${variants[variant]} ${className}`} {...props} />
}

export function Card({ className = '', hover=false, ...props }: HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return <div className={`rounded-2xl border border-slate-200/70 bg-white shadow-soft ${hover ? 'transition-all hover:shadow-card hover:-translate-y-0.5' : ''} ${className}`} {...props} />
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h3 className="text-sm font-bold tracking-tight text-slate-900">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

const badgeColors: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-700 ring-amber-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
  gray: 'bg-slate-100 text-slate-600 ring-slate-200',
  blue: 'bg-sky-50 text-sky-700 ring-sky-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
}

export function Badge({ color = 'gray', children, className='' }: { color?: keyof typeof badgeColors; children: ReactNode; className?: string }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${badgeColors[color]} ${className}`}>{children}</span>
}

export function StatCard({ label, value, sub, badge, icon }: { label: string; value: ReactNode; sub?: string; badge?: ReactNode; icon?: ReactNode }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</div>
        {icon && <div className="rounded-lg bg-slate-50 p-1.5 text-slate-500">{icon}</div>}
      </div>
      <div className="mt-2 text-2xl font-extrabold tracking-tight text-slate-900 tabular">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
      {badge && <div className="mt-3">{badge}</div>}
    </Card>
  )
}

export function Metric({ label, value, hint, trend }: { label: string; value: string; hint?: string; trend?: 'up'|'down'|'neutral' }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="text-lg font-bold text-slate-900 tabular">{value}</span>
        {trend && <span className={`text-xs ${trend==='up' ? 'text-emerald-600' : trend==='down' ? 'text-red-600' : 'text-slate-400'}`}>{trend==='up'?'↗':'↘'}</span>}
      </div>
      {hint && <div className="text-xs text-slate-500">{hint}</div>}
    </div>
  )
}

export function ScoreBar({ label, value, color = 'green', hint }: { label: string; value: number; color?: string; hint?: string }) {
  const barColor = color === 'green' ? 'bg-brand-500' : color === 'amber' ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="mb-3">
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="flex items-center font-medium text-slate-700">
          {label}
          {hint && <span title={hint} className="ml-1.5 inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-500">?</span>}
        </span>
        <span className="font-bold text-slate-900 tabular">{value}<span className="text-slate-400 font-normal">/100</span></span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-2 rounded-full transition-all duration-700 ${barColor}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  )
}

export function Provenance({ source, reference, confidence, note }: { source?: string; reference?: string; confidence?: string; note?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/70 p-3 text-xs leading-relaxed text-slate-600">
      {source && <div><span className="font-semibold text-slate-700">Source: </span>{source}</div>}
      {reference && <div><span className="font-semibold text-slate-700">Ref: </span>{reference}</div>}
      {confidence && <div><span className="font-semibold text-slate-700">Confidence: </span>{confidence}</div>}
      {note && <div className="mt-1 italic text-slate-500">{note}</div>}
    </div>
  )
}

export function Disclaimer({ children }: { children: ReactNode }) {
  return (
    <div className="mt-4 flex gap-2 rounded-xl border border-amber-200 bg-amber-50/80 p-3 text-xs leading-relaxed text-amber-900">
      <span className="text-sm">⚠️</span><span><strong>Note: </strong>{children}</span>
    </div>
  )
}

export function Section({ title, desc, children, action }: { title: string; desc?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-widest text-slate-700">{title}</h2>
          {desc && <p className="text-xs text-slate-500">{desc}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

export function EmptyState({ icon, title, desc, action }: { icon?: string; title: string; desc: string; action?: ReactNode }) {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-2xl">{icon ?? '🌾'}</div>
      <h3 className="mt-4 text-base font-bold text-slate-900">{title}</h3>
      <p className="mt-1.5 text-sm text-slate-500">{desc}</p>
      {action && <div className="mt-5 flex justify-center gap-2">{action}</div>}
    </div>
  )
}
