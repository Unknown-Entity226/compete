import { Link, useLocation } from 'react-router-dom'
import { User, LogOut, UserPlus, Users, Trophy } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

export default function Navbar({ onOpenProfile }) {
  const { isLoggedIn, currentUser, logout } = useAuth()
  const location = useLocation()

  const navItems = [
    { name: 'Find Friends', path: '/friends/find', icon: UserPlus },
    { name: 'Your Friends', path: '/friends', icon: Users },
    { name: 'Leaderboard', path: '/leaderboard', icon: Trophy },
  ]

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[#2a2d35] bg-[#0d0d0f]/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-8">
          <Link
            to="/"
            className="flex items-center gap-2 font-heading text-2xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-fuchsia-400 to-indigo-400 hover:opacity-90 transition-opacity"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-purple-600 to-indigo-600 text-white shadow-lg shadow-purple-900/40 text-base">
              ⚡
            </span>
            <span>Compete</span>
          </Link>

          {/* Logged-In Navigation Sections */}
          {isLoggedIn && (
            <nav className="hidden md:flex items-center gap-1">
              {navItems.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname === item.path
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-purple-900/30 text-purple-300 border border-purple-500/30'
                        : 'text-gray-400 hover:bg-[#16181c] hover:text-gray-200'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{item.name}</span>
                  </Link>
                )
              })}
            </nav>
          )}
        </div>

        {/* Right Action: Profile Icon (Logged Out) or Profile Badge + Logout (Logged In) */}
        <div className="flex items-center gap-3">
          {isLoggedIn ? (
            <div className="flex items-center gap-3">
              <Link
                to="/"
                className="flex items-center gap-2.5 rounded-full border border-[#2a2d35] bg-[#16181c] py-1.5 pl-3 pr-4 text-sm font-medium text-gray-200 hover:border-purple-500/40 transition-colors"
              >
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-tr from-purple-600 to-pink-500 text-xs font-bold text-white uppercase">
                  {currentUser?.username?.[0] || 'U'}
                </div>
                <span className="text-gray-300 max-w-[120px] truncate">
                  {currentUser?.realName || currentUser?.username}
                </span>
                {currentUser?.contestRating && (
                  <span className="rounded bg-purple-950/80 px-1.5 py-0.5 text-[10px] font-semibold text-purple-300 border border-purple-700/40">
                    {currentUser.contestRating}
                  </span>
                )}
              </Link>

              <button
                type="button"
                onClick={logout}
                title="Log out"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#2a2d35] bg-[#16181c] text-gray-400 hover:border-red-500/40 hover:bg-red-500/10 hover:text-red-400 transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onOpenProfile}
              title="Profile / Log In"
              className="group flex h-10 w-10 items-center justify-center rounded-xl border border-[#2a2d35] bg-[#16181c] text-gray-300 hover:border-purple-500 hover:bg-purple-950/20 hover:text-purple-300 transition-all shadow-sm"
            >
              <User className="h-5 w-5 transition-transform group-hover:scale-110" />
            </button>
          )}
        </div>
      </div>

      {/* Mobile Nav Bar when Logged In */}
      {isLoggedIn && (
        <div className="flex md:hidden border-t border-[#2a2d35] bg-[#121316] px-4 py-2 justify-around">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex flex-col items-center gap-1 text-[11px] font-medium py-1 px-2 rounded ${
                  isActive ? 'text-purple-400' : 'text-gray-400'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{item.name}</span>
              </Link>
            )
          })}
        </div>
      )}
    </header>
  )
}
