import { useEffect, useState } from 'react'

export function OfflineIndicator() {
  const [online, setOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true)
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  if (online) return null
  return (
    <div data-testid="offline-indicator" className="fixed top-[60px] left-0 right-0 z-40 bg-amber-500 py-1 text-center text-xs font-semibold text-white">
      ⚠️ You are offline — some data may be cached
    </div>
  )
}

export function PWAInstallPrompt() {
  const [deferred, setDeferred] = useState<any>(null)
  const [dismissed, setDismissed] = useState(false)
  useEffect(() => {
    const handler = (e: any) => {
      e.preventDefault()
      setDeferred(e)
    }
    window.addEventListener('beforeinstallprompt', handler)
    return () => window.removeEventListener('beforeinstallprompt', handler)
  }, [])
  if (!deferred || dismissed) return null
  return (
    <div data-testid="pwa-install" className="fixed bottom-20 right-4 z-40 flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl dark:border-slate-700 dark:bg-slate-800">
      <div className="text-sm font-semibold text-slate-900 dark:text-white">Install GramBiz AI</div>
      <button
        onClick={async () => {
          deferred.prompt()
          await deferred.userChoice
          setDeferred(null)
        }}
        className="rounded-xl bg-brand-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-brand-700"
      >
        Install
      </button>
      <button onClick={() => setDismissed(true)} className="rounded-lg px-2 py-1 text-xs text-slate-500">
        ✕
      </button>
    </div>
  )
}
