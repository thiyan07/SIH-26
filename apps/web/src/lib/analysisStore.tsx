import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { AnalysisResult } from '../types'

type Language = 'en' | 'ta' | 'hi'

interface ApplicantDetails {
  fullName: string
  phone: string
  houseAddress: string
}

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
  // Journey progression
  businessSetupConfirmed: boolean
  setBusinessSetupConfirmed: (v: boolean) => void
  budgetAllocation: Record<string, number> | null
  setBudgetAllocation: (v: Record<string, number> | null) => void
  financeConfirmed: boolean
  setFinanceConfirmed: (v: boolean) => void
  simulatorSkipped: boolean
  setSimulatorSkipped: (v: boolean) => void
  applicantDetails: ApplicantDetails | null
  setApplicantDetails: (v: ApplicantDetails | null) => void
  applicantAge: number | null
  setApplicantAge: (v: number | null) => void
  eligibilityResult: any | null
  setEligibilityResult: (v: any | null) => void
  clearJourney: () => void
  isHydrated: boolean
}

const Ctx = createContext<Store | null>(null)
const KEY = 'grambiz.last.analysis'
const KEY_SCHEME = 'grambiz.selectedScheme'
const KEY_SETUP = 'grambiz.setup.confirmed'
const KEY_BUDGET = 'grambiz.budget.allocation'
const KEY_FINANCE = 'grambiz.finance.confirmed'
const KEY_SIM = 'grambiz.sim.skipped'
const KEY_APPLICANT = 'grambiz.applicant'
const KEY_AGE = 'grambiz.age'
const KEY_ELIG = 'grambiz.eligibility'

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Language>('en')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [form, setForm] = useState<Record<string, unknown> | null>(null)
  const [selectedSchemeCode, setSelectedSchemeCodeRaw] = useState<string | null>(null)
  const [businessSetupConfirmed, setBusinessSetupConfirmedRaw] = useState<boolean>(false)
  const [budgetAllocation, setBudgetAllocationRaw] = useState<Record<string, number> | null>(null)
  const [financeConfirmed, setFinanceConfirmedRaw] = useState<boolean>(false)
  const [simulatorSkipped, setSimulatorSkippedRaw] = useState<boolean>(false)
  const [applicantDetails, setApplicantDetailsRaw] = useState<ApplicantDetails | null>(null)
  const [applicantAge, setApplicantAgeRaw] = useState<number | null>(null)
  const [eligibilityResult, setEligibilityResultRaw] = useState<any | null>(null)

  const [isHydrated, setIsHydrated] = useState(false)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY)
      if (saved) {
        const parsed = JSON.parse(saved) as any
        // Guard against stale / incompatible shapes from older builds
        // Also clear if cached analysis contains old SIH/demo source_document (real data only now)
        const hasOldDemo = parsed?.financial_plan?.source_document?.includes('Problem Statement') || parsed?.financial_plan?.source_document?.includes('26091')
        const hasOldScheme = parsed?.financial_plan?.scheme_name?.includes('Problem Statement')
        if (hasOldDemo || hasOldScheme) {
          localStorage.removeItem(KEY)
          console.warn('[analysisStore] cleared cached analysis with old demo source_document')
        } else if (parsed && parsed.location && parsed.opportunity_score && parsed.financial_plan) {
          setResult(parsed as AnalysisResult)
        } else {
          // Old shape — clear to avoid render crashes
          localStorage.removeItem(KEY)
          console.warn('[analysisStore] cleared stale cached analysis')
        }
      }
      const savedScheme = localStorage.getItem(KEY_SCHEME)
      if (savedScheme) setSelectedSchemeCodeRaw(savedScheme)
      const savedSetup = localStorage.getItem(KEY_SETUP)
      if (savedSetup) setBusinessSetupConfirmedRaw(savedSetup === 'true')
      const savedBudget = localStorage.getItem(KEY_BUDGET)
      if (savedBudget) try { setBudgetAllocationRaw(JSON.parse(savedBudget)) } catch {}
      const savedFinance = localStorage.getItem(KEY_FINANCE)
      if (savedFinance) setFinanceConfirmedRaw(savedFinance === 'true')
      const savedSim = localStorage.getItem(KEY_SIM)
      if (savedSim) setSimulatorSkippedRaw(savedSim === 'true')
      const savedApplicant = localStorage.getItem(KEY_APPLICANT)
      if (savedApplicant) try { setApplicantDetailsRaw(JSON.parse(savedApplicant)) } catch {}
      const savedAge = localStorage.getItem(KEY_AGE)
      if (savedAge) setApplicantAgeRaw(Number(savedAge))
      const savedElig = localStorage.getItem(KEY_ELIG)
      if (savedElig) try { setEligibilityResultRaw(JSON.parse(savedElig)) } catch {}
    } catch (e) {
      localStorage.removeItem(KEY)
      console.warn('[analysisStore] failed to parse cached analysis', e)
    } finally {
      setIsHydrated(true)
    }
  }, [])

  const persist = (r: AnalysisResult) => {
    setResult(r)
    // New analysis cleanly replaces old — clear downstream journey state
    setBusinessSetupConfirmedRaw(false)
    setFinanceConfirmedRaw(false)
    setSimulatorSkippedRaw(false)
    try {
      localStorage.setItem(KEY, JSON.stringify(r))
      localStorage.removeItem(KEY_SETUP)
      localStorage.removeItem(KEY_BUDGET)
      localStorage.removeItem(KEY_FINANCE)
      localStorage.removeItem(KEY_SIM)
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

  const setBusinessSetupConfirmed = (v: boolean) => {
    setBusinessSetupConfirmedRaw(v)
    try { localStorage.setItem(KEY_SETUP, String(v)) } catch {}
  }
  const setBudgetAllocation = (v: Record<string, number> | null) => {
    setBudgetAllocationRaw(v)
    try { if (v) localStorage.setItem(KEY_BUDGET, JSON.stringify(v)); else localStorage.removeItem(KEY_BUDGET) } catch {}
  }
  const setFinanceConfirmed = (v: boolean) => {
    setFinanceConfirmedRaw(v)
    try { localStorage.setItem(KEY_FINANCE, String(v)) } catch {}
  }
  const setSimulatorSkipped = (v: boolean) => {
    setSimulatorSkippedRaw(v)
    try { localStorage.setItem(KEY_SIM, String(v)) } catch {}
  }
  const setApplicantDetails = (v: ApplicantDetails | null) => {
    setApplicantDetailsRaw(v)
    try { if (v) localStorage.setItem(KEY_APPLICANT, JSON.stringify(v)); else localStorage.removeItem(KEY_APPLICANT) } catch {}
  }
  const setApplicantAge = (v: number | null) => {
    setApplicantAgeRaw(v)
    try { if (v != null) localStorage.setItem(KEY_AGE, String(v)); else localStorage.removeItem(KEY_AGE) } catch {}
  }
  const setEligibilityResult = (v: any | null) => {
    setEligibilityResultRaw(v)
    try { if (v) localStorage.setItem(KEY_ELIG, JSON.stringify(v)); else localStorage.removeItem(KEY_ELIG) } catch {}
  }
  const clearJourney = () => {
    setBusinessSetupConfirmedRaw(false)
    setBudgetAllocationRaw(null)
    setFinanceConfirmedRaw(false)
    setSimulatorSkippedRaw(false)
    setApplicantDetailsRaw(null)
    setApplicantAgeRaw(null)
    setEligibilityResultRaw(null)
    try {
      localStorage.removeItem(KEY_SETUP)
      localStorage.removeItem(KEY_BUDGET)
      localStorage.removeItem(KEY_FINANCE)
      localStorage.removeItem(KEY_SIM)
      localStorage.removeItem(KEY_APPLICANT)
      localStorage.removeItem(KEY_AGE)
      localStorage.removeItem(KEY_ELIG)
    } catch {}
  }

  const selectedSchemeName = (() => {
    if (!selectedSchemeCode || !result) return null
    // Try to find name in result's financial_plan or alternatives
    const fpName = (result as any)?.financial_plan?.scheme_name
    const fpCode = (result as any)?.financial_plan?.scheme_code
    if (fpCode === selectedSchemeCode) return fpName || selectedSchemeCode
    return selectedSchemeCode
  })()

  return <Ctx.Provider value={{ lang, setLang, result, setResult: persist, form, setForm, selectedSchemeCode, setSelectedSchemeCode, selectedSchemeName, businessSetupConfirmed, setBusinessSetupConfirmed, budgetAllocation, setBudgetAllocation, financeConfirmed, setFinanceConfirmed, simulatorSkipped, setSimulatorSkipped, applicantDetails, setApplicantDetails, applicantAge, setApplicantAge, eligibilityResult, setEligibilityResult, clearJourney, isHydrated }}>{children}</Ctx.Provider>
}

export function useAnalysis(): Store {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAnalysis must be used within AnalysisProvider')
  return ctx
}
