import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor for auth token
api.interceptors.request.use(
  (config) => {
    // Add auth token here if needed
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// API endpoints
export const endpoints = {
  // Server stats
  getServerStats: (serverId: string) => `/api/server/${serverId}/stats`,
  getLeaderboard: (serverId: string, page: number = 1) =>
    `/api/server/${serverId}/leaderboard?page=${page}`,

  // User data
  getUserData: (userId: string, guildId: string) =>
    `/api/user/${userId}?guild=${guildId}`,

  // Admin endpoints
  setUserLevel: (userId: string, guildId: string, level: number) =>
    `/api/admin/setlevel`,
  addUserXP: (userId: string, guildId: string, xp: number) => `/api/admin/addxp`,
  resetUserLevel: (userId: string, guildId: string) => `/api/admin/resetlevel`,
}

export default api
