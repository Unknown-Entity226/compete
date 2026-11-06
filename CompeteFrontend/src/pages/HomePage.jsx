import { useAuth } from '../context/AuthContext'
import LoggedOutHero from '../components/auth/LoggedOutHero'
import HowItWorks from '../components/auth/HowItWorks'
import Dashboard from './Dashboard'

export default function HomePage({ onOpenLogin }) {
  const { isLoggedIn } = useAuth()

  if (isLoggedIn) {
    return <Dashboard />
  }

  return (
    <div className="space-y-12">
      <LoggedOutHero onOpenLogin={onOpenLogin} />
      <HowItWorks onOpenLogin={onOpenLogin} />
    </div>
  )
}
