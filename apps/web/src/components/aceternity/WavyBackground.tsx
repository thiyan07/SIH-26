import { useEffect, useRef } from "react"

export function WavyBackground({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    let w = (canvas.width = canvas.offsetWidth * 2)
    let h = (canvas.height = canvas.offsetHeight * 2)
    ctx.scale(2, 2)
    w /= 2; h /= 2

    let t = 0
    let raf = 0
    const draw = () => {
      t += 0.005
      ctx.clearRect(0, 0, w, h)
      // gradient bg
      const g = ctx.createLinearGradient(0, 0, w, h)
      g.addColorStop(0, "#0f766e")
      g.addColorStop(0.5, "#0e7490")
      g.addColorStop(1, "#1e3a5f")
      ctx.fillStyle = g
      ctx.fillRect(0, 0, w, h)

      // waves
      for (let j = 0; j < 3; j++) {
        ctx.beginPath()
        ctx.moveTo(0, h * (0.55 + j * 0.08))
        for (let x = 0; x <= w; x += 10) {
          const y = Math.sin(x * 0.008 + t * (1 + j * 0.3) + j) * (18 + j * 10) + h * (0.6 + j * 0.07)
          ctx.lineTo(x, y)
        }
        ctx.lineTo(w, h)
        ctx.lineTo(0, h)
        ctx.closePath()
        ctx.fillStyle = j === 0 ? "rgba(255,255,255,0.08)" : j === 1 ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.03)"
        ctx.fill()
      }
      raf = requestAnimationFrame(draw)
    }
    draw()
    const onResize = () => {
      w = canvas.width = canvas.offsetWidth * 2
      h = canvas.height = canvas.offsetHeight * 2
      ctx.scale(2, 2)
      w /= 2; h /= 2
    }
    window.addEventListener("resize", onResize)
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", onResize) }
  }, [])

  return (
    <div className={`relative overflow-hidden ${className}`}>
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" style={{ width: "100%", height: "100%" }} />
      <div className="relative">{children}</div>
    </div>
  )
}

export function SparklesBackground({ className = "" }: { className?: string }) {
  return (
    <div className={`absolute inset-0 overflow-hidden ${className}`}>
      <div className="absolute inset-0 bg-gradient-to-br from-teal-900 via-cyan-900 to-slate-900" />
      <div className="absolute inset-0 opacity-30" style={{
        backgroundImage: `radial-gradient(white 1px, transparent 1px)`,
        backgroundSize: "24px 24px",
      }} />
    </div>
  )
}
