import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Navbar from './components/layout/Navbar'
import HomePage from './pages/HomePage'
import FindFriendsPage from './pages/FindFriendsPage'
import YourFriendsPage from './pages/YourFriendsPage'
import LeaderboardPage from './pages/LeaderboardPage'
import LoginModal from './components/auth/LoginModal'

function ProtectedRoute({ children }) {
  const { isLoggedIn } = useAuth()
  if (!isLoggedIn) {
    return <Navigate to="/" replace />
  }
  return children
}

function AppContent() {
  const [isLoginOpen, setIsLoginOpen] = useState(false)

  return (
    <div className="min-h-screen bg-[#0d0d0f] text-gray-100 flex flex-col justify-between selection:bg-purple-600 selection:text-white">
      <div>
        <Navbar onOpenProfile={() => setIsLoginOpen(true)} />
        <main>
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
