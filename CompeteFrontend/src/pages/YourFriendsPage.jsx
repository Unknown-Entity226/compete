import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Users, Swords, Trash2, UserPlus, Trophy, Code, Zap } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import DuelModal from '../components/duel/DuelModal'

export default function YourFriendsPage() {
  const { currentUser, friends, removeFriend } = useAuth()
  const [duelTarget, setDuelTarget] = useState(null)

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      {/* Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-[#2a2d35] mb-8 gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold text-white flex items-center gap-3">
            <Users className="h-7 w-7 text-purple-400" />
            <span>Your Friends ({friends.length})</span>
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Compare stats head-to-head, track relative rankings, and challenge your peers.
          </p>
        </div>

        <Link
          to="/friends/find"
          className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-purple-600/30 hover:bg-purple-500 transition-all self-start sm:self-auto"
        >
          <UserPlus className="h-4 w-4" />
          <span>Add New Friend</span>
        </Link>
      </div>

      {friends.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[#2a2d35] bg-[#16181c]/50 p-12 text-center space-y-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#20222a] text-gray-400">
            <Users className="h-7 w-7" />
          </div>
          <h3 className="font-heading text-lg font-bold text-white">
            No friends added yet
          </h3>
          <p className="text-xs sm:text-sm text-gray-400 max-w-sm mx-auto">
            Search for fellow developers by their LeetCode username and add them to compare your progress.
          </p>
          <Link
            to="/friends/find"
            className="inline-flex items-center gap-2 rounded-xl bg-purple-600 px-5 py-2.5 text-xs font-semibold text-white hover:bg-purple-500 transition-colors"
          >
            <UserPlus className="h-4 w-4" />
            <span>Search Friends</span>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {friends.map((friend) => {
            const stats = friend.problemStats || { total: 0 }
            return (
              <div
                key={friend.username}
                className="group rounded-2xl border border-[#2a2d35] bg-[#16181c] p-5 shadow-lg hover:border-purple-500/50 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-tr from-purple-700 to-indigo-600 font-heading text-base font-bold text-white shadow-md">
                        {friend.username?.[0]?.toUpperCase()}
                      </div>
                      <div>
                        <h3 className="font-heading text-base font-bold text-white">
                          {friend.realName || friend.username}
                        </h3>
                        <span className="text-xs text-purple-400 font-mono">
                          @{friend.username}
                        </span>
                        {friend.isMockData && (
                          <span className="mt-1 inline-block text-[10px] font-medium text-amber-300">
                            Sample profile
                          </span>
                        )}
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => removeFriend(friend.username)}
                      title="Remove Friend"
                      aria-label={`Remove ${friend.username} from friends`}
                      className="text-gray-500 hover:text-red-400 p-1 rounded hover:bg-red-950/20 transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>

                  {/* Quick stats pills */}
                  <div className="grid grid-cols-2 gap-2 mb-4">
                    <div className="rounded-lg bg-[#101115] p-2 text-center">
                      <div className="text-[10px] text-gray-400 flex items-center justify-center gap-1">
                        <Trophy className="h-3 w-3 text-amber-400" />
                        <span>Rating</span>
                      </div>
                      <div className="font-heading text-base font-bold text-amber-300">
                        {friend.contestRating ?? '—'}
                      </div>
                    </div>

                    <div className="rounded-lg bg-[#101115] p-2 text-center">
                      <div className="text-[10px] text-gray-400 flex items-center justify-center gap-1">
                        <Code className="h-3 w-3 text-purple-400" />
                        <span>Solved</span>
                      </div>
                      <div className="font-heading text-base font-bold text-white">
                        {stats.total || 0}
                      </div>
                    </div>
                  </div>

                  {friend.strongestArea && (
                    <div className="mb-4 flex items-center gap-1 text-[11px] text-purple-300 bg-purple-950/30 px-2.5 py-1 rounded-md border border-purple-900/40">
                      <Zap className="h-3 w-3 text-amber-400" />
                      <span>Strongest in <strong>{friend.strongestArea}</strong></span>
                    </div>
                  )}
                </div>

                {/* Compare CTA */}
                <button
                  type="button"
                  onClick={() => setDuelTarget(friend.username)}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-purple-600/20 border border-purple-500/40 py-2.5 text-xs font-semibold text-purple-300 hover:bg-purple-600 hover:text-white transition-all cursor-pointer"
                >
                  <Swords className="h-4 w-4" />
                  <span>Duel Head-to-Head</span>
                </button>
              </div>
            )
          })}
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
