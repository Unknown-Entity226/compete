import { createContext, useContext, useEffect, useState } from 'react'

const AuthContext = createContext(null)

const DEFAULT_FRIENDS = []

function readStoredValue(key, fallback) {
  try {
    const stored = localStorage.getItem(key)
    return stored ? JSON.parse(stored) : fallback
  } catch {
    return fallback
  }
}

function readStoredUser() {
  const user = readStoredValue('compete_user', null)
  return normalizeUser(user)
}

function normalizeFriends(value) {
  if (!Array.isArray(value)) return DEFAULT_FRIENDS
  const friendsByUsername = new Map()
  value.forEach((friend) => {
    const normalized = normalizeUser(friend)
    if (normalized) friendsByUsername.set(normalized.username.toLowerCase(), normalized)
  })
  return [...friendsByUsername.values()]
}

function normalizeUser(user) {
  if (!user || typeof user.username !== 'string' || !user.username.trim()) return null
  const toNumber = (value, fallback = 0) => {
    const number = Number(value)
    return Number.isFinite(number) ? number : fallback
  }
  const problemStats = user.problemStats || {}
  const easy = toNumber(problemStats.easy)
  const medium = toNumber(problemStats.medium)
  const hard = toNumber(problemStats.hard)
  const rating = user.contestRating == null ? null : toNumber(user.contestRating, null)
  const ranking = user.globalRanking == null ? null : toNumber(user.globalRanking, null)

  return {
    ...user,
    username: user.username.trim(),
    realName: typeof user.realName === 'string' ? user.realName : null,
    contestRating: rating,
    globalRanking: ranking,
    problemStats: {
      total: toNumber(problemStats.total, easy + medium + hard),
      easy,
      medium,
      hard,
    },
    topicStats: Array.isArray(user.topicStats) ? user.topicStats : [],
  }
}

function writeStoredValue(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Keep the in-memory session usable when browser storage is unavailable.
  }
}

function removeStoredValue(key) {
  try {
    localStorage.removeItem(key)
  } catch {
    // Keep the in-memory session usable when browser storage is unavailable.
  }
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(readStoredUser)
  const [friends, setFriends] = useState(() => normalizeFriends(readStoredValue('compete_friends', DEFAULT_FRIENDS)))

  useEffect(() => {
    writeStoredValue('compete_friends', friends)
  }, [friends])

  const login = (userData) => {
    const normalizedUser = normalizeUser(userData)
    if (!normalizedUser) return
    writeStoredValue('compete_user', normalizedUser)
    setCurrentUser(normalizedUser)
  }

  const logout = () => {
    removeStoredValue('compete_user')
    setCurrentUser(null)
  }

  const addFriend = (friendObj) => {
    if (typeof friendObj?.username !== 'string' || !friendObj.username.trim()) return
    setFriends((prev) => {
      const exists = prev.some(
        (f) => f.username.toLowerCase() === friendObj.username.toLowerCase()
      )
      if (exists) return prev
      return [...prev, friendObj]
    })
  }

  const removeFriend = (username) => {
    if (typeof username !== 'string' || !username) return
    setFriends((prev) => {
      const updated = prev.filter(
        (f) => f.username.toLowerCase() !== username.toLowerCase()
      )
      return updated
    })
  }

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        isLoggedIn: Boolean(currentUser),
        login,
        logout,
        friends,
        addFriend,
        removeFriend,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
