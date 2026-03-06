export interface User {
  id: string
  username: string
  discriminator: string
  avatar: string | null
  level: number
  xp: number
  totalXp: number
  rank: number
}

export interface Guild {
  id: string
  name: string
  icon: string | null
  memberCount: number
  hasMiku: boolean
}

export interface ServerStats {
  totalMembers: number
  totalXP: number
  activeUsers: number
  averageLevel: number
  topUser: {
    username: string
    level: number
  }
}

export interface LeaderboardEntry {
  rank: number
  userId: string
  username: string
  discriminator: string
  avatar: string | null
  level: number
  xp: number
  totalXp: number
}

export interface LeaderboardResponse {
  data: LeaderboardEntry[]
  page: number
  totalPages: number
  total: number
}
