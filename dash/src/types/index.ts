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

export interface RoleReward {
  level: number
  roleId: string
  roleName: string
  roleColor: number
}

export interface GuildSettings {
  levelupChannelId: string | null
  levelupChannelName: string | null
  roleRewards: RoleReward[]
}

export interface Channel {
  id: string
  name: string
  position: number
}

export interface Role {
  id: string
  name: string
  color: number
  position: number
}

export interface GuildData {
  channels: Channel[]
  roles: Role[]
}
