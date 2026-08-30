import { BRAND } from '../lib/theme'

export function ScoreDonut({ value, size = 140 }: { value: number; size?: number }) {
  const pct = Math.max(0, Math.min(100, value))
  const stroke = 14
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const dash = (pct / 100) * c
  const color = pct >= 60 ? BRAND[500] : pct >= 40 ? '#f59e0b' : '#ef4444'
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-3xl font-bold text-gray-900">{Math.round(pct)}</div>
        <div className="text-[10px] text-gray-400">/ 100</div>
      </div>
    </div>
  )
}
