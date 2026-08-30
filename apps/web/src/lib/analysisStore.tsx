import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { AnalysisResult } from '../types'

type Language = 'en' | 'ta' | 'hi'

interface Store {
  lang: Language
  setLang: (l: Language) => void
  result: AnalysisResult | null
  setResult: (r: AnalysisResult) => void
  form: Record<string, unknown> | null
  setForm: (f: Record<string, unknown>) => void
}

const Ctx = createContext<Store | null>(null)
const KEY = 'grambiz.last.analysis'

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Language>('en')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [form, setForm] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY)
      if (saved) setResult(JSON.parse(saved) as AnalysisResult)
    } catch {
      /* ignore */
    }
  }, [])

  const persist = (r: AnalysisResult) => {
    setResult(r)
    try {
      localStorage.setItem(KEY, JSON.stringify(r))
    } catch {
      /* ignore */
    }
  }

  return <Ctx.Provider value={{ lang, setLang, result, setResult: persist, form, setForm }}>{children}</Ctx.Provider>
}

export function useAnalysis(): Store {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAnalysis must be used within AnalysisProvider')
  return ctx
}
