import { lazy, Suspense, useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Navbar from './components/layout/Navbar'
import LoginModal from './components/auth/LoginModal'

const HomePage = lazy(() => import('./pages/HomePage'))
const FindFriendsPage = lazy(() => import('./pages/FindFriendsPage'))
const YourFriendsPage = lazy(() => import('./pages/YourFriendsPage'))
const LeaderboardPage = lazy(() => import('./pages/LeaderboardPage'))

function ProtectedRoute({ children }) {
  const { isLoggedIn } = useAuth()
  const location = useLocation()
  if (!isLoggedIn) {
    return <Navigate to="/" replace state={{ from: location }} />
  }
  return children
}

function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return null
}

function AppContent() {
  const [isLoginOpen, setIsLoginOpen] = useState(false)

  return (
    <div className="min-h-screen bg-[#0d0d0f] text-gray-100 flex flex-col justify-between selection:bg-purple-600 selection:text-white">
      <div>
        <ScrollToTop />
        <Navbar onOpenProfile={() => setIsLoginOpen(true)} />
        <main>
          <Suspense fallback={<div role="status" className="mx-auto max-w-7xl px-4 py-12 text-center text-sm text-gray-400">Loading page…</div>}>
            <Routes>
              <Route path="/" element={<HomePage onOpenLogin={() => setIsLoginOpen(true)} />} />
              <Route
                path="/friends/find"
                element={
                  <ProtectedRoute>
                    <FindFriendsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/friends"
                element={
                  <ProtectedRoute>
                    <YourFriendsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/leaderboard"
                element={
                  <ProtectedRoute>
                    <LeaderboardPage />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>
      </div>

      {/* Footer */}
      <footer className="border-t border-[#2a2d35]/60 bg-[#0d0d0f] py-6 px-4 text-center text-xs text-gray-500">
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Compete — Developer Head-to-Head & Leaderboards</span>
          <span>Powered by FastAPI & LeetCode GraphQL Proxy</span>
        </div>
      </footer>

      {/* Profile / Login Modal */}
      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  )
}
