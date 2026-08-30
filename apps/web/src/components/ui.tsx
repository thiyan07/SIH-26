import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'

// --- shadcn/ui-style primitives ---

export function Button({ className = '', variant = 'primary', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'outline' | 'ghost' }) {
  const base =
    'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition-colors focus:outline-none disabled:opacity-50'
  const variants: Record<string, string> = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700',
    secondary: 'bg-brand-100 text-brand-700 hover:bg-brand-200',
    outline: 'border border-gray-300 text-gray-700 hover:bg-gray-50',
    ghost: 'text-brand-700 hover:bg-brand-50',
  }
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />
}

export function Card({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-xl border border-gray-200 bg-white p-5 shadow-sm ${className}`} {...props} />
}

export function CardHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h3 className="text-base font-semibold text-gray-900">{title}</h3>
      {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
    </div>
  )
}

const badgeColors: Record<string, string> = {
  green: 'bg-green-100 text-green-800',
  amber: 'bg-amber-100 text-amber-800',
  red: 'bg-red-100 text-red-800',
  gray: 'bg-gray-100 text-gray-700',
  blue: 'bg-blue-100 text-blue-800',
}

export function Badge({ color = 'gray', children }: { color?: keyof typeof badgeColors; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${badgeColors[color]}`}>{children}</span>
}

export function StatCard({ label, value, sub, badge }: { label: string; value: ReactNode; sub?: string; badge?: ReactNode }) {
  return (
    <Card>
      <div className="text-xs font-medium text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-gray-900">{value}</div>
      {sub && <div className="mt-1 text-xs text-gray-500">{sub}</div>}
      {badge && <div className="mt-2">{badge}</div>}
    </Card>
  )
}

export function ScoreBar({ label, value, color = 'green' }: { label: string; value: number; color?: string }) {
  const barColor = color === 'green' ? 'bg-brand-500' : color === 'amber' ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-gray-700">{label}</span>
        <span className="font-semibold text-gray-900">{value}/100</span>
      </div>
      <div className="h-2 w-full rounded bg-gray-100">
        <div className={`h-2 rounded ${barColor}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  )
}

export function Provenance({ source, reference, confidence, note }: { source?: string; reference?: string; confidence?: string; note?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3 text-xs text-gray-600">
      {source && (
        <div>
          <span className="font-medium text-gray-700">Source: </span>
          {source}
        </div>
      )}
      {reference && (
        <div>
          <span className="font-medium text-gray-700">Reference: </span>
          {reference}
        </div>
      )}
      {confidence && (
        <div>
          <span className="font-medium text-gray-700">Confidence: </span>
          {confidence}
        </div>
      )}
      {note && <div className="mt-1 italic">{note}</div>}
    </div>
  )
}

export function Disclaimer({ children }: { children: ReactNode }) {
  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
      <strong>Disclaimer: </strong>
      {children}
    </div>
  )
}
