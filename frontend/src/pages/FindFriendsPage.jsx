import { useEffect, useRef, useState } from 'react'
import { Search, UserPlus, Swords, Check, Loader2, AlertCircle, Code, Trophy, Award } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { comparisonService } from '../services/comparisonService'
import DuelModal from '../components/duel/DuelModal'

export default function FindFriendsPage() {
  const { currentUser, friends, addFriend } = useAuth()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [duelTarget, setDuelTarget] = useState(null)
  const searchRequestId = useRef(0)

  useEffect(() => () => {
    searchRequestId.current += 1
  }, [])

  const handleSearch = async (e) => {
    e?.preventDefault()
    if (loading) return
    const trimmed = query.trim().replace(/^@/, '')
    if (!trimmed) {
      setResult(null)
      setError('Enter a LeetCode username to search.')
      return
    }

    const requestId = ++searchRequestId.current
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const profile = await comparisonService.getUserProfile(trimmed)
      if (requestId === searchRequestId.current) setResult(profile)
    } catch (err) {
      if (requestId !== searchRequestId.current) return
      if (err.status === 404) {
        setError(`LeetCode user "${trimmed}" does not exist.`)
      } else {
        setError(err.message || 'Error searching user.')
      }
    } finally {
      if (requestId === searchRequestId.current) setLoading(false)
    }
  }

  const isFriend = result && friends.some((f) => f.username.toLowerCase() === result.username.toLowerCase())
  const isMe = result && currentUser?.username?.toLowerCase() === result.username.toLowerCase()

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      {/* Page Title */}
      <div className="mb-8 space-y-2">
        <h1 className="font-heading text-3xl font-extrabold text-white">
          Find Friends
        </h1>
        <p className="text-sm text-gray-400">
          Search any public LeetCode user, inspect their statistics, and add them to your friends leaderboard.
        </p>
      </div>

      {/* Search Input Box */}
      <form onSubmit={handleSearch} className="mb-8 flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            aria-label="LeetCode username"
            required
            placeholder="Enter LeetCode username (e.g. binary_ninja, tourist, neetcode)..."
            value={query}
            disabled={loading}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-xl border border-[#2a2d35] bg-[#16181c] pl-11 pr-4 py-3 text-sm text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 transition-colors"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-purple-600/30 hover:bg-purple-500 disabled:opacity-50 transition-all cursor-pointer"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          <span>Search</span>
        </button>
      </form>

      {/* Quick Suggestions */}
      <div className="mb-8 flex flex-wrap items-center gap-2 text-xs text-gray-400">
        <span>Popular suggestions:</span>
        {['binary_ninja', 'algo_master_99', 'tourist'].map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => {
              setQuery(s)
            }}
            className="rounded-lg border border-[#2a2d35] bg-[#16181c] px-2.5 py-1 text-gray-300 hover:border-purple-500/40 hover:text-purple-300 transition-colors"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Error Message */}
      {error && (
        <div role="alert" className="mb-8 flex items-center gap-2.5 rounded-xl border border-red-900/50 bg-red-950/30 p-4 text-sm text-red-300">
          <AlertCircle className="h-5 w-5 shrink-0 text-red-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Search Result Card */}
      {result && (
        <div className="rounded-2xl border border-[#2a2d35] bg-[#16181c] p-6 shadow-xl space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-[#2a2d35]">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-600 text-xl font-bold text-white shadow-md">
                {result.username?.[0]?.toUpperCase()}
              </div>
              <div>
                <h3 className="font-heading text-xl font-bold text-white">
                  {result.realName || result.username}
                </h3>
                <span className="text-xs text-purple-400 font-mono">
                  @{result.username}
                </span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              {!isMe && (
                <button
                  type="button"
                  onClick={() => setDuelTarget(result.username)}
                  className="inline-flex items-center gap-2 rounded-xl border border-purple-500/50 bg-purple-950/40 px-4 py-2.5 text-xs font-semibold text-purple-300 hover:bg-purple-900/60 hover:text-white transition-all cursor-pointer"
                >
                  <Swords className="h-4 w-4" />
                  <span>Duel Head-to-Head</span>
                </button>
              )}

              {isMe ? (
                <span className="rounded-lg bg-[#20222a] px-3.5 py-2 text-xs font-medium text-gray-400">
                  That's you!
                </span>
              ) : isFriend ? (
                <span className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-950/50 border border-emerald-800/40 px-4 py-2.5 text-xs font-semibold text-emerald-300">
                  <Check className="h-4 w-4" />
                  <span>Already Friends</span>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => addFriend(result)}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-md shadow-purple-600/30 hover:opacity-95 transition-all cursor-pointer"
                >
                  <UserPlus className="h-4 w-4" />
                  <span>Add Friend</span>
                </button>
              )}
            </div>
          </div>

          {result.isMockData && (
            <p role="status" className="text-xs text-amber-300">
              Showing sample profile data. Live profile data is unavailable right now.
            </p>
          )}

          {/* Stat Numbers */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl bg-[#101115] p-3 text-center">
              <div className="text-[11px] text-gray-400 mb-1 flex items-center justify-center gap-1">
                <Code className="h-3 w-3 text-purple-400" />
                <span>Solved</span>
              </div>
              <div className="font-heading text-xl font-bold text-white">
                {result.problemStats?.total || 0}
              </div>
            </div>

            <div className="rounded-xl bg-[#101115] p-3 text-center">
              <div className="text-[11px] text-gray-400 mb-1 flex items-center justify-center gap-1">
                <Trophy className="h-3 w-3 text-amber-400" />
                <span>Rating</span>
              </div>
              <div className="font-heading text-xl font-bold text-amber-300">
                {result.contestRating ?? '—'}
              </div>
            </div>

            <div className="rounded-xl bg-[#101115] p-3 text-center">
              <div className="text-[11px] text-gray-400 mb-1 flex items-center justify-center gap-1">
                <Award className="h-3 w-3 text-cyan-400" />
                <span>Rank</span>
              </div>
              <div className="font-heading text-lg font-bold text-cyan-300">
                {result.globalRanking != null ? `#${result.globalRanking.toLocaleString()}` : '—'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Duel Modal */}
      {duelTarget && currentUser && (
        <DuelModal
          isOpen={true}
          onClose={() => setDuelTarget(null)}
          user1={currentUser.username}
          user2={duelTarget}
        />
      )}
    </div>
  )
}
