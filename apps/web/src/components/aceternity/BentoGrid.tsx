import { Card3D } from "./Card3D"

export function BentoGrid({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const base = className.includes("grid-cols") ? `grid gap-6 ${className}` : `grid gap-4 md:grid-cols-3 ${className}`
  return <div className={base}>{children}</div>
}

export function BentoCard({ title, description, header, className = "", children }: { title?: string; description?: string; header?: React.ReactNode; className?: string; children?: React.ReactNode }) {
  return (
    <Card3D className={`h-full ${className}`}>
      <div className="flex h-full flex-col rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
        {header && <div className="mb-3">{header}</div>}
        {title && <h3 className="text-sm font-semibold text-gray-900">{title}</h3>}
        {description && <p className="mt-1 text-xs text-gray-500">{description}</p>}
        {children && <div className="mt-3 flex-1">{children}</div>}
      </div>
    </Card3D>
  )
}
