import { Link } from 'react-router-dom'
import { tr, type Language } from '../lib/i18n'
import { useAnalysis } from '../lib/analysisStore'

export function Landing() {
  const { lang } = useAnalysis()
  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-b from-brand-50 via-white to-white">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">G</span>
          <span className="text-lg font-bold text-gray-900">GramBiz AI</span>
        </div>
        <LangSwitcher lang={lang} />
      </header>
      <main className="mx-auto flex w-full max-w-4xl flex-col items-center px-6 text-center">
        <h1 className="mt-10 text-4xl font-extrabold leading-tight text-gray-900 sm:text-5xl">
          Know Your Market Before You{' '}
          <span className="text-brand-600">Take the Loan.</span>
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-gray-600">
          AI-powered hyper-local business feasibility and financial planning for rural entrepreneurs.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/analyze"
            className="rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow hover:bg-brand-700"
          >
            {tr('analyzeBusiness', lang)}
          </Link>
          <Link
            to="/dashboard"
            className="rounded-lg border border-gray-300 bg-white px-6 py-3 text-sm font-semibold text-gray-700 hover:bg-gray-50"
          >
            {tr('exploreDemo', lang)}
          </Link>
        </div>
        <div className="mt-10 w-full max-w-3xl rounded-2xl border border-gray-200 bg-white p-6 text-left shadow-sm">
          <p className="text-sm text-gray-500">
            <strong className="text-gray-700">How it works</strong> — Tell us where you live, your available capital, and
            the business you want to start. GramBiz AI:
          </p>
          <ol className="mt-3 space-y-1.5 text-sm text-gray-600">
            <li>1. Maps your village and finds nearby businesses (© OpenStreetMap).</li>
            <li>2. Computes local demand, competition and accessibility indicators.</li>
            <li>3. Calculates a transparent opportunity score with confidence level.</li>
            <li>4. Words a financial plan: project cost, loan, scheme routing, EMI.</li>
            <li>5. Simulates profit and repayment health with what-if scenarios.</li>
            <li>6. Generates a GO / MODIFY / AVOID recommendation grounded in evidence.</li>
          </ol>
        </div>
        <p className="mt-8 max-w-2xl text-xs text-gray-400">
          Business opportunity scores are analytical estimates based on available data and are not guarantees of business
          success. Loan and scheme guidance is informational and must be verified with the relevant agency.
        </p>
      </main>
    </div>
  )
}

function LangSwitcher({ lang }: { lang: Language }) {
  const { setLang } = useAnalysis()
  return (
    <select
      value={lang}
      onChange={(e) => setLang(e.target.value as Language)}
      className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700"
    >
      <option value="en">English</option>
      <option value="ta">தமிழ்</option>
      <option value="hi">हिंदी</option>
    </select>
  )
}
