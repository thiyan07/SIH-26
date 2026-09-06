import { useRef } from "react"
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion"

export function Card3D({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const mx = useSpring(x, { stiffness: 300, damping: 20 })
  const my = useSpring(y, { stiffness: 300, damping: 20 })
  const rx = useTransform(my, [-0.5, 0.5], ["7deg", "-7deg"])
  const ry = useTransform(mx, [-0.5, 0.5], ["-7deg", "7deg"])

  const onMove = (e: React.MouseEvent) => {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return
    x.set((e.clientX - r.left) / r.width - 0.5)
    y.set((e.clientY - r.top) / r.height - 0.5)
  }
  const onLeave = () => { x.set(0); y.set(0) }

  return (
    <motion.div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ rotateX: rx, rotateY: ry, transformStyle: "preserve-3d" as any }}
      className={`relative ${className}`}
    >
      <div style={{ transform: "translateZ(30px)" }} className="h-full">
        {children}
      </div>
      <div className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-tr from-white/10 to-transparent opacity-60" style={{ transform: "translateZ(20px)" }} />
    </motion.div>
  )
}

export function Pin3D({ title, href, children }: { title?: string; href?: string; children: React.ReactNode }) {
  return (
    <div className="group relative flex h-full w-full flex-col">
      <div className="absolute left-1/2 top-0 flex -translate-x-1/2 justify-center">
        <div className="h-6 w-6 rounded-full bg-gradient-to-b from-white to-gray-400 shadow-lg" />
        <div className="absolute top-6 h-10 w-px bg-gradient-to-b from-gray-400 to-transparent" />
      </div>
      <div className="mt-8">
        <Card3D className="rounded-xl border border-white/20 bg-white/95 p-4 shadow-2xl backdrop-blur">
          {href ? <a href={href} target="_blank" rel="noopener" className="block">{children}</a> : children}
          {title && <div className="mt-2 text-xs font-medium text-gray-500">{title}</div>}
        </Card3D>
      </div>
    </div>
  )
}
