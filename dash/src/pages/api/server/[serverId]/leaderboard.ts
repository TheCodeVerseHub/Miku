import type { NextApiRequest, NextApiResponse } from 'next'
import { getSession } from 'next-auth/react'

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

  try {
    // In production, fetch from your Python bot's API endpoint
    // const response = await fetch(`${process.env.API_URL}/api/server/${serverId}/leaderboard?page=${page}&limit=${limit}`)
    
    // Mock data for now
    const leaderboard = Array.from({ length: limit }, (_, i) => ({
      rank: (page - 1) * limit + i + 1,
      userId: `${i}`,
      username: `User${i + 1}`,
      discriminator: String(i).padStart(4, '0'),
      avatar: null,
      level: Math.floor(50 - i * 0.5),
      xp: Math.floor(100000 - i * 1000),
      totalXp: Math.floor(150000 - i * 1500),
    }))

    res.status(200).json({
      data: leaderboard,
      page,
      totalPages: 10,
      total: 500,
    })
  } catch (error) {
    console.error('Error fetching leaderboard:', error)
    res.status(500).json({ error: 'Failed to fetch leaderboard' })
  }
}
