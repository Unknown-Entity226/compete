import { api } from './api'
import mockState from '../mockData/competestate.json'

const mockUsers = mockState.competitionData.users

function findMockUser(username) {
  if (typeof username !== 'string') return undefined
  return mockUsers.find((user) => user.leetcodeId.toLowerCase() === username.toLowerCase())
}

function createMockComparison(firstUser, secondUser) {
  const firstRating = firstUser.contestRating || 0
  const secondRating = secondUser.contestRating || 0
  const calculateBreakdown = (user) => {
    const ratingScore = Math.max(0, ((user.contestRating || 0) - 1200) * 0.5)
    const difficultyScore = user.problemStats.easy + user.problemStats.medium * 3 + user.problemStats.hard * 6
    const totalScore = ratingScore + difficultyScore
    return { ratingScore, difficultyScore, velocityScore: 0, streakScore: 0, totalScore }
  }

  const firstBreakdown = calculateBreakdown(firstUser)
  const secondBreakdown = calculateBreakdown(secondUser)
  const winner = firstBreakdown.totalScore === secondBreakdown.totalScore
    ? 'TIE'
    : firstBreakdown.totalScore > secondBreakdown.totalScore
      ? firstUser.leetcodeId
      : secondUser.leetcodeId

  return {
    isMockData: true,
    comparisonId: `${firstUser.leetcodeId}-vs-${secondUser.leetcodeId}`,
    lastUpdated: mockState.competitionData.lastUpdated,
    winner,
    score: {
      [firstUser.leetcodeId]: firstBreakdown.totalScore,
      [secondUser.leetcodeId]: secondBreakdown.totalScore,
    },
    scoreBreakdown: {
      [firstUser.leetcodeId]: firstBreakdown,
      [secondUser.leetcodeId]: secondBreakdown,
    },
    metrics: {
      ratingDiff: firstRating - secondRating,
      totalSolvedDiff: firstUser.problemStats.total - secondUser.problemStats.total,
      easyDiff: firstUser.problemStats.easy - secondUser.problemStats.easy,
      mediumDiff: firstUser.problemStats.medium - secondUser.problemStats.medium,
      hardDiff: firstUser.problemStats.hard - secondUser.problemStats.hard,
      velocity7dDiff: 0,
      weeklySolvedDiff: 0,
      streakDiff: 0,
      higherRankedUser: winner === 'TIE' ? null : winner,
    },
    competitionData: {
      lastUpdated: mockState.competitionData.lastUpdated,
      users: [firstUser, secondUser],
    },
  }
}

export const comparisonService = {
  /**
   * Fetch single user normalized profile & statistics.
   */
  async getUserProfile(username) {
    try {
      return await api.get(`/api/users/${encodeURIComponent(username)}`)
    } catch (err) {
      const mockUser = findMockUser(username)
      if (mockUser) {
        return {
          username: mockUser.leetcodeId,
          contestRating: mockUser.contestRating,
          problemStats: mockUser.problemStats,
          strongestArea: mockUser.strongestArea,
          topicStats: mockUser.topicStats,
          lastUpdated: mockState.competitionData.lastUpdated,
          isMockData: true,
        }
      }
      throw err
    }
  },

  /**
   * Compare two users head-to-head.
   */
  async compareUsers(firstUser, secondUser) {
    try {
      return await api.get(`/api/compare/${encodeURIComponent(firstUser)}/${encodeURIComponent(secondUser)}`)
    } catch (err) {
      const firstMockUser = findMockUser(firstUser)
      const secondMockUser = findMockUser(secondUser)
      if (firstMockUser && secondMockUser && firstMockUser.leetcodeId !== secondMockUser.leetcodeId) {
        return createMockComparison(firstMockUser, secondMockUser)
      }
      throw err
    }
  },

  async getUserHistory(username) {
    return await api.get(`/api/users/${encodeURIComponent(username)}/history`)
  },

  async getUserActivity(username) {
    return await api.get(`/api/users/${encodeURIComponent(username)}/activity`)
  },
}
