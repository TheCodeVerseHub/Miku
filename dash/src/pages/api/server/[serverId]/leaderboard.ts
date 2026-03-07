import type { NextApiRequest, NextApiResponse } from 'next'
import { getSession } from 'next-auth/react'

const BOT_API_URL = process.env.BOT_API_URL || process.env.API_URL || 'http://localhost:8000'

// Helper function to fetch user with timeout
async function fetchUserWithTimeout(userId: string, botToken: string): Promise<any> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 2000) // 2 second timeout per user
  
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

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const session = await getSession({ req })

  if (!session) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const { serverId } = req.query
  const page = parseInt(req.query.page as string) || 1
  const limit = 50

  if (typeof serverId !== 'string') {
    return res.status(400).json({ error: 'Invalid server ID' })
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
    
    // Fetch Discord user data for each user (with individual timeouts)
    const botToken = process.env.DISCORD_BOT_TOKEN
    const hasValidToken = botToken && botToken !== 'your_bot_token_here'
    
    const enrichedData = await Promise.all(
      leaderboardData.data.map(async (entry: any) => {
        if (!hasValidToken) {
          return {
            ...entry,
            username: `User ${entry.userId}`,
            discriminator: '0000',
            avatar: null,
          }
        }

        try {
          const userData = await fetchUserWithTimeout(entry.userId, botToken)
          
          if (userData) {
            return {
              ...entry,
              username: userData.username,
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
        } catch (error) {
          return {
            ...entry,
            username: `User ${entry.userId}`,
            discriminator: '0000',
            avatar: null,
          }
        }
      })
    )

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
