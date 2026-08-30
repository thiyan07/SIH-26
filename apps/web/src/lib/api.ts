// Typed API client for the GramBiz backend.
// Backend serves routes at root (/analysis, /schemes, ...). In dev, Vite
// proxies these to the FastAPI server (see vite.config.ts). Override the
// origin with VITE_API_URL when the API is hosted elsewhere (e.g. nginx).
const API_URL = (import.meta.env.VITE_API_URL as string) || ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
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
}
