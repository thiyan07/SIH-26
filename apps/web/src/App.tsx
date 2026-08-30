import { Routes, Route, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { Layout } from './components/Layout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Landing } from './pages/Landing'
import { Analyze } from './pages/Analyze'
import { Dashboard } from './pages/Dashboard'
import { Market } from './pages/Market'
import { MapPage } from './pages/MapPage'
import { Finance } from './pages/Finance'
import { Simulator } from './pages/Simulator'
import { Report } from './pages/Report'
import { Schemes } from './pages/Schemes'
import { DataSources } from './pages/DataSources'

export default function App() {
  const location = useLocation()
  const isLanding = location.pathname === '/'
  return (
    <Layout hideNav={isLanding}>
      <Routes>
        <Route path="/" element={<Guarded><Landing /></Guarded>} />
        <Route path="/analyze" element={<Guarded><Analyze /></Guarded>} />
        <Route path="/dashboard" element={<Guarded><Dashboard /></Guarded>} />
        <Route path="/market" element={<Guarded><Market /></Guarded>} />
        <Route path="/map" element={<Guarded><MapPage /></Guarded>} />
        <Route path="/finance" element={<Guarded><Finance /></Guarded>} />
        <Route path="/simulator" element={<Guarded><Simulator /></Guarded>} />
        <Route path="/report" element={<Guarded><Report /></Guarded>} />
        <Route path="/schemes" element={<Guarded><Schemes /></Guarded>} />
        <Route path="/data-sources" element={<Guarded><DataSources /></Guarded>} />
      </Routes>
    </Layout>
  )
}

function Guarded({ children }: { children: ReactNode }) {
  const pathname = useLocation().pathname
  // Key by path so a boundary reset happens on each route change,
  // letting the user retry after navigating away and back.
  return <ErrorBoundary key={pathname}>{children}</ErrorBoundary>
}
