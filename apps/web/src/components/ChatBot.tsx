import { useState, useRef, useEffect } from 'react'
import { useAnalysis } from '../lib/analysisStore'
import { api } from '../lib/api'
import { tr, type Language } from '../lib/i18n'

interface Msg { role: 'user' | 'assistant'; text: string }

const QUICK_QUESTIONS: Record<Language, string[]> = {
  en: ['Is this business profitable?', 'What is the loan EMI?', 'Who are my competitors?'],
  ta: ['இந்த தொழில் லாபகரமா?', 'கடன் EMI எவ்வளவு?', 'போட்டியாளர்கள் யார்?'],
  hi: ['क्या यह व्यवसाय लाभदायक है?', 'लोन EMI कितनी है?', 'मेरे प्रतियोगी कौन हैं?'],
}

export function ChatBot() {
  const { result, lang } = useAnalysis()
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState<Msg[]>([{ role: 'assistant', text: tr('chatWelcome', lang as Language) || 'Hi! Ask me about your business feasibility.' }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(()=>{ bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, open])

  const send = async (text: string) => {
    if (!text.trim()) return
    setMsgs(m=>[...m, { role:'user', text }])
    setInput('')
    setLoading(true)
    try {
      const evidence = result || {}
      const res = await api.post<{ content: string; role?: string }>('/ai/advice', { evidence, language: lang })
      const reply = (res as any).content || (res as any).role || 'Based on your analysis, I can help with profit, loan and competitors.'
      setMsgs(m=>[...m, { role:'assistant', text: reply.slice(0,800) }])
    } catch {
      // deterministic fallback
      const fallback = lang==='ta' ? 'உங்கள் தரவின் அடிப்படையில், இந்த தொழில் பற்றி விரிவாக விளக்க முடியும்.' : lang==='hi' ? 'आपके डेटा के आधार पर मैं लाभ, लोन और प्रतिस्पर्धा समझा सकता हूँ.' : `Based on your data: Score ${(result as any)?.opportunity_score?.overall_score ?? '—'}/100. Ask about profit, loan or competitors.`
      setMsgs(m=>[...m, { role:'assistant', text: fallback }])
    } finally { setLoading(false) }
  }

  return (
    <>
      <button
        data-testid="chat-toggle"
        onClick={()=>setOpen(v=>!v)}
        className="fixed bottom-4 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-brand-600 to-cyan-600 text-white shadow-lg hover:scale-105"
        aria-label="Chat"
      >
        {open ? '✕' : '💬'}
      </button>
      {open && (
        <div data-testid="chat-window" className="fixed bottom-20 right-4 z-40 flex h-[420px] w-[340px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900">
          <div className="bg-gradient-to-r from-brand-600 to-cyan-600 px-4 py-3 text-sm font-bold text-white">
            GramBiz Assistant • {lang.toUpperCase()}
          </div>
          <div className="flex-1 overflow-auto p-3 space-y-2">
            {msgs.map((m,i)=>(
              <div key={i} className={`max-w-[80%] rounded-2xl px-3 py-2 text-xs ${m.role==='user' ? 'ml-auto bg-brand-600 text-white' : 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100'}`}>
                {m.text}
              </div>
            ))}
            {loading && <div className="text-xs text-slate-500">Typing…</div>}
            <div ref={bottomRef} />
          </div>
          <div className="flex flex-wrap gap-1 border-t p-2">
            {(QUICK_QUESTIONS[lang as Language] || QUICK_QUESTIONS.en).map(q=>(
              <button key={q} onClick={()=>send(q)} className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-200">{q}</button>
            ))}
          </div>
          <div className="flex gap-2 border-t p-2">
            <input
              data-testid="chat-input"
              value={input}
              onChange={e=>setInput(e.target.value)}
              onKeyDown={e=>e.key==='Enter'&&send(input)}
              placeholder={tr('chatPlaceholder', lang as Language) || 'Ask in Tamil, Hindi or English...'}
              className="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-xs outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-white"
            />
            <button data-testid="chat-send" onClick={()=>send(input)} disabled={loading || !input.trim()} className="rounded-xl bg-brand-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">Send</button>
          </div>
        </div>
      )}
    </>
  )
}
