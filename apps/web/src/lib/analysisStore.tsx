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
      if (saved) {
        const parsed = JSON.parse(saved) as any
        // Guard against stale / incompatible shapes from older builds
        if (parsed && parsed.location && parsed.opportunity_score && parsed.financial_plan) {
          setResult(parsed as AnalysisResult)
        } else {
          // Old shape — clear to avoid render crashes
          localStorage.removeItem(KEY)
          console.warn('[analysisStore] cleared stale cached analysis')
        }
      }
    } catch (e) {
      localStorage.removeItem(KEY)
      console.warn('[analysisStore] failed to parse cached analysis', e)
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
