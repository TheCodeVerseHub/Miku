import Database from 'better-sqlite3'
import path from 'path'

// Database path - points to the bot's database
const DB_PATH = path.join(process.cwd(), '..', 'data', 'leveling.db')

// Get database instance
export function getDatabase() {
  try {
    const db = new Database(DB_PATH, { readonly: true })
    return db
  } catch (error) {
    console.error('Failed to open database:', error)
    throw new Error('Database connection failed')
  }
}

// Check if a guild has the bot (has any data in database)
export function guildHasBot(guildId: string): boolean {
  const db = getDatabase()
  try {
    const result = db.prepare('SELECT COUNT(*) as count FROM user_levels WHERE guild_id = ?').get(guildId) as { count: number }
    return result.count > 0
  } finally {
    db.close()
  }
}

// Get server statistics
export function getServerStats(guildId: string) {
  const db = getDatabase()
  try {
    // Get aggregate stats
    const stats = db.prepare(`
      SELECT 
        COUNT(*) as activeUsers,
        SUM(xp) as totalXP,
        AVG(level) as averageLevel
      FROM user_levels 
      WHERE guild_id = ?
    `).get(guildId) as {
      activeUsers: number
      totalXP: number
      averageLevel: number
    }

    // Get top user
    const topUser = db.prepare(`
      SELECT user_id, level, xp
      FROM user_levels 
      WHERE guild_id = ? 
      ORDER BY xp DESC 
      LIMIT 1
    `).get(guildId) as {
      user_id: string
      level: number
      xp: number
    } | undefined

    return {
      totalMembers: stats.activeUsers || 0,
      totalXP: stats.totalXP || 0,
      activeUsers: stats.activeUsers || 0,
      averageLevel: stats.averageLevel || 0,
      topUser: topUser ? {
        userId: topUser.user_id,
        level: topUser.level,
      } : null
    }
  } finally {
    db.close()
  }
}

// Get leaderboard
export function getLeaderboard(guildId: string, page: number = 1, limit: number = 50) {
  const db = getDatabase()
  try {
    const offset = (page - 1) * limit

    // Get total count
    const totalResult = db.prepare('SELECT COUNT(*) as count FROM user_levels WHERE guild_id = ?').get(guildId) as { count: number }
    const total = totalResult.count

    // Get leaderboard page
    const rows = db.prepare(`
      SELECT 
        user_id,
        xp,
        level,
        messages
      FROM user_levels 
      WHERE guild_id = ?
      ORDER BY xp DESC
      LIMIT ? OFFSET ?
    `).all(guildId, limit, offset) as Array<{
      user_id: number
      xp: number
      level: number
      messages: number
    }>

    const data = rows.map((row, index) => ({
      rank: offset + index + 1,
      userId: row.user_id.toString(),
      level: row.level,
      xp: row.xp,
      totalXp: row.xp,
      messages: row.messages,
    }))

    return {
      data,
      page,
      totalPages: Math.ceil(total / limit),
      total,
    }
  } finally {
    db.close()
  }
}

// Get user data
export function getUserData(userId: string, guildId: string) {
  const db = getDatabase()
  try {
    const user = db.prepare(`
      SELECT 
        user_id,
        xp,
        level,
        messages,
        last_message_time
      FROM user_levels 
      WHERE user_id = ? AND guild_id = ?
    `).get(userId, guildId) as {
      user_id: number
      xp: number
      level: number
      messages: number
      last_message_time: number
    } | undefined

    if (!user) {
      return null
    }

    // Get user's rank
    const rankResult = db.prepare(`
      SELECT COUNT(*) + 1 as rank
      FROM user_levels
      WHERE guild_id = ? AND xp > ?
    `).get(guildId, user.xp) as { rank: number }

    return {
      userId: user.user_id.toString(),
      level: user.level,
      xp: user.xp,
      totalXp: user.xp,
      messages: user.messages,
      rank: rankResult.rank,
      lastMessageTime: user.last_message_time,
    }
  } finally {
    db.close()
  }
}

// Get all guilds that have bot data
export function getAllGuildsWithBot(): string[] {
  const db = getDatabase()
  try {
    const guilds = db.prepare(`
      SELECT DISTINCT guild_id 
      FROM user_levels
    `).all() as Array<{ guild_id: number }>

    return guilds.map(g => g.guild_id.toString())
  } finally {
    db.close()
  }
}
