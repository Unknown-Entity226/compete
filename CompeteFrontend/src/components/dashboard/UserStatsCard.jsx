import { Trophy, Award, Zap, Code } from 'lucide-react'

export default function UserStatsCard({ user }) {
  if (!user) return null

  const stats = user.problemStats || { total: 0, easy: 0, medium: 0, hard: 0 }
  const total = stats.total || 0
  const easyPct = total > 0 ? (stats.easy / total) * 100 : 0
  const medPct = total > 0 ? (stats.medium / total) * 100 : 0
  const hardPct = total > 0 ? (stats.hard / total) * 100 : 0

  return (
    <div className="rounded-2xl border border-[#2a2d35] bg-[#16181c] p-6 shadow-xl flex flex-col justify-between">
      <div>
        {/* User Identity / Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#2a2d35]/60 mb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-purple-600 via-fuchsia-600 to-indigo-600 text-lg font-bold text-white shadow-md shadow-purple-900/30">
              {user.username?.[0]?.toUpperCase() || 'U'}
            </div>
            <div>
              <h2 className="font-heading text-lg font-bold text-white">
                {user.realName || user.username}
              </h2>
              <span className="text-xs text-purple-400 font-mono">
                @{user.username}
              </span>
            </div>
          </div>
          {user.strongestArea && (
            <div className="hidden sm:flex items-center gap-1.5 rounded-full border border-purple-800/40 bg-purple-950/40 px-3 py-1 text-xs text-purple-300">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
              <span>{user.strongestArea}</span>
            </div>
          )}
        </div>

        {/* High-Level Numeric Indicators */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="rounded-xl border border-[#2a2d35]/50 bg-[#0d0d0f]/60 p-3.5 text-center">
            <div className="flex items-center justify-center gap-1 text-[11px] text-gray-400 mb-1">
              <Code className="h-3.5 w-3.5 text-purple-400" />
              <span>Solved</span>
            </div>
            <div className="font-heading text-2xl font-black text-white">
              {total}
            </div>
          </div>

          <div className="rounded-xl border border-[#2a2d35]/50 bg-[#0d0d0f]/60 p-3.5 text-center">
            <div className="flex items-center justify-center gap-1 text-[11px] text-gray-400 mb-1">
              <Trophy className="h-3.5 w-3.5 text-amber-400" />
              <span>Contest</span>
            </div>
            <div className="font-heading text-2xl font-black text-amber-300">
              {user.contestRating || '—'}
            </div>
          </div>

          <div className="rounded-xl border border-[#2a2d35]/50 bg-[#0d0d0f]/60 p-3.5 text-center">
            <div className="flex items-center justify-center gap-1 text-[11px] text-gray-400 mb-1">
              <Award className="h-3.5 w-3.5 text-cyan-400" />
              <span>Rank</span>
            </div>
            <div className="font-heading text-xl sm:text-2xl font-black text-cyan-300">
              {user.globalRanking ? `#${user.globalRanking.toLocaleString()}` : '—'}
            </div>
          </div>
        </div>

        {/* Difficulty Breakdown Bars */}
        <div className="space-y-3">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
            Difficulty Distribution
          </span>

          {/* Easy */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="font-medium text-emerald-400">Easy</span>
              <span className="font-mono text-gray-300">{stats.easy} <span className="text-gray-500">({Math.round(easyPct)}%)</span></span>
            </div>
            <div className="h-2 w-full rounded-full bg-[#202228] overflow-hidden">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-700"
                style={{ width: `${easyPct}%` }}
              />
            </div>
          </div>

          {/* Medium */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="font-medium text-amber-400">Medium</span>
              <span className="font-mono text-gray-300">{stats.medium} <span className="text-gray-500">({Math.round(medPct)}%)</span></span>
            </div>
            <div className="h-2 w-full rounded-full bg-[#202228] overflow-hidden">
              <div
                className="h-full rounded-full bg-amber-500 transition-all duration-700"
                style={{ width: `${medPct}%` }}
              />
            </div>
          </div>

          {/* Hard */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="font-medium text-rose-400">Hard</span>
              <span className="font-mono text-gray-300">{stats.hard} <span className="text-gray-500">({Math.round(hardPct)}%)</span></span>
            </div>
            <div className="h-2 w-full rounded-full bg-[#202228] overflow-hidden">
              <div
                className="h-full rounded-full bg-rose-500 transition-all duration-700"
                style={{ width: `${hardPct}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 pt-3 border-t border-[#2a2d35]/40 flex justify-between items-center text-[11px] text-gray-500">
        <span>Source: LeetCode Public GraphQL</span>
        <span className="text-emerald-400/90 font-medium">● Verified Sync</span>
      </div>
    </div>
  )
}
