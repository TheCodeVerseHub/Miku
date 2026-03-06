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
          // Fallback if user fetch fails
          topUser = {
            username: `User#${dbStats.topUser.userId.slice(-4)}`,
            level: dbStats.topUser.level,
          }
        }
      } catch (error) {
        console.error('Error fetching top user:', error)
        // Fallback
        topUser = {
          username: `User#${dbStats.topUser.userId.slice(-4)}`,
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

