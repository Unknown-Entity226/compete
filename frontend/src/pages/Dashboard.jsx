import { useState } from 'react'
import { Sparkles, Swords } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import UserStatsCard from '../components/dashboard/UserStatsCard'
import TopicBreakdownChart from '../components/dashboard/TopicBreakdownChart'
import FriendsRankingStrip from '../components/friends/FriendsRankingStrip'
import DuelModal from '../components/duel/DuelModal'

export default function Dashboard() {
  const { currentUser, friends } = useAuth()
  const [duelTarget, setDuelTarget] = useState(null)
  const quickMatchTarget = friends.find(
    (friend) => friend.username.toLowerCase() !== currentUser?.username?.toLowerCase()
  )?.username

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8 animate-in fade-in duration-300">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#2a2d35] gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-purple-400 uppercase tracking-wider font-heading mb-1">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Developer Arena</span>
          </div>
          <h1 className="font-heading text-2xl sm:text-3xl font-extrabold text-white">
            Welcome back, {currentUser?.realName || currentUser?.username} 👋
          </h1>
          <p className="text-xs sm:text-sm text-gray-400 mt-0.5">
            Your connected LeetCode stats and topic breakdown.
          </p>
        </div>

        {/* Quick Duel Trigger */}
        <button
          type="button"
          onClick={() => quickMatchTarget && setDuelTarget(quickMatchTarget)}
          disabled={!quickMatchTarget}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-purple-600/30 hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-50 transition-all self-start sm:self-auto cursor-pointer"
        >
          <Swords className="h-4 w-4" />
          <span>{quickMatchTarget ? `Quick Match vs ${quickMatchTarget}` : 'Add a friend to start a match'}</span>
        </button>
      </div>

      {/* Main Stats Grid: Current User Stats + Interactive Topic Graph */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
        <UserStatsCard user={currentUser} />
        <TopicBreakdownChart topicStats={currentUser?.topicStats} />
      </div>

      {/* Current Ranking Among Friends */}
      <FriendsRankingStrip onCompare={(targetUsername) => setDuelTarget(targetUsername)} />

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
