// Typed API client for the GramBiz backend.
// Backend serves routes at root (/analysis, /schemes, ...). In dev, Vite
// proxies these to the FastAPI server (see vite.config.ts). Override the
// origin with VITE_API_URL when the API is hosted elsewhere (e.g. nginx).
const API_URL = (import.meta.env.VITE_API_URL as string) || ''

const TOKEN_KEY = 'grambiz.access_token'
const REFRESH_KEY = 'grambiz.refresh_token'

function getAuthHeader(): Record<string, string> {
  try {
    const t = localStorage.getItem(TOKEN_KEY)
    if (t) return { Authorization: `Bearer ${t}` }
  } catch { /* ignore */ }
  return {}
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...getAuthHeader(), ...(options?.headers as Record<string, string> || {}) }
  let res = await fetch(`${API_URL}${path}`, { ...options, headers })
  // Transparent refresh on 401 for authenticated endpoints (except auth itself)
  if (res.status === 401 && !path.startsWith('/auth/') && localStorage.getItem(REFRESH_KEY)) {
    try {
      const rt = localStorage.getItem(REFRESH_KEY)!
      const r = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      })
      if (r.ok) {
        const data: any = await r.json()
        try {
          localStorage.setItem(TOKEN_KEY, data.access_token)
          localStorage.setItem(REFRESH_KEY, data.refresh_token)
        } catch { /* ignore */ }
        // retry original request with new token
        const retryHeaders: Record<string, string> = { 'Content-Type': 'application/json', Authorization: `Bearer ${data.access_token}`, ...(options?.headers as Record<string, string> || {}) }
        res = await fetch(`${API_URL}${path}`, { ...options, headers: retryHeaders })
      }
    } catch { /* refresh failed, fall through to error */ }
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body?.detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : 'Request failed')
  }
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  setTokens: (access: string, refresh: string) => {
    try {
      localStorage.setItem(TOKEN_KEY, access)
      localStorage.setItem(REFRESH_KEY, refresh)
    } catch { /* ignore */ }
  },
  clearTokens: () => {
    try {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_KEY)
    } catch { /* ignore */ }
  },
  getAccessToken: () => {
    try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
  },
}
