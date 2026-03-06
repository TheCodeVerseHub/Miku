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

  try {
    // In production, fetch from your Python bot's API endpoint
    // const response = await fetch(`${process.env.API_URL}/api/server/${serverId}/stats`)
    
    // Mock data for now
    const stats = {
      totalMembers: 1234,
      totalXP: 5678900,
      activeUsers: 432,
      averageLevel: 12.5,
      topUser: {
        username: 'TopPlayer#1234',
        level: 45,
      },
    }

    res.status(200).json(stats)
  } catch (error) {
    console.error('Error fetching server stats:', error)
    res.status(500).json({ error: 'Failed to fetch server stats' })
  }
}
