import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'

export interface AuthUser {
  id: string
  email: string
  display_name: string | null
  language: string
  is_active: boolean
  is_verified: boolean
}

interface AuthStore {
  user: AuthUser | null
  isAuthenticated: boolean
  isHydrated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, display_name?: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  setUser: (u: AuthUser | null) => void
}

const Ctx = createContext<AuthStore | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isHydrated, setIsHydrated] = useState(false)

  useEffect(() => {
    const token = (() => {
      try { return localStorage.getItem('grambiz.access_token') } catch { return null }
    })()
    if (!token) { setIsHydrated(true); return }
    api.get<AuthUser>('/auth/me').then(setUser).catch(() => {
      // token invalid — clear
      try { localStorage.removeItem('grambiz.access_token'); localStorage.removeItem('grambiz.refresh_token') } catch {}
    }).finally(() => setIsHydrated(true))
  }, [])

  const login = async (email: string, password: string) => {
    const res: any = await api.post('/auth/login', { email, password })
    api.setTokens(res.access_token, res.refresh_token)
    const me = await api.get<AuthUser>('/auth/me')
    setUser(me)
  }

  const register = async (email: string, password: string, display_name?: string) => {
    await api.post('/auth/register', { email, password, display_name })
    // auto-login after register
    await login(email, password)
  }

  const logout = async () => {
    try {
      const rt = (() => { try { return localStorage.getItem('grambiz.refresh_token') } catch { return null } })()
      if (rt) await api.post('/auth/logout', { refresh_token: rt })
    } catch { /* ignore */ }
    api.clearTokens()
    setUser(null)
  }

  const refresh = async () => {
    const rt = (() => { try { return localStorage.getItem('grambiz.refresh_token') } catch { return null } })()
    if (!rt) return
    const res: any = await api.post('/auth/refresh', { refresh_token: rt })
    api.setTokens(res.access_token, res.refresh_token)
    const me = await api.get<AuthUser>('/auth/me')
    setUser(me)
  }

  return <Ctx.Provider value={{ user, isAuthenticated: !!user, isHydrated, login, register, logout, refresh, setUser }}>{children}</Ctx.Provider>
}

export function useAuth(): AuthStore {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
