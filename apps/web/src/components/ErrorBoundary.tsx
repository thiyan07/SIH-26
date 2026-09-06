import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, info: unknown) => void
}

interface State {
  error: Error | null
}

/**
 * Catches render/runtime errors from a subtree so a single failing section
 * (e.g. the MapLibre map) doesn't unmount and blank the whole page.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: unknown) {
    this.props.onError?.(error, info)
  }

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback
      // In dev, surface the actual error to help debugging via playwright / user
      const msg = this.state.error.message || String(this.state.error)
      const stack = (this.state.error.stack || '').split('\n').slice(0, 6).join('\n')
      console.error('[ErrorBoundary]', this.state.error)
      return (
        <div className="flex min-h-[240px] flex-col items-center justify-center rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
          <p className="text-sm font-bold text-amber-800">This section couldn&apos;t load.</p>
          <p className="mt-1 max-w-xl break-words text-xs text-amber-700">
            Try refreshing. If it persists, clear site data (localStorage `grambiz.last.analysis`) or reload demo from Analyze.
          </p>
          <details className="mt-3 w-full max-w-xl rounded-lg bg-white p-3 text-left shadow-sm">
            <summary className="cursor-pointer text-xs font-semibold text-amber-800">Error details (for debugging)</summary>
            <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-relaxed text-slate-700">{msg}</pre>
            <pre className="mt-2 whitespace-pre-wrap break-words text-[10px] leading-relaxed text-slate-500">{stack}</pre>
            <button
              onClick={() => { localStorage.removeItem('grambiz.last.analysis'); location.reload() }}
              className="mt-3 rounded-lg bg-amber-600 px-3 py-1 text-xs font-semibold text-white"
            >
              Clear saved analysis & reload
            </button>
          </details>
        </div>
      )
    }
    return this.props.children
  }
}
