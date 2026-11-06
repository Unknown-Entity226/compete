import { useState, useEffect, useRef } from 'react'
import { X, Trophy, Swords, Loader2 } from 'lucide-react'
import { comparisonService } from '../../services/comparisonService'

export default function DuelModal({ isOpen, onClose, user1, user2 }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const closeButtonRef = useRef(null)

  useEffect(() => {
    setData(null)
    setError(null)
    setLoading(true)
    if (!isOpen || !user1 || !user2) return undefined

    let isCancelled = false
    const previousOverflow = document.body.style.overflow
    const previousFocus = document.activeElement
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)

    async function fetchDuel() {
      try {
        const res = await comparisonService.compareUsers(user1, user2)
        if (!isCancelled) {
          setData(res)
          setLoading(false)
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || 'Failed to compare competitors.')
          setLoading(false)
        }
      }
    }

    fetchDuel()

    return () => {
      isCancelled = true
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKeyDown)
      previousFocus?.focus?.()
    }
  }, [isOpen, user1, user2, onClose])

  if (!isOpen) return null

  const winner = data?.winner
  const scores = data?.score || {}
  const breakdowns = data?.scoreBreakdown || {}
  const metrics = data?.metrics || {}
  const getForUser = (values, username) => {
    if (values[username] !== undefined) return values[username]
    const match = Object.keys(values).find((key) => key.toLowerCase() === username.toLowerCase())
    return match ? values[match] : undefined
  }

  const score1 = getForUser(scores, user1) ?? 0
  const score2 = getForUser(scores, user2) ?? 0
  const breakdown1 = getForUser(breakdowns, user1)
  const breakdown2 = getForUser(breakdowns, user2)
  const isUser1Winner = winner?.toLowerCase() === user1?.toLowerCase()
  const isUser2Winner = winner?.toLowerCase() === user2?.toLowerCase()
  const isTie = winner?.toUpperCase() === 'TIE'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto p-4 bg-black/85 backdrop-blur-md animate-in fade-in duration-200"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="duel-dialog-title"
        className="relative my-4 w-full max-w-3xl rounded-3xl border border-[#2a2d35] bg-[#16181c] p-5 shadow-2xl sm:my-8 sm:p-8"
      >
        {/* Close Button */}
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label="Close duel comparison"
          className="absolute top-5 right-5 flex h-9 w-9 items-center justify-center rounded-xl bg-[#20222a] text-gray-400 hover:text-white hover:bg-[#2b2e38] transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Modal Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2 rounded-full bg-purple-950/70 border border-purple-800/40 px-3 py-1 text-xs font-semibold text-purple-300 uppercase tracking-wider mb-2">
            <Swords className="h-3.5 w-3.5 text-purple-400" />
            <span>Head-to-Head Duel</span>
          </div>
          <h2 id="duel-dialog-title" className="font-heading text-2xl sm:text-3xl font-extrabold text-white">
            {user1} <span className="text-purple-400 font-normal">vs</span> {user2}
          </h2>
        </div>

        {loading ? (
          <div role="status" className="flex flex-col items-center justify-center py-16 gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
            <p className="text-sm text-gray-400">Fetching live LeetCode stats & calculating duel scores...</p>
          </div>
        ) : error ? (
          <div role="alert" className="rounded-xl border border-red-900/50 bg-red-950/30 p-4 text-center text-sm text-red-300">
            {error}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Winner Announcement Banner */}
            <div className="rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-purple-500/10 to-indigo-500/10 p-5 text-center">
              <div className="flex items-center justify-center gap-2 text-amber-400 font-heading text-lg sm:text-xl font-bold mb-1">
                <Trophy className="h-6 w-6 text-amber-400" />
                <span>
                  {isTie ? "It's an Even Match (TIE)!" : winner ? `Duel Winner: ${winner}` : 'Comparison complete'}
                </span>
              </div>
              <p className="text-xs text-gray-400">
                Determined by contest rating, difficulty-weighted problems, velocity, and solving streaks.
              </p>
            </div>

            {/* Score Comparison Cards */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* User 1 */}
              <div
                className={`rounded-2xl border p-5 transition-all ${
                  isUser1Winner
                    ? 'border-purple-500/60 bg-gradient-to-b from-purple-950/40 to-[#181922] shadow-lg shadow-purple-900/20'
                    : 'border-[#2a2d35] bg-[#121316]'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-heading text-base font-bold text-white truncate max-w-[120px]">
                    {user1}
                  </span>
                  {isUser1Winner && (
                    <span className="rounded bg-amber-400/20 px-2 py-0.5 text-[11px] font-bold text-amber-300 border border-amber-400/30">
                      WINNER 👑
                    </span>
                  )}
                </div>
                <div className="font-heading text-3xl sm:text-4xl font-black text-purple-300 mb-1">
                  {score1} <span className="text-xs font-normal text-gray-400">pts</span>
                </div>
                {breakdown1 && (
                  <div className="text-[11px] text-gray-400 space-y-1 pt-2 border-t border-[#2a2d35]/60">
                    <div className="flex justify-between">
                      <span>Rating Score:</span>
                      <strong className="text-gray-200">{breakdown1.ratingScore}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Difficulty Score:</span>
                      <strong className="text-gray-200">{breakdown1.difficultyScore}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Velocity Score:</span>
                      <strong className="text-gray-200">{breakdown1.velocityScore}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Streak Score:</span>
                      <strong className="text-gray-200">{breakdown1.streakScore}</strong>
                    </div>
                  </div>
                )}
              </div>

              {/* User 2 */}
              <div
                className={`rounded-2xl border p-5 transition-all ${
                  isUser2Winner
                    ? 'border-purple-500/60 bg-gradient-to-b from-purple-950/40 to-[#181922] shadow-lg shadow-purple-900/20'
                    : 'border-[#2a2d35] bg-[#121316]'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="font-heading text-base font-bold text-white truncate max-w-[120px]">
                    {user2}
                  </span>
                  {isUser2Winner && (
                    <span className="rounded bg-amber-400/20 px-2 py-0.5 text-[11px] font-bold text-amber-300 border border-amber-400/30">
                      WINNER 👑
                    </span>
                  )}
                </div>
                <div className="font-heading text-3xl sm:text-4xl font-black text-purple-300 mb-1">
                  {score2} <span className="text-xs font-normal text-gray-400">pts</span>
                </div>
                {breakdown2 && (
                  <div className="text-[11px] text-gray-400 space-y-1 pt-2 border-t border-[#2a2d35]/60">
                    <div className="flex justify-between">
                      <span>Rating Score:</span>
                      <strong className="text-gray-200">{breakdown2.ratingScore}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Difficulty Score:</span>
                      <strong className="text-gray-200">{breakdown2.difficultyScore}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Velocity Score:</span>
                      <strong className="text-gray-200">{breakdown2.velocityScore}</strong>
                    </div>
                    <div className="flex justify-between">
                      <span>Streak Score:</span>
                      <strong className="text-gray-200">{breakdown2.streakScore}</strong>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Differential Metrics Table */}
            <div className="rounded-xl border border-[#2a2d35] bg-[#101115] p-4">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-3">
                Key Comparison Differentials
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="rounded-lg bg-[#181920] p-2.5">
                  <div className="text-[11px] text-gray-400">Total Solved Diff</div>
                  <div className={`font-heading text-sm font-bold ${metrics.totalSolvedDiff >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {metrics.totalSolvedDiff == null ? '—' : metrics.totalSolvedDiff > 0 ? `+${metrics.totalSolvedDiff}` : metrics.totalSolvedDiff}
                  </div>
                </div>

                <div className="rounded-lg bg-[#181920] p-2.5">
                  <div className="text-[11px] text-gray-400">Rating Diff</div>
                  <div className="font-heading text-sm font-bold text-amber-300">
                    {metrics.ratingDiff != null ? (metrics.ratingDiff > 0 ? `+${metrics.ratingDiff}` : metrics.ratingDiff) : '—'}
                  </div>
                </div>

                <div className="rounded-lg bg-[#181920] p-2.5">
                  <div className="text-[11px] text-gray-400">Velocity (7d) Diff</div>
                  <div className="font-heading text-sm font-bold text-cyan-300">
                    {metrics.velocity7dDiff == null ? '—' : `${metrics.velocity7dDiff > 0 ? '+' : ''}${metrics.velocity7dDiff} /day`}
                  </div>
                </div>

                <div className="rounded-lg bg-[#181920] p-2.5">
                  <div className="text-[11px] text-gray-400">Streak Diff</div>
                  <div className="font-heading text-sm font-bold text-fuchsia-300">
                    {metrics.streakDiff == null ? '—' : `${metrics.streakDiff > 0 ? '+' : ''}${metrics.streakDiff} days`}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
