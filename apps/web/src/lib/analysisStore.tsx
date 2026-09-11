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
  selectedSchemeCode: string | null
  setSelectedSchemeCode: (code: string | null) => void
  selectedSchemeName: string | null
}

const Ctx = createContext<Store | null>(null)
const KEY = 'grambiz.last.analysis'
const KEY_SCHEME = 'grambiz.selectedScheme'

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Language>('en')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [form, setForm] = useState<Record<string, unknown> | null>(null)
  const [selectedSchemeCode, setSelectedSchemeCodeRaw] = useState<string | null>(null)

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
      const savedScheme = localStorage.getItem(KEY_SCHEME)
      if (savedScheme) setSelectedSchemeCodeRaw(savedScheme)
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

  const setSelectedSchemeCode = (code: string | null) => {
    setSelectedSchemeCodeRaw(code)
    try {
      if (code) localStorage.setItem(KEY_SCHEME, code)
      else localStorage.removeItem(KEY_SCHEME)
    } catch { /* ignore */ }
  }

  const selectedSchemeName = (() => {
    if (!selectedSchemeCode || !result) return null
    // Try to find name in result's financial_plan or alternatives
    const fpName = (result as any)?.financial_plan?.scheme_name
    const fpCode = (result as any)?.financial_plan?.scheme_code
    if (fpCode === selectedSchemeCode) return fpName || selectedSchemeCode
    return selectedSchemeCode
  })()

  return <Ctx.Provider value={{ lang, setLang, result, setResult: persist, form, setForm, selectedSchemeCode, setSelectedSchemeCode, selectedSchemeName }}>{children}</Ctx.Provider>
}

export function useAnalysis(): Store {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAnalysis must be used within AnalysisProvider')
  return ctx
}
