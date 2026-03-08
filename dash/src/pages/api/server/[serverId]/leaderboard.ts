import type { NextApiRequest, NextApiResponse } from 'next'
import { getServerSession } from 'next-auth/next'
import { authOptions } from '../../auth/[...nextauth]'

const BOT_API_URL = process.env.BOT_API_URL || process.env.API_URL || 'http://localhost:8000'

// Helper function to fetch user with timeout
async function fetchUserWithTimeout(userId: string, botToken: string): Promise<any> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 8000) // 8 second timeout per user
  
  try {
    const userResponse = await fetch(`https://discord.com/api/v10/users/${userId}`, {
      headers: {
        Authorization: `Bot ${botToken}`,
      },
      signal: controller.signal,
    })
    
    clearTimeout(timeoutId)
    
    if (userResponse.ok) {
      return await userResponse.json()
    }
    return null
  } catch (error) {
    clearTimeout(timeoutId)
    return null
  }
}

// Helper to batch fetch users with concurrency limit
async function fetchUsersInBatches(userIds: string[], botToken: string, concurrency: number = 10) {
  const results: { [key: string]: any } = {}
  
  for (let i = 0; i < userIds.length; i += concurrency) {
    const batch = userIds.slice(i, i + concurrency)
    const batchResults = await Promise.all(
      batch.map(async (userId) => {
        const userData = await fetchUserWithTimeout(userId, botToken)
        return { userId, userData }
      })
    )
    
    for (const { userId, userData } of batchResults) {
      results[userId] = userData
    }
    
    // Small delay between batches to avoid rate limits (Discord allows 50 req/s)
    if (i + concurrency < userIds.length) {
      await new Promise(resolve => setTimeout(resolve, 100))
    }
  }
  
  return results
}

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const session = await getServerSession(req, res, authOptions)

  if (!session) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const { serverId } = req.query
  const page = parseInt(req.query.page as string) || 1
  const limit = 50

  if (typeof serverId !== 'string') {
    return res.status(400).json({ error: 'Invalid server ID' })
  }

  // Check if user has access to this guild
  try {
    const accessToken = session.accessToken
    
    if (!accessToken) {
      return res.status(401).json({ error: 'Authentication token missing. Please sign out and sign in again.' })
    }

    const guildsResponse = await fetch('https://discord.com/api/v10/users/@me/guilds', {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })

    if (!guildsResponse.ok) {
      return res.status(401).json({ error: 'Failed to verify guild access. Please sign out and sign in again.' })
    }

    const userGuilds = await guildsResponse.json()
    const guild = userGuilds.find((g: any) => g.id === serverId)

    if (!guild) {
      return res.status(403).json({ error: 'You do not have access to this server' })
    }

    // Check if user has MANAGE_GUILD permission (0x20) or is owner
    const permissions = BigInt(guild.permissions)
    const hasManageGuild = (permissions & BigInt(0x20)) === BigInt(0x20)
    const hasPermission = guild.owner || hasManageGuild

    if (!hasPermission) {
      return res.status(403).json({ error: 'You do not have permission to manage this server' })
    }
  } catch (error) {
    console.error('Error checking guild permissions:', error)
    return res.status(500).json({ error: 'Failed to verify permissions' })
  }

  try {
    // Fetch leaderboard from bot API with timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000) // 5 second timeout
    
    const response = await fetch(`${BOT_API_URL}/api/server/${serverId}/leaderboard?page=${page}&limit=${limit}`, {
      signal: controller.signal,
    })
    
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error('Failed to fetch leaderboard from bot API')
    }
    
    const leaderboardData = await response.json()
    
    // Fetch Discord user data for each user (with batching and concurrency control)
    const botToken = process.env.DISCORD_BOT_TOKEN
    const hasValidToken = botToken && botToken !== 'your_bot_token_here'
    
    if (!hasValidToken) {
      // No token, return with placeholder usernames
      const enrichedData = leaderboardData.data.map((entry: any) => ({
        ...entry,
        username: `User ${entry.userId}`,
        discriminator: '0000',
        avatar: null,
      }))
      
      return res.status(200).json({
        data: enrichedData,
        page: leaderboardData.page,
        totalPages: leaderboardData.totalPages,
        total: leaderboardData.total,
      })
    }

    // Fetch users in controlled batches
    const userIds = leaderboardData.data.map((entry: any) => entry.userId)
    const userDataMap = await fetchUsersInBatches(userIds, botToken, 10)
    
    const enrichedData = leaderboardData.data.map((entry: any) => {
      const userData = userDataMap[entry.userId]
      
      if (userData) {
        return {
          ...entry,
          username: userData.username || `User ${entry.userId}`,
          discriminator: userData.discriminator || '0',
          avatar: userData.avatar,
        }
      } else {
        return {
          ...entry,
          username: `User ${entry.userId}`,
          discriminator: '0000',
          avatar: null,
        }
      }
    })

    res.status(200).json({
      data: enrichedData,
      page: leaderboardData.page,
      totalPages: leaderboardData.totalPages,
      total: leaderboardData.total,
    })
  } catch (error) {
    console.error('Error fetching leaderboard:', error)
    res.status(500).json({ error: 'Failed to fetch leaderboard' })
  }
}
