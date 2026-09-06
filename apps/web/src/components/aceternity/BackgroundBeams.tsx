export function BackgroundBeams({ className = "", children }: { className?: string; children?: React.ReactNode }) {
  return (
    <div className={`relative overflow-hidden bg-slate-950 ${className}`}>
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-br from-teal-900/20 via-transparent to-cyan-900/20" />
        <svg className="absolute inset-0 h-full w-full opacity-20" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="beams" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
            </pattern>
            <linearGradient id="beamGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#14b8a6" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0" />
            </linearGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#beams)" />
          {[...Array(6)].map((_, i) => (
            <path
              key={i}
              d={`M ${-100 + i * 200} 0 Q ${200 + i * 100} ${300 + i * 50} ${400 + i * 200} ${600 + i * 100} T ${800 + i * 100} 800`}
              stroke="url(#beamGrad)"
              strokeWidth="1.5"
              fill="none"
              opacity={0.3 - i * 0.03}
              className="animate-pulse"
              style={{ animationDelay: `${i * 0.5}s`, animationDuration: `${3 + i}s` }}
            />
          ))}
        </svg>
        <div className="absolute top-0 h-px w-full bg-gradient-to-r from-transparent via-teal-500/20 to-transparent" />
      </div>
      <div className="relative">{children}</div>
    </div>
  )
}

export function Spotlight({ className = "", children }: { className?: string; children?: React.ReactNode }) {
  return (
    <div className={`relative overflow-hidden ${className}`}>
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-gradient-to-r from-teal-500/10 via-cyan-500/10 to-blue-500/10 blur-3xl" />
      <div className="relative">{children}</div>
    </div>
  )
}
