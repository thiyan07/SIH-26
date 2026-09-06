import { useState, useRef } from 'react'

export function VoiceInput({ onResult, lang = 'en' }: { onResult: (text: string) => void; lang?: string }) {
  const [listening, setListening] = useState(false)
  const [supported, setSupported] = useState(() => typeof window !== 'undefined' && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window))
  const recRef = useRef<any>(null)

  const toggle = () => {
    if (listening) {
      recRef.current?.stop()
      setListening(false)
      return
    }
    const SR: any = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    if (!SR) {
      setSupported(false)
      return
    }
    const rec = new SR()
    recRef.current = rec
    rec.lang = lang === 'ta' ? 'ta-IN' : lang === 'hi' ? 'hi-IN' : 'en-IN'
    rec.interimResults = false
    rec.continuous = false
    rec.onstart = () => setListening(true)
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    rec.onresult = (e: any) => {
      const text = e.results[0]?.[0]?.transcript || ''
      if (text) onResult(text)
    }
    rec.start()
  }

  if (!supported) return null
  return (
    <button
      type="button"
      onClick={toggle}
      className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold transition ${listening ? 'bg-red-600 text-white animate-pulse' : 'bg-slate-900 text-white hover:bg-slate-800'}`}
      title={listening ? 'Listening... tap to stop' : 'Tap to speak (Tamil/Hindi/English)'}
    >
      <span>{listening ? '●' : '🎙️'}</span> {listening ? 'Listening…' : 'Speak'}
    </button>
  )
}
