import { Link } from 'react-router-dom'
import { tr, type Language } from '../lib/i18n'
import { useAnalysis } from '../lib/analysisStore'
import { lazy, Suspense } from 'react'
import { ErrorBoundary } from '../components/ErrorBoundary'
const Globe = lazy(() => import('../components/three/Globe').then(m => ({ default: m.Globe })))

const FEATURES = [
  { icon: '📍', title: 'Hyper-local mapping', desc: 'OSM-cached businesses within 10 km of your pin — no invented data.' },
  { icon: '📊', title: 'Opportunity score', desc: 'Demand · Competition · Accessibility · Finance · Risk, with confidence.' },
  { icon: '💳', title: 'Financial structuring', desc: 'Project cost → own capital → loan → EMI & repayment health.' },
  { icon: '🏛️', title: 'Scheme routing', desc: '24 govt schemes matched to your project cost & eligibility.' },
  { icon: '🌦️', title: 'Climate & seasonality', desc: 'Weather evidence + seasonal demand so you stock the right month.' },
  { icon: '🗣️', title: 'Multilingual advisory', desc: 'Type in English, Tamil or Hindi — AI pre-fills & explains.' },
]

const STEPS = [
  { n: '01', t: 'Pick your village & drop the exact shop pin' },
  { n: '02', t: 'GramBiz maps demand, competitors & access' },
  { n: '03', t: 'Get a transparent GO / MODIFY / AVOID score' },
  { n: '04', t: 'See your loan, EMI & scheme in plain language' },
]

export function Landing() {
  const { lang } = useAnalysis()
  return (
    <div className="min-h-screen bg-slate-950">
      {/* top bar */}
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white font-extrabold text-slate-900">G</span>
          <span className="text-sm font-extrabold tracking-tight text-white">GramBiz AI</span>
          <span className="hidden rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold tracking-widest text-white/70 ring-1 ring-white/10 sm:inline">SIH 26091</span>
        </div>
        <LangSwitcher lang={lang} />
      </header>

      {/* HERO */}
      <section className="relative overflow-hidden px-6">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-600/20 via-cyan-600/10 to-transparent" />
        <div className="absolute -top-32 left-1/2 h-[700px] w-[1200px] -translate-x-1/2 rounded-full bg-gradient-to-r from-brand-500/15 via-cyan-500/10 to-blue-500/10 blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl gap-8 py-10 lg:grid-cols-[1.15fr_0.85fr] lg:py-14">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-white/80 backdrop-blur">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" /> Live • Tamil Nadu demo ready
            </div>
            <h1 className="mt-4 text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-[52px]">
              {tr('landingHero1', lang)} <span className="bg-gradient-to-r from-amber-300 to-yellow-100 bg-clip-text text-transparent">{tr('landingHero2', lang)}</span>
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-white/70">{tr('landingTagline', lang)}</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/analyze" className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-bold text-slate-900 shadow-lg hover:bg-slate-100"> {tr('analyzeBusiness', lang)} <span>→</span></Link>
              <Link to="/dashboard" className="inline-flex items-center rounded-xl border border-white/15 bg-white/10 px-6 py-3 text-sm font-semibold text-white backdrop-blur hover:bg-white/15">{tr('exploreDemo', lang)}</Link>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-white/50">
              <span className="rounded-full bg-white/10 px-2.5 py-1">295 villages</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1">5,012 businesses</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1">24 schemes</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1">3 languages</span>
            </div>
            {/* steps */}
            <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {STEPS.map(s=>(
                <div key={s.n} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 backdrop-blur">
                  <div className="text-[11px] font-bold tracking-widest text-white/40">{s.n}</div>
                  <div className="mt-1 text-xs font-medium leading-snug text-white/90">{s.t}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative">
            <div className="overflow-hidden rounded-[28px] border border-white/10 bg-white/5 p-3 shadow-2xl backdrop-blur">
              <ErrorBoundary fallback={<div className="flex h-[380px] items-center justify-center rounded-2xl bg-white/5 p-6 text-center text-xs text-white/60">3D globe unavailable — continue to Analyze</div>}>
                <Suspense fallback={<div className="h-[380px] animate-pulse rounded-2xl bg-white/5" />}>
                  <Globe className="h-[380px] rounded-2xl" businesses={[{ lat: 11.34, lon: 77.72 }, { lat: 11.28, lon: 77.58 }, { lat: 11.5, lon: 77.43 }, { lat: 11.3, lon: 77.9 }]} />
                </Suspense>
              </ErrorBoundary>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-white px-2 py-2.5"><div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Coverage</div><div className="text-sm font-extrabold text-slate-900">10 km</div></div>
                <div className="rounded-xl bg-white px-2 py-2.5"><div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Confidence</div><div className="text-sm font-extrabold text-emerald-600">High</div></div>
                <div className="rounded-xl bg-white px-2 py-2.5"><div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Scheme</div><div className="text-sm font-extrabold text-slate-900">Auto</div></div>
              </div>
            </div>
            <div className="pointer-events-none absolute -bottom-4 -right-4 -z-10 h-40 w-40 rounded-full bg-brand-500/20 blur-2xl" />
          </div>
        </div>
      </section>

      {/* FEATURE GRID */}
      <section className="bg-white">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h2 className="text-lg font-extrabold tracking-tight text-slate-900">Everything aligned. Nothing invented.</h2>
              <p className="mt-1 max-w-2xl text-sm text-slate-500">Deterministic engines compute every number. AI only explains. Historical baselines are labelled, never presented as current.</p>
            </div>
            <Link to="/analyze" className="hidden rounded-xl bg-slate-900 px-4 py-2 text-xs font-bold text-white sm:inline">Start analysis →</Link>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(f=>(
              <div key={f.title} className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-card">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 text-lg ring-1 ring-slate-200 group-hover:bg-brand-50">{f.icon}</div>
                <div className="mt-3 text-sm font-bold text-slate-900">{f.title}</div>
                <div className="mt-1 text-xs leading-relaxed text-slate-500">{f.desc}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 lg:col-span-2">
              <div className="text-xs font-bold uppercase tracking-widest text-slate-400">How it works</div>
              <p className="mt-2 text-sm text-slate-600"><strong className="text-slate-900">{tr('howItWorks', lang)}</strong> — {tr('howItWorksIntro', lang)}</p>
              <ol className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                <li className="rounded-xl bg-white p-3 ring-1 ring-slate-200">1. {tr('howStep1', lang)}</li>
                <li className="rounded-xl bg-white p-3 ring-1 ring-slate-200">2. {tr('howStep2', lang)}</li>
                <li className="rounded-xl bg-white p-3 ring-1 ring-slate-200">3. {tr('howStep3', lang)}</li>
                <li className="rounded-xl bg-white p-3 ring-1 ring-slate-200">4. {tr('howStep4', lang)}</li>
                <li className="rounded-xl bg-white p-3 ring-1 ring-slate-200">5. {tr('howStep5', lang)}</li>
                <li className="rounded-xl bg-white p-3 ring-1 ring-slate-200">6. {tr('howStep6', lang)}</li>
              </ol>
            </div>
            <div className="rounded-2xl bg-slate-900 p-6 text-white">
              <div className="text-xs font-bold uppercase tracking-widest text-white/50">Built for SIH 26091</div>
              <div className="mt-2 text-lg font-bold leading-tight">Know your market before you take the loan.</div>
              <p className="mt-2 text-xs leading-relaxed text-white/60">Evidence-based feasibility for rural micro-entrepreneurs. Scores, prices & loan guidance are estimates — verified with the agency before you commit.</p>
              <div className="mt-4 flex gap-2">
                <Link to="/analyze" className="rounded-xl bg-white px-4 py-2 text-xs font-bold text-slate-900">Analyze now</Link>
                <Link to="/data-sources" className="rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-xs font-semibold text-white">Provenance</Link>
              </div>
            </div>
          </div>
          <p className="mt-6 text-center text-xs text-slate-400">{tr('landingDisclaimer', lang)}</p>
        </div>
      </section>
    </div>
  )
}
function LangSwitcher({ lang }: { lang: Language }) {
  const { setLang } = useAnalysis()
  return (
    <select value={lang} onChange={(e) => setLang(e.target.value as Language)} className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-xs font-semibold text-white backdrop-blur">
      <option value="en" className="text-slate-900">English</option><option value="ta" className="text-slate-900">தமிழ்</option><option value="hi" className="text-slate-900">हिंदी</option>
    </select>
  )
}
