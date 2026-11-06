import { createContext, useContext, useEffect, useState } from 'react'

const AuthContext = createContext(null)

const DEFAULT_FRIENDS = [
  {
    username: 'binary_ninja',
    realName: 'Binary Ninja',
    contestRating: 1720,
    problemStats: { total: 415, easy: 190, medium: 200, hard: 25 },
    strongestArea: 'Trees',
  },
]

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
  return user && typeof user.username === 'string' && user.username.trim() ? user : null
}

function normalizeFriends(value) {
  if (!Array.isArray(value)) return DEFAULT_FRIENDS
  return value.filter((friend) => friend && typeof friend.username === 'string' && friend.username.trim())
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
    if (!userData || typeof userData.username !== 'string' || !userData.username.trim()) return
    writeStoredValue('compete_user', userData)
    setCurrentUser(userData)
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
