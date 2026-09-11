import { useState, useRef } from 'react'

export function VoiceInput({ onResult, lang = 'en' }: { onResult: (text: string) => void; lang?: string }) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const supported = typeof window !== 'undefined' && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)
  const recRef = useRef<any>(null)

  const toggle = () => {
    setError(null)
    if (listening) {
      try { recRef.current?.stop() } catch { /* ignore */ }
      setListening(false)
      return
    }
    const SR: any = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    if (!SR) {
      setError('Speech recognition not supported in this browser. Try Chrome on desktop/mobile.')
      return
    }
    try {
      const rec = new SR()
      recRef.current = rec
      rec.lang = lang === 'ta' ? 'ta-IN' : lang === 'hi' ? 'hi-IN' : 'en-IN'
      rec.interimResults = false
      rec.continuous = false
      rec.maxAlternatives = 1
      rec.onstart = () => { setListening(true); setError(null) }
      rec.onend = () => setListening(false)
      rec.onerror = (e: any) => {
        setListening(false)
        const code = e?.error || 'unknown'
        if (code === 'not-allowed' || code === 'permission-denied') setError('Microphone permission denied. Allow access and try again.')
        else if (code === 'no-speech') setError('No speech detected. Try again.')
        else if (code === 'audio-capture') setError('No microphone found.')
        else if (code === 'network') setError('Network error during recognition.')
        else setError(`Recognition error: ${code}`)
      }
      rec.onresult = (e: any) => {
        const text = e.results?.[0]?.[0]?.transcript || ''
        if (text) onResult(text)
        else setError('Could not transcribe. Please try again.')
      }
      rec.start()
    } catch (err: any) {
      setError(err?.message || 'Could not start microphone.')
      setListening(false)
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        disabled={!supported}
        className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition ${
          !supported
            ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
            : listening
              ? 'bg-red-600 text-white animate-pulse'
              : 'bg-slate-900 text-white hover:bg-slate-800'
        }`}
        title={
          !supported
            ? 'Speech recognition not supported – try Chrome'
            : listening
              ? 'Listening... tap to stop'
              : 'Tap to speak (Tamil/Hindi/English)'
        }
      >
        <span>{listening ? '●' : '🎙️'}</span> {listening ? 'Listening…' : 'Speak'}
      </button>
      {error && <span className="max-w-[220px] text-[11px] text-red-600">{error}</span>}
      {!supported && !error && (
        <span className="text-[11px] text-slate-500">Voice input requires Chrome</span>
      )}
    </span>
  )
}
