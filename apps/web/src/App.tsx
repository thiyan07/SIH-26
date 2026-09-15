import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { Layout } from './components/Layout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Landing } from './pages/Landing'
import { Analyze } from './pages/Analyze'
import { Dashboard } from './pages/Dashboard'
import { Market } from './pages/Market'
import { Finance } from './pages/Finance'
import { Simulator } from './pages/Simulator'
import { Report } from './pages/Report'
import { Schemes } from './pages/Schemes'
import { BusinessSetup } from './pages/BusinessSetup'
import { VideoTutorials } from './pages/VideoTutorials'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { MyBusinesses } from './pages/MyBusinesses'
import { MyReports } from './pages/MyReports'
import { PostLoan } from './pages/PostLoan'
import { BusinessProfilePage } from './pages/BusinessProfile'
import { Health } from './pages/Health'
import { MarketGap } from './pages/MarketGap'
import { ForecastPage } from './pages/Forecast'
import { Scenarios } from './pages/Scenarios'
import { useAnalysis } from './lib/analysisStore'
import { useAuth } from './lib/auth'

export default function App() {
  const location = useLocation()
  const isLanding = location.pathname === '/'
  return (
    <Layout hideNav={isLanding}>
      <Routes>
        <Route path="/" element={<Guarded><Landing /></Guarded>} />
        <Route path="/analyze" element={<Guarded><Analyze /></Guarded>} />
        <Route path="/login" element={<Guarded><Login /></Guarded>} />
        <Route path="/register" element={<Guarded><Register /></Guarded>} />
        <Route path="/dashboard" element={<RequireAnalysis><Dashboard /></RequireAnalysis>} />
        <Route path="/business-setup" element={<RequireAnalysis><BusinessSetup /></RequireAnalysis>} />
        <Route path="/market" element={<RequireBusinessSetup><Market /></RequireBusinessSetup>} />
        <Route path="/map" element={<Navigate to="/market" replace />} />
        <Route path="/schemes" element={<RequireBusinessSetup><Schemes /></RequireBusinessSetup>} />
        <Route path="/finance" element={<RequireFinanceEligible><Finance /></RequireFinanceEligible>} />
        <Route path="/simulator" element={<RequireFinance><Simulator /></RequireFinance>} />
        <Route path="/report" element={<RequireReport><Report /></RequireReport>} />
        <Route path="/videos" element={<RequireReport><VideoTutorials /></RequireReport>} />
        <Route path="/businesses" element={<RequireAuth><MyBusinesses /></RequireAuth>} />
        <Route path="/reports" element={<RequireAuth><MyReports /></RequireAuth>} />
        <Route path="/post-loan" element={<RequireAuth><PostLoan /></RequireAuth>} />
        <Route path="/businesses/:id/profile" element={<RequireAuth><BusinessProfilePage /></RequireAuth>} />
        <Route path="/businesses/:id/health" element={<RequireAuth><Health /></RequireAuth>} />
        <Route path="/businesses/:id/market-gap" element={<RequireAuth><MarketGap /></RequireAuth>} />
        <Route path="/businesses/:id/forecast" element={<RequireAuth><ForecastPage /></RequireAuth>} />
        <Route path="/businesses/:id/scenarios" element={<RequireAuth><Scenarios /></RequireAuth>} />
      </Routes>
    </Layout>
  )
}

function Guarded({ children }: { children: ReactNode }) {
  const pathname = useLocation().pathname
  return <ErrorBoundary key={pathname}>{children}</ErrorBoundary>
}

function RequireAnalysis({ children }: { children: ReactNode }) {
  const { result, isHydrated } = useAnalysis() as any
  if (!isHydrated) return <div className="p-8 text-center text-sm text-slate-500">Loading...</div>
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
function RequireBusinessSetup({ children }: { children: ReactNode }) {
  const { result, isHydrated } = useAnalysis() as any
  if (!isHydrated) return <div className="p-8 text-center text-sm text-slate-500">Loading...</div>
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
function RequireFinanceEligible({ children }: { children: ReactNode }) {
  const { result, isHydrated } = useAnalysis() as any
  if (!isHydrated) return <div className="p-8 text-center text-sm text-slate-500">Loading...</div>
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
function RequireFinance({ children }: { children: ReactNode }) {
  const { result, isHydrated } = useAnalysis() as any
  if (!isHydrated) return <div className="p-8 text-center text-sm text-slate-500">Loading...</div>
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
function RequireReport({ children }: { children: ReactNode }) {
  const { result, isHydrated } = useAnalysis() as any
  if (!isHydrated) return <div className="p-8 text-center text-sm text-slate-500">Loading...</div>
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isHydrated } = useAuth() as any
  const loc = useLocation()
  if (!isHydrated) return <div className="p-8 text-center text-sm text-slate-500">Loading...</div>
  if (!isAuthenticated) return <Navigate to="/login" state={{ next: loc.pathname }} replace />
  return <Guarded>{children}</Guarded>
}
