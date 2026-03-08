import type { NextApiRequest, NextApiResponse } from 'next'
import { getServerSession } from 'next-auth/next'
import { authOptions } from '../../auth/[...nextauth]'

const BOT_API_URL = process.env.BOT_API_URL || process.env.API_URL || 'http://localhost:8000'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const session = await getServerSession(req, res, authOptions)

  if (!session) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  const { serverId } = req.query

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
