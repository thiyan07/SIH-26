import { Link } from 'react-router-dom'
import { tr, type Language } from '../lib/i18n'
import { useAnalysis } from '../lib/analysisStore'
import { lazy, Suspense } from 'react'
import { ErrorBoundary } from '../components/ErrorBoundary'
const Globe = lazy(() => import('../components/three/Globe'))



export function Landing() {
  const { lang } = useAnalysis()
  const features = [
    { icon: '📍', title: tr('featureHyperLocalTitle', lang), desc: tr('featureHyperLocalDesc', lang) },
    { icon: '📊', title: tr('featureOpportunityTitle', lang), desc: tr('featureOpportunityDesc', lang) },
    { icon: '💳', title: tr('featureFinancialTitle', lang), desc: tr('featureFinancialDesc', lang) },
    { icon: '🏛️', title: tr('featureSchemeTitle', lang), desc: tr('featureSchemeDesc', lang) },
    { icon: '🌦️', title: tr('featureClimateTitle', lang), desc: tr('featureClimateDesc', lang) },
    { icon: '🗣️', title: tr('featureMultilingualTitle', lang), desc: tr('featureMultilingualDesc', lang) },
  ]
  const steps = [
    { n: '01', t: tr('step1', lang) },
    { n: '02', t: tr('step2', lang) },
    { n: '03', t: tr('step3', lang) },
    { n: '04', t: tr('step4', lang) },
  ]
  return (
    <div className="min-h-screen bg-slate-950">
      {/* top bar — backdrop-blur was the #1 scroll jank source: now solid, no blur */}
      <header className="sticky top-0 z-20 mx-auto flex w-full max-w-6xl items-center justify-between border-b border-white/5 bg-slate-950 px-6 py-4 [transform:translateZ(0)]">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white font-extrabold text-slate-900 shadow">G</span>
          <span className="text-sm font-extrabold tracking-tight text-white">GramBiz AI</span>
        </div>
        <LangSwitcher lang={lang} />
      </header>

      {/* HERO — grid + large blur were causing compositor overdraw on scroll; keep but lighter */}
      <section className="hero-mesh relative overflow-hidden px-6 [contain:layout_paint]">
        <div className="pointer-events-none absolute -top-32 left-1/2 h-[640px] w-[1100px] -translate-x-1/2 rounded-full bg-gradient-to-r from-brand-500/14 via-cyan-500/10 to-blue-500/10 blur-3xl will-change-transform [transform:translateZ(0)]" />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:56px_56px] opacity-60 [mask-image:radial-gradient(ellipse_70%_60%_at_50%_0%,#000_70%,transparent_110%)]" />
        <div className="relative mx-auto grid max-w-6xl gap-8 py-10 lg:grid-cols-[1.15fr_0.85fr] lg:py-14">
          <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-white/80">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" /> Live • Tamil Nadu demo ready
            </div>
            <h1 className="mt-4 text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-[52px]">
              {tr('landingHero1', lang)} <span className="bg-gradient-to-r from-amber-300 to-yellow-100 bg-clip-text text-transparent">{tr('landingHero2', lang)}</span>
            </h1>
            <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-white/70">{tr('landingTagline', lang)}</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/analyze" className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-bold text-slate-900 shadow-lg hover:bg-slate-100"> {tr('analyzeBusiness', lang)} <span>→</span></Link>
              <Link to="/dashboard" className="inline-flex items-center rounded-xl border border-white/15 bg-white/10 px-6 py-3 text-sm font-semibold text-white hover:bg-white/15">{tr('exploreDemo', lang)}</Link>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-white/50">
              <span className="rounded-full bg-white/10 px-2.5 py-1">295 villages</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1">5,012 businesses</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1">24 schemes</span>
              <span className="rounded-full bg-white/10 px-2.5 py-1">3 languages</span>
            </div>
            {/* steps */}
            <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {steps.map(s=>(
                <div key={s.n} className="rounded-2xl border border-white/10 bg-white/[0.06] p-3 transition hover:bg-white/[0.09] hover:border-white/15">
                  <div className="text-[11px] font-bold tracking-widest text-white/40">{s.n}</div>
                  <div className="mt-1 text-xs font-medium leading-snug text-white/90">{s.t}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative [contain:layout_paint]">
            <div className="overflow-hidden rounded-[28px] border border-white/10 bg-white/[0.06] p-3 shadow-2xl [transform:translateZ(0)]">
              <ErrorBoundary fallback={<div className="flex h-[380px] items-center justify-center rounded-2xl bg-white/5 p-6 text-center text-xs text-white/60">3D globe unavailable — continue to Analyze</div>}>
                <Suspense fallback={<div className="h-[380px] animate-pulse rounded-2xl bg-white/5" />}>
                  <Globe className="h-[380px] rounded-2xl" businesses={[{ lat: 11.34, lon: 77.72 }, { lat: 11.28, lon: 77.58 }, { lat: 11.5, lon: 77.43 }, { lat: 11.3, lon: 77.9 }]} />
                </Suspense>
              </ErrorBoundary>
              <div className="absolute bottom-3 left-3 rounded-lg bg-slate-900/80 px-2.5 py-1 text-[11px] font-bold text-white backdrop-blur">● Tamil Nadu — GramBiz operating region</div>
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
          <div>
            <h2 className="text-lg font-extrabold tracking-tight text-slate-900">Everything aligned. Nothing invented.</h2>
            <p className="mt-1 max-w-2xl text-sm text-slate-500">Deterministic engines compute every number. AI only explains. Historical baselines are labelled, never presented as current.</p>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map(f=>(
              <div key={f.title} className="card-lift group rounded-2xl border border-slate-200 bg-white p-5 shadow-soft hover:border-slate-200">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-teal-50 to-cyan-50 text-lg ring-1 ring-teal-100 group-hover:from-brand-50 group-hover:to-teal-50">{f.icon}</div>
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
              <div className="text-xs font-bold uppercase tracking-widest text-white/50">Enterprise Ready</div>
              <div className="mt-2 text-lg font-bold leading-tight">Know your market before you take the loan.</div>
              <p className="mt-2 text-xs leading-relaxed text-white/60">Evidence-based feasibility for small businesses and growing enterprises. Scores, prices & loan guidance are estimates — verified with the agency before you commit.</p>
              <div className="mt-4">
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
    <select value={lang} onChange={(e) => setLang(e.target.value as Language)} className="rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-xs font-semibold text-white">
      <option value="en" className="text-slate-900">English</option><option value="ta" className="text-slate-900">தமிழ்</option><option value="hi" className="text-slate-900">हिंदी</option>
    </select>
  )
}
