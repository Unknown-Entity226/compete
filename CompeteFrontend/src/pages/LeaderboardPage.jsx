import { useState } from 'react'
import { Trophy, Swords } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import DuelModal from '../components/duel/DuelModal'

export default function LeaderboardPage() {
  const { currentUser, friends } = useAuth()
  const [duelTarget, setDuelTarget] = useState(null)

  // Construct leaderboard participants
  const participants = [
    {
      username: currentUser?.username || 'You',
      realName: currentUser?.realName || 'You',
      contestRating: Number.isFinite(currentUser?.contestRating) ? currentUser.contestRating : null,
      globalRanking: currentUser?.globalRanking || null,
      problemStats: currentUser?.problemStats || { total: 0, easy: 0, medium: 0, hard: 0 },
      strongestArea: currentUser?.strongestArea || null,
      isCurrentUser: true,
    },
    ...friends.map((f) => ({
      username: f.username,
      realName: f.realName || f.username,
      contestRating: Number.isFinite(f.contestRating) ? f.contestRating : null,
      globalRanking: f.globalRanking || null,
      problemStats: f.problemStats || { total: 0, easy: 0, medium: 0, hard: 0 },
      strongestArea: f.strongestArea || null,
      isCurrentUser: false,
    })),
  ]

  // Sort descending by contest rating, then total problems
  participants.sort((a, b) => {
    if (a.contestRating == null && b.contestRating != null) return 1
    if (a.contestRating != null && b.contestRating == null) return -1
    return (b.contestRating ?? 0) - (a.contestRating ?? 0) || (b.problemStats?.total || 0) - (a.problemStats?.total || 0)
  })

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      {/* Page Header */}
      <div className="mb-8 space-y-2">
        <div className="flex items-center gap-2 text-xs font-bold text-amber-400 uppercase tracking-wider font-heading">
          <Trophy className="h-4 w-4" />
          <span>Competitive Standing</span>
        </div>
        <h1 className="font-heading text-3xl sm:text-4xl font-extrabold text-white">
          Friends Leaderboard
        </h1>
        <p className="text-sm text-gray-400">
          Sorted by LeetCode contest rating, with total solved as the tie breaker.
        </p>
      </div>

      {/* Leaderboard Table / Card List */}
      <div className="rounded-2xl border border-[#2a2d35] bg-[#16181c] shadow-2xl overflow-hidden">
        {/* Table Head */}
        <div className="grid grid-cols-12 gap-2 border-b border-[#2a2d35] bg-[#121316] px-6 py-3.5 text-xs font-semibold text-gray-400 uppercase tracking-wider">
          <div className="col-span-1">Rank</div>
          <div className="col-span-4 sm:col-span-4">Competitor</div>
          <div className="col-span-2 text-center">Contest Rating</div>
          <div className="col-span-2 text-center hidden sm:block">Total Solved</div>
          <div className="col-span-2 text-center hidden sm:block">Global Rank</div>
          <div className="col-span-5 sm:col-span-1 text-right">Action</div>
        </div>

        {/* Table Body */}
        <div className="divide-y divide-[#2a2d35]/60">
          {participants.map((player, idx) => {
            const rank = idx + 1
            const isTop = rank === 1
            const stats = player.problemStats || { total: 0, easy: 0, medium: 0, hard: 0 }

            return (
              <div
                key={player.username}
                className={`grid grid-cols-12 gap-2 items-center px-6 py-4 transition-colors ${
                  player.isCurrentUser
                    ? 'bg-purple-950/20 hover:bg-purple-950/30'
                    : 'hover:bg-[#1a1c24]'
                }`}
              >
                {/* Rank */}
                <div className="col-span-1 flex items-center">
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-lg font-heading text-xs font-bold ${
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
                </div>

                {/* User Info */}
                <div className="col-span-4 sm:col-span-4 flex items-center gap-3">
                  <div className="hidden sm:flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-700 to-indigo-600 font-heading text-xs font-bold text-white">
                    {player.username?.[0]?.toUpperCase()}
                  </div>
                  <div className="truncate">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="font-heading text-sm font-bold text-white truncate">
                        {player.realName}
                      </span>
                      {player.isCurrentUser && (
                        <span className="rounded bg-purple-500/20 px-1.5 py-0.2 text-[9px] font-semibold text-purple-300 border border-purple-500/40">
                          YOU
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-gray-500 font-mono block truncate">
                      @{player.username}
                    </span>
                  </div>
                </div>

                {/* Contest Rating */}
                <div className="col-span-2 text-center">
                  <span className="font-heading text-sm font-bold text-amber-300">
                    {player.contestRating ?? '—'}
                  </span>
                </div>

                {/* Total Solved */}
                <div className="col-span-2 text-center hidden sm:block">
                  <span className="font-heading text-sm font-bold text-white">
                    {stats.total}
                  </span>
                  <div className="text-[10px] text-gray-500">
                    {stats.easy}E · {stats.medium}M · {stats.hard}H
                  </div>
                </div>

                {/* Global Rank */}
                <div className="col-span-2 text-center hidden sm:block">
                  <span className="text-xs text-gray-400 font-mono">
                    {player.globalRanking ? `#${player.globalRanking.toLocaleString()}` : '—'}
                  </span>
                </div>

                {/* Action (Duel) */}
                <div className="col-span-5 sm:col-span-1 text-right">
                  {!player.isCurrentUser && (
                    <button
                      type="button"
                      onClick={() => setDuelTarget(player.username)}
                      className="inline-flex items-center gap-1 rounded-lg border border-purple-500/40 bg-purple-950/40 px-2.5 py-1 text-xs font-semibold text-purple-300 hover:bg-purple-900/60 hover:text-white transition-colors cursor-pointer"
                    >
                      <Swords className="h-3 w-3" />
                      <span>Duel</span>
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

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
