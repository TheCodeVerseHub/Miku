import type { NextApiRequest, NextApiResponse } from 'next'
import { getSession } from 'next-auth/react'
import { getLeaderboard } from '@/lib/database'

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
    // Fetch leaderboard from database
    const leaderboardData = getLeaderboard(serverId, page, limit)
    
    // Fetch Discord user data for each user
    const enrichedData = await Promise.all(
      leaderboardData.data.map(async (entry) => {
        try {
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
            // Fallback if user fetch fails
            return {
              ...entry,
              username: `User`,
              discriminator: entry.userId.slice(-4),
              avatar: null,
            }
          }
        } catch (error) {
          console.error(`Error fetching user ${entry.userId}:`, error)
          // Fallback
          return {
            ...entry,
            username: `User`,
            discriminator: entry.userId.slice(-4),
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

