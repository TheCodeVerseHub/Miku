import type { NextApiRequest, NextApiResponse } from 'next'
import { getServerSession } from 'next-auth/next'
import { authOptions } from './auth/[...nextauth]'

const BOT_API_URL = process.env.BOT_API_URL || process.env.API_URL || 'http://localhost:8000'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const session = await getServerSession(req, res, authOptions)

  if (!session || !session.accessToken) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  console.log(`[DEBUG] BOT_API_URL: ${BOT_API_URL}`)

  try {
    // Fetch user's guilds from Discord API with timeout
    const controller = new AbortController()
    const discordTimeoutId = setTimeout(() => controller.abort(), 10000) // 10 second timeout
    
    const discordResponse = await fetch('https://discord.com/api/users/@me/guilds', {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
      signal: controller.signal,
    })
    
    clearTimeout(discordTimeoutId)

    if (!discordResponse.ok) {
      throw new Error('Failed to fetch guilds from Discord')
    }

    const guilds = await discordResponse.json()

    // Filter guilds where user has admin permissions
    const adminGuilds = guilds.filter((guild: any) => {
      const permissions = parseInt(guild.permissions)
      return (permissions & 0x8) === 0x8 || (permissions & 0x20) === 0x20
    })

    // Batch check all guilds at once (much faster!)
    let botStatusMap: Record<string, boolean> = {}
    
    try {
      const batchController = new AbortController()
      const batchTimeoutId = setTimeout(() => batchController.abort(), 10000) // 10 second timeout for cold starts
      
      const guildIds = adminGuilds.map((g: any) => g.id)
      
      const batchResponse = await fetch(`${BOT_API_URL}/api/guilds/batch-check`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(guildIds),
        signal: batchController.signal,
      })
      
      clearTimeout(batchTimeoutId)
      
      if (batchResponse.ok) {
        botStatusMap = await batchResponse.json()
      } else {
        console.warn(`Batch check returned ${batchResponse.status}: ${batchResponse.statusText}`)
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        console.warn('Batch check timed out after 10 seconds - API may be on cold start')
      } else {
        console.error('Error batch checking bot status:', error)
      }
      // Continue without bot status rather than failing completely
    }

    // Map guilds with their bot status
    const guildsWithStatus = adminGuilds.map((guild: any) => ({
      id: guild.id,
      name: guild.name,
      icon: guild.icon,
      memberCount: guild.approximate_member_count || 0,
      hasMiku: botStatusMap[guild.id] || false,
    }))

    // Return the guilds with their status
    return res.status(200).json(guildsWithStatus)
  } catch (error) {
    console.error('Error fetching guilds:', error)
    return res.status(500).json({ error: 'Failed to fetch guilds' })
  }
}
