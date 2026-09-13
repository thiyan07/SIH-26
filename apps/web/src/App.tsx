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
import { ExpenseTracker } from './pages/ExpenseTracker'
import { BusinessSetup } from './pages/BusinessSetup'
import { VideoTutorials } from './pages/VideoTutorials'
import { useAnalysis } from './lib/analysisStore'

export default function App() {
  const location = useLocation()
  const isLanding = location.pathname === '/'
  return (
    <Layout hideNav={isLanding}>
      <Routes>
        <Route path="/" element={<Guarded><Landing /></Guarded>} />
        <Route path="/analyze" element={<Guarded><Analyze /></Guarded>} />
        <Route path="/dashboard" element={<RequireAnalysis><Dashboard /></RequireAnalysis>} />
        <Route path="/business-setup" element={<RequireAnalysis><BusinessSetup /></RequireAnalysis>} />
        <Route path="/market" element={<RequireBusinessSetup><Market /></RequireBusinessSetup>} />
        <Route path="/map" element={<Navigate to="/market" replace />} />
        <Route path="/schemes" element={<RequireBusinessSetup><Schemes /></RequireBusinessSetup>} />
        <Route path="/finance" element={<RequireFinanceEligible><Finance /></RequireFinanceEligible>} />
        <Route path="/simulator" element={<RequireFinance><Simulator /></RequireFinance>} />
        <Route path="/report" element={<RequireReport><Report /></RequireReport>} />
        <Route path="/videos" element={<RequireReport><VideoTutorials /></RequireReport>} />
        <Route path="/expenses" element={<Guarded><ExpenseTracker /></Guarded>} />
      </Routes>
    </Layout>
  )
}

function Guarded({ children }: { children: ReactNode }) {
  const pathname = useLocation().pathname
  return <ErrorBoundary key={pathname}>{children}</ErrorBoundary>
}

function RequireAnalysis({ children }: { children: ReactNode }) {
  const { result } = useAnalysis()
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
function RequireBusinessSetup({ children }: { children: ReactNode }) {
  const { result } = useAnalysis()
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
function RequireFinanceEligible({ children }: { children: ReactNode }) {
  const { result } = useAnalysis()
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
function RequireFinance({ children }: { children: ReactNode }) {
  const { result } = useAnalysis()
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
function RequireReport({ children }: { children: ReactNode }) {
  const { result } = useAnalysis()
  if (!result) return <Navigate to="/analyze" replace />
  return <Guarded>{children}</Guarded>
}
