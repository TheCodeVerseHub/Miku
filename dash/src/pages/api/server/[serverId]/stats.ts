import type { NextApiRequest, NextApiResponse } from 'next'
import { getSession } from 'next-auth/react'
import { getServerStats } from '@/lib/database'

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
    // Fetch stats from database
    const dbStats = getServerStats(serverId)
    
    // If there's a top user, fetch their Discord username
    let topUser = null
    if (dbStats.topUser) {
      try {
        if (!process.env.DISCORD_BOT_TOKEN || process.env.DISCORD_BOT_TOKEN === 'your_bot_token_here') {
          console.warn('DISCORD_BOT_TOKEN not configured properly')
          topUser = {
            username: `${dbStats.topUser.userId}`,
            level: dbStats.topUser.level,
          }
        } else {
          const userResponse = await fetch(`https://discord.com/api/v10/users/${dbStats.topUser.userId}`, {
            headers: {
              Authorization: `Bot ${process.env.DISCORD_BOT_TOKEN}`,
            },
          })
          
          if (userResponse.ok) {
            const userData = await userResponse.json()
            topUser = {
              username: `${userData.username}#${userData.discriminator}`,
              level: dbStats.topUser.level,
            }
          } else {
            const errorData = await userResponse.text()
            console.error(`Discord API error for top user: ${userResponse.status} - ${errorData}`)
            // Fallback if user fetch fails - use user ID
            topUser = {
              username: `${dbStats.topUser.userId}`,
              level: dbStats.topUser.level,
            }
          }
        }
      } catch (error) {
        console.error('Error fetching top user:', error)
        // Fallback - use user ID
        topUser = {
          username: `${dbStats.topUser.userId}`,
          level: dbStats.topUser.level,
        }
      }
    }
    
    const stats = {
      totalMembers: dbStats.totalMembers || 0,
      totalXP: dbStats.totalXP || 0,
      activeUsers: dbStats.activeUsers || 0,
      averageLevel: dbStats.averageLevel ? Math.round(dbStats.averageLevel * 10) / 10 : 0,
      topUser,
    }

    res.status(200).json(stats)
  } catch (error) {
    console.error('Error fetching server stats:', error)
    res.status(500).json({ error: 'Failed to fetch server stats' })
  }
}

