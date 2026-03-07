import type { NextApiRequest, NextApiResponse } from 'next'
import { getSession } from 'next-auth/react'

const BOT_API_URL = process.env.BOT_API_URL || process.env.API_URL || 'http://localhost:8000'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const session = await getSession({ req })

  if (!session) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const { serverId } = req.query

  if (typeof serverId !== 'string') {
    return res.status(400).json({ error: 'Invalid server ID' })
  }

  try {
    // Fetch stats from bot API with timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000) // 5 second timeout
    
    const response = await fetch(`${BOT_API_URL}/api/server/${serverId}/stats`, {
      signal: controller.signal,
    })
    
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error('Failed to fetch stats from bot API')
    }
    
    const dbStats = await response.json()
    
    // If there's a top user, fetch their Discord username
    let topUser = null
    if (dbStats.topUser) {
      try {
        if (!process.env.DISCORD_BOT_TOKEN || process.env.DISCORD_BOT_TOKEN === 'your_bot_token_here') {
          console.warn('DISCORD_BOT_TOKEN not configured properly')
          topUser = {
            username: `User ${dbStats.topUser.userId}`,
            level: dbStats.topUser.level,
          }
        } else {
          const userController = new AbortController()
          const userTimeoutId = setTimeout(() => userController.abort(), 3000) // 3 second timeout
          
          const userResponse = await fetch(`https://discord.com/api/v10/users/${dbStats.topUser.userId}`, {
            headers: {
              Authorization: `Bot ${process.env.DISCORD_BOT_TOKEN}`,
            },
            signal: userController.signal,
          })
          
          clearTimeout(userTimeoutId)
          
          if (userResponse.ok) {
            const userData = await userResponse.json()
            topUser = {
              username: userData.discriminator === '0' 
                ? userData.username 
                : `${userData.username}#${userData.discriminator}`,
              level: dbStats.topUser.level,
            }
          } else {
            topUser = {
              username: `User ${dbStats.topUser.userId}`,
              level: dbStats.topUser.level,
            }
          }
        }
      } catch (error) {
        console.error('Error fetching top user:', error)
        topUser = {
          username: `User ${dbStats.topUser.userId}`,
          level: dbStats.topUser.level,
        }
      }
    }
    
    const stats = {
      totalMembers: dbStats.totalMembers || 0,
      totalXP: dbStats.totalXP || 0,
      activeUsers: dbStats.activeUsers || 0,
      averageLevel: dbStats.averageLevel || 0,
      topUser,
    }

    res.status(200).json(stats)
  } catch (error) {
    console.error('Error fetching server stats:', error)
    res.status(500).json({ error: 'Failed to fetch server stats' })
  }
}
