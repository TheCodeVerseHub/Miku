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
  const page = parseInt(req.query.page as string) || 1
  const limit = 50

  if (typeof serverId !== 'string') {
    return res.status(400).json({ error: 'Invalid server ID' })
  }

  try {
    // Fetch leaderboard from bot API
    const response = await fetch(`${BOT_API_URL}/api/server/${serverId}/leaderboard?page=${page}&limit=${limit}`)
    
    if (!response.ok) {
      throw new Error('Failed to fetch leaderboard from bot API')
    }
    
    const leaderboardData = await response.json()
    
    // Fetch Discord user data for each user
    const enrichedData = await Promise.all(
      leaderboardData.data.map(async (entry: any) => {
        try {
          if (!process.env.DISCORD_BOT_TOKEN || process.env.DISCORD_BOT_TOKEN === 'your_bot_token_here') {
            console.warn('DISCORD_BOT_TOKEN not configured properly')
            return {
              ...entry,
              username: entry.userId,
              discriminator: '0000',
              avatar: null,
            }
          }

          const userResponse = await fetch(`https://discord.com/api/v10/users/${entry.userId}`, {
            headers: {
              Authorization: `Bot ${process.env.DISCORD_BOT_TOKEN}`,
            },
          })
          
          if (userResponse.ok) {
            const userData = await userResponse.json()
            return {
              ...entry,
              username: userData.username,
              discriminator: userData.discriminator || '0',
              avatar: userData.avatar,
            }
          } else {
            return {
              ...entry,
              username: entry.userId,
              discriminator: '0000',
              avatar: null,
            }
          }
        } catch (error) {
          console.error(`Error fetching user ${entry.userId}:`, error)
          return {
            ...entry,
            username: entry.userId,
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
