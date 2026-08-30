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
      return (
        <div className="flex min-h-[200px] items-center justify-center rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
          <div>
            <p className="text-sm font-medium text-amber-800">This section couldn&apos;t load.</p>
            <p className="mt-1 text-xs text-amber-700">
              Try refreshing the page. The rest of the app is unaffected.
            </p>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
