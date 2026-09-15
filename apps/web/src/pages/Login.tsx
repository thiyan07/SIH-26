import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAnalysis } from '../lib/analysisStore'
import { tr } from '../lib/i18n'
import { useAuth } from '../lib/auth'
import { Card, CardHeader } from '../components/ui'

export function Login() {
  const { lang } = useAnalysis()
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as any
  const next = location.state?.next || '/dashboard'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email.trim(), password)
      navigate(next, { replace: true })
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="mx-auto max-w-md py-10">
      <Card>
        <CardHeader title={tr('loginTitle', lang)} subtitle={tr('loginSubtitle', lang)} />
        <form onSubmit={submit} className="mt-4 space-y-4">
          {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>}
          <div>
            <label className="text-xs font-semibold text-gray-700">{tr('loginEmailLabel', lang)}</label>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" placeholder="you@example.com" />
          </div>
          <div>
            <label className="text-xs font-semibold text-gray-700">{tr('loginPasswordLabel', lang)}</label>
            <input type="password" required value={password} onChange={e => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" placeholder="••••••••" />
          </div>
          <button type="submit" disabled={loading} className="w-full rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-brand-700 disabled:opacity-50">
            {loading ? tr('loginSigning', lang) : tr('loginBtn', lang)}
          </button>
          <p className="text-center text-xs text-gray-500">
            {tr('loginNoAccount', lang)} <Link to="/register" state={{ next }} className="font-semibold text-brand-600 underline">{tr('loginRegisterLink', lang)}</Link>
          </p>
          <p className="text-center text-xs text-gray-400">{tr('loginStillExplore', lang)} <Link to="/analyze" className="underline">{tr('loginExplorePreloan', lang)}</Link>.</p>
        </form>
      </Card>
    </div>
  )
}
