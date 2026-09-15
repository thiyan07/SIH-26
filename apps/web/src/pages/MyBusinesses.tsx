import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Card, CardHeader } from '../components/ui'
import { useAuth } from '../lib/auth'

interface Biz {
  id: string
  name: string
  category_code: string | null
  latitude: number
  longitude: number
  address: string | null
  created_at: string | null
}

export function MyBusinesses() {
  const { isAuthenticated } = useAuth()
  const [items, setItems] = useState<Biz[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated) { setLoading(false); return }
    api.get<Biz[]>('/user/businesses').then(setItems).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [isAuthenticated])

  if (!isAuthenticated) {
    return (
      <div className="mx-auto max-w-md py-20 text-center">
        <p className="text-sm text-gray-500">Please log in to see your businesses.</p>
        <Link to="/login" className="mt-4 inline-block rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white">Log in</Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="My Businesses" subtitle={`${items.length} business${items.length !== 1 ? 'es' : ''} — private to you`} />
        {loading ? <p className="p-4 text-sm text-gray-500">Loading…</p> : error ? <p className="p-4 text-sm text-red-600">{error}</p> : items.length === 0 ? (
          <p className="p-4 text-sm text-gray-500">No businesses yet. Create one from your Pre-Loan analysis via “Save Business”.</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {items.map(b => (
              <li key={b.id} className="flex items-center justify-between p-4">
                <div>
                  <div className="font-semibold text-gray-900">{b.name}</div>
                  <div className="text-xs text-gray-500">{b.category_code || 'other'} · {b.address || `${b.latitude.toFixed(3)}, ${b.longitude.toFixed(3)}`}</div>
                </div>
                <span className="text-xs text-gray-400">{b.created_at ? new Date(b.created_at).toLocaleDateString() : ''}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Link to="/analyze" className="text-sm text-brand-600 underline">← New analysis</Link>
    </div>
  )
}
