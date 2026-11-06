import { Link } from 'react-router-dom'
import { Trophy, Swords, UserPlus } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

export default function FriendsRankingStrip({ onCompare }) {
  const { currentUser, friends } = useAuth()

  // Build ranking list: current user + all friends
  const myRating = Number.isFinite(currentUser?.contestRating) ? currentUser.contestRating : null
  const myTotal = currentUser?.problemStats?.total || 0

  const allParticipants = [
    {
      username: currentUser?.username || 'You',
      realName: currentUser?.realName || 'You',
      contestRating: myRating,
      totalSolved: myTotal,
      isMockData: Boolean(currentUser?.isMockData),
      isCurrentUser: true,
    },
    ...friends.map((f) => ({
      username: f.username,
      realName: f.realName || f.username,
      contestRating: Number.isFinite(f.contestRating) ? f.contestRating : null,
      totalSolved: f.problemStats?.total || 0,
      isMockData: Boolean(f.isMockData),
      isCurrentUser: false,
    })),
  ]

  // Sort descending by contest rating (fallback to total solved)
  allParticipants.sort((a, b) => {
    if (a.contestRating == null && b.contestRating != null) return 1
    if (a.contestRating != null && b.contestRating == null) return -1
    return (b.contestRating ?? 0) - (a.contestRating ?? 0) || b.totalSolved - a.totalSolved
  })

  const myRank = allParticipants.findIndex((p) => p.isCurrentUser) + 1
  const maxRating = Math.max(...allParticipants.map((p) => p.contestRating ?? 0), 2000)

  return (
    <div className="rounded-2xl border border-[#2a2d35] bg-[#16181c] p-6 shadow-xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#2a2d35]/60 mb-5 gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Trophy className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-heading text-lg font-bold text-white flex items-center gap-2">
              <span>Current Ranking Among Friends</span>
              <span className="rounded-full bg-purple-900/60 px-2.5 py-0.5 text-xs font-semibold text-purple-300 border border-purple-700/40">
                Rank #{myRank} of {allParticipants.length}
              </span>
            </h3>
          <p className="text-xs text-gray-400">
              Sorted by contest rating, with total solved as the tie breaker
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            to="/friends/find"
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#2a2d35] bg-[#121316] px-3 py-1.5 text-xs font-medium text-gray-300 hover:border-purple-500/40 hover:text-white transition-colors"
          >
            <UserPlus className="h-3.5 w-3.5" />
            <span>Find More Friends</span>
          </Link>
          <Link
            to="/leaderboard"
            className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600/20 border border-purple-500/40 px-3 py-1.5 text-xs font-medium text-purple-300 hover:bg-purple-600/30 transition-colors"
          >
            <span>Full Leaderboard</span>
          </Link>
        </div>
      </div>

      {/* Ranking List */}
      <div className="space-y-3">
        {allParticipants.map((participant, index) => {
          const rank = index + 1
          const isTop = rank === 1
          const hasRating = participant.contestRating != null
          const pct = hasRating ? Math.min(100, Math.max(15, (participant.contestRating / maxRating) * 100)) : 0

          return (
            <div
              key={participant.username}
              className={`relative flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border p-4 transition-all duration-200 ${
                participant.isCurrentUser
                  ? 'border-purple-500/60 bg-gradient-to-r from-purple-950/40 via-[#181920] to-[#16181c] shadow-lg shadow-purple-950/20'
                  : 'border-[#2a2d35]/60 bg-[#121316]/60 hover:border-[#383c48]'
              }`}
            >
              <div className="flex items-center gap-3.5 min-w-[200px]">
                {/* Rank Badge */}
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg font-heading text-xs font-bold ${
                    isTop
                      ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40'
                      : rank === 2
                      ? 'bg-slate-300/20 text-slate-200 border border-slate-300/30'
                      : rank === 3
                      ? 'bg-amber-700/20 text-amber-500 border border-amber-700/30'
                      : 'bg-[#20222a] text-gray-400'
                  }`}
                >
                  {isTop ? '👑' : `#${rank}`}
                </div>

                {/* Avatar / Name */}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-heading text-sm font-bold text-white">
                      {participant.realName}
                    </span>
                    {participant.isCurrentUser && (
                      <span className="rounded bg-purple-500/20 px-1.5 py-0.2 text-[10px] font-semibold text-purple-300 border border-purple-500/40">
                        YOU
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-gray-500 font-mono">
                    @{participant.username}
                  </span>
                  {participant.isMockData && (
                    <span className="block text-[10px] text-amber-300">Sample profile</span>
                  )}
                </div>
              </div>

              {/* Relative Rating Progress Bar */}
              <div className="flex-1 max-w-md hidden md:block">
                <div className="flex justify-between text-[11px] text-gray-400 mb-1">
                  <span>Rating: <strong className="text-gray-200">{participant.contestRating ?? '—'}</strong></span>
                  <span>{participant.totalSolved} solved</span>
                </div>
                <div className="h-2 w-full rounded-full bg-[#20222a] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      participant.isCurrentUser
                        ? 'bg-gradient-to-r from-purple-500 to-fuchsia-500'
                        : isTop
                        ? 'bg-amber-500'
                        : 'bg-indigo-500/80'
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>

              {/* Actions & Rating Badge */}
              <div className="flex items-center justify-between sm:justify-end gap-3">
                <div className="text-right sm:text-right">
                  <div className="font-heading text-sm font-bold text-purple-300">
                    {participant.contestRating ?? '—'} {hasRating && <span className="text-[10px] font-normal text-gray-400">pts</span>}
                  </div>
                  <div className="text-[10px] text-gray-500">
                    {participant.totalSolved} problems
                  </div>
                </div>

                {!participant.isCurrentUser && (
                  <button
                    type="button"
                    onClick={() => onCompare?.(participant.username)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-purple-500/40 bg-purple-950/30 px-3 py-1.5 text-xs font-semibold text-purple-300 hover:bg-purple-900/50 hover:text-white transition-all cursor-pointer"
                  >
                    <Swords className="h-3.5 w-3.5" />
                    <span>Duel</span>
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
