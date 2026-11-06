import { lazy, Suspense } from 'react'
import { useAuth } from '../context/AuthContext'
import LoggedOutHero from '../components/auth/LoggedOutHero'
import HowItWorks from '../components/auth/HowItWorks'

const Dashboard = lazy(() => import('./Dashboard'))

export default function HomePage({ onOpenLogin }) {
  const { isLoggedIn } = useAuth()

  if (isLoggedIn) {
    return (
      <Suspense fallback={<div role="status" className="mx-auto max-w-7xl px-4 py-12 text-center text-sm text-gray-400">Loading dashboard…</div>}>
        <Dashboard />
      </Suspense>
    )
  }

  return (
    <div className="space-y-12">
      <LoggedOutHero onOpenLogin={onOpenLogin} />
      <HowItWorks onOpenLogin={onOpenLogin} />
    </div>
  )
}
