import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { X, Sparkles, AlertCircle, Loader2, Link2, User } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { comparisonService } from '../../services/comparisonService'

function extractLeetCodeUsername(input) {
  if (!input) return ''
  const trimmed = input.trim()
  if (/^(https?:\/\/|www\.|leetcode\.com\/)/i.test(trimmed)) {
    try {
      const normalizedUrl = /^(www\.|leetcode\.com\/)/i.test(trimmed) ? `https://${trimmed}` : trimmed
      const url = new URL(normalizedUrl)
      if (!['leetcode.com', 'www.leetcode.com'].includes(url.hostname.toLowerCase())) return ''
      const segments = url.pathname.split('/').filter(Boolean)
      if (segments[0] === 'u' && segments[1]) return segments[1]
      return segments.length === 1 ? segments[0] : ''
    } catch {
      return ''
    }
  }
  return trimmed.replace(/^@/, '')
}

export default function LoginModal({ isOpen, onClose }) {
  const { login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [displayName, setDisplayName] = useState('')
  const [profileInput, setProfileInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const dialogRef = useRef(null)
  const closeButtonRef = useRef(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (!isOpen) {
      requestIdRef.current += 1
      return undefined
    }

    const previousOverflow = document.body.style.overflow
    const previousFocus = document.activeElement
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key !== 'Tab') return

      const focusableElements = dialogRef.current?.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
      )
      if (!focusableElements?.length) return
      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
      previousFocus?.focus?.()
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleLogin = async (e) => {
    e?.preventDefault()
    setErrorMessage('')

    const username = extractLeetCodeUsername(profileInput)
    if (!username) {
      setErrorMessage('Please enter your LeetCode username or profile link.')
      return
    }

    setIsLoading(true)
    const requestId = ++requestIdRef.current
    try {
      const profile = await comparisonService.getUserProfile(username)
      if (requestId !== requestIdRef.current) return
      login({
        username: profile.username || username,
        realName: displayName.trim() || profile.realName || username,
        avatarUrl: profile.avatarUrl || null,
        contestRating: profile.contestRating ?? null,
        globalRanking: profile.globalRanking ?? null,
        problemStats: profile.problemStats || { total: 0, easy: 0, medium: 0, hard: 0 },
        strongestArea: profile.strongestArea || null,
        topicStats: profile.topicStats || [],
        lastUpdated: profile.lastUpdated || null,
        isMockData: Boolean(profile.isMockData),
      })
      const destination = location.state?.from
      if (destination?.pathname) {
        navigate(`${destination.pathname}${destination.search || ''}${destination.hash || ''}`, {
          replace: true,
          state: null,
        })
      }
      onClose()
    } catch (err) {
      if (requestId !== requestIdRef.current) return
      if (err.status === 404) {
        setErrorMessage(`LeetCode user "${username}" was not found. Please verify the handle.`)
      } else {
        setErrorMessage(err.message || 'Unable to connect to profile service. Check your connection.')
      }
    } finally {
      if (requestId === requestIdRef.current) setIsLoading(false)
    }
  }

  const handleQuickDemo = (demoUser) => {
    setProfileInput(demoUser)
    setDisplayName(demoUser === 'algo_master_99' ? 'Algo Master' : 'Binary Ninja')
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-dialog-title"
        className="relative my-auto w-full max-w-md rounded-2xl border border-[#2a2d35] bg-[#16181c] p-6 sm:p-8 shadow-2xl"
      >
        {/* Close Button */}
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label="Close profile setup"
          className="absolute top-4 right-4 flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-[#20222a] hover:text-white transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Modal Header */}
        <div className="mb-6 space-y-1.5">
          <div className="flex items-center gap-2 text-purple-400 font-heading text-xs font-bold uppercase tracking-wider">
            <Sparkles className="h-4 w-4" />
            <span>Profile Setup</span>
          </div>
          <h2 id="login-dialog-title" className="font-heading text-2xl font-bold text-white">
            Connect to Compete
          </h2>
          <p className="text-xs sm:text-sm text-gray-400">
            Enter your details and LeetCode profile to view head-to-head stats and leaderboard rankings.
          </p>
        </div>

        {/* Quick Demo Previews */}
        <div className="mb-5 rounded-xl border border-purple-900/30 bg-purple-950/20 p-3">
          <span className="block text-[11px] font-medium text-purple-300 mb-2">
            Try with pre-configured accounts:
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleQuickDemo('algo_master_99')}
              className="flex-1 rounded-lg border border-purple-800/40 bg-purple-900/30 py-1.5 px-2 text-xs font-medium text-purple-200 hover:bg-purple-800/40 transition-colors"
            >
              algo_master_99
            </button>
            <button
              type="button"
              onClick={() => handleQuickDemo('binary_ninja')}
              className="flex-1 rounded-lg border border-purple-800/40 bg-purple-900/30 py-1.5 px-2 text-xs font-medium text-purple-200 hover:bg-purple-800/40 transition-colors"
            >
              binary_ninja
            </button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label htmlFor="display-name" className="block text-xs font-medium text-gray-300 mb-1.5">
              Display Name (optional)
            </label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
              <input
                type="text"
                id="display-name"
                placeholder="e.g. John Doe"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full rounded-xl border border-[#2a2d35] bg-[#0d0d0f] pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 transition-colors"
              />
            </div>
          </div>

          <div>
            <label htmlFor="profile-input" className="block text-xs font-medium text-gray-300 mb-1.5">
              Competitive Site Profile Link *
            </label>
            <div className="relative">
              <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
              <input
                type="text"
                id="profile-input"
                required
                autoComplete="url"
                aria-invalid={Boolean(errorMessage)}
                placeholder="https://leetcode.com/your_handle/ or your_handle"
                value={profileInput}
                onChange={(e) => setProfileInput(e.target.value)}
                className="w-full rounded-xl border border-[#2a2d35] bg-[#0d0d0f] pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 transition-colors"
              />
            </div>
            <p className="mt-1 text-[11px] text-gray-500">
              Only LeetCode is supported at this moment.
            </p>
          </div>

          {errorMessage && (
            <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-900/50 bg-red-950/30 p-2.5 text-xs text-red-300">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <div className="pt-2">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 py-3 text-sm font-semibold text-white shadow-lg shadow-purple-600/30 hover:opacity-95 disabled:opacity-50 transition-all cursor-pointer"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Verifying LeetCode Profile...</span>
                </>
              ) : (
                <span>Log In & Connect</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
