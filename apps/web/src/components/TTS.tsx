import { useState } from 'react'
import { useAnalysis } from '../lib/analysisStore'

export function TTSButton({ text, lang }: { text: string; lang?: string }) {
  const { lang: storeLang } = useAnalysis()
  const l = lang || storeLang
  const [speaking, setSpeaking] = useState(false)
  const speak = () => {
    if (!('speechSynthesis' in window)) { alert('TTS not supported'); return }
    if (speaking) { speechSynthesis.cancel(); setSpeaking(false); return }
    const utter = new SpeechSynthesisUtterance(text.slice(0, 900))
    utter.lang = l==='ta'?'ta-IN':l==='hi'?'hi-IN':'en-IN'
    utter.rate = 0.9
    utter.onend = ()=> setSpeaking(false)
    utter.onerror = ()=> setSpeaking(false)
    setSpeaking(true)
    speechSynthesis.cancel()
    speechSynthesis.speak(utter)
  }
  return (
    <button
      data-testid="tts-button"
      onClick={speak}
      className={`rounded-xl px-3 py-1.5 text-xs font-semibold ${speaking ? 'bg-red-600 text-white' : 'bg-slate-900 text-white hover:bg-slate-800'}`}
      title="Listen in Tamil/Hindi/English"
    >
      {speaking ? '⏹ Stop' : '🔊 Listen'}
    </button>
  )
}
