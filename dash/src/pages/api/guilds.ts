import type { NextApiRequest, NextApiResponse } from 'next'
import { getSession } from 'next-auth/react'

const BOT_API_URL = process.env.BOT_API_URL || process.env.API_URL || 'http://localhost:8000'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const session = await getSession({ req })

  if (!session || !session.accessToken) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

  console.log(`[DEBUG] BOT_API_URL: ${BOT_API_URL}`)

  try {
    // Fetch user's guilds from Discord API
    const discordResponse = await fetch('https://discord.com/api/users/@me/guilds', {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    })

    if (!discordResponse.ok) {
      throw new Error('Failed to fetch guilds from Discord')
    }

    const guilds = await discordResponse.json()

    // Filter guilds where user has admin permissions
    const adminGuilds = guilds.filter((guild: any) => {
      const permissions = parseInt(guild.permissions)
      return (permissions & 0x8) === 0x8 || (permissions & 0x20) === 0x20
    })

    // Check which guilds have the bot by querying bot API
    const guildsWithStatus = await Promise.all(
      adminGuilds.map(async (guild: any) => {
        let hasMiku = false
        try {
          // Add timeout to prevent hanging
          const controller = new AbortController()
          const timeoutId = setTimeout(() => controller.abort(), 5000) // 5 second timeout
          
          const botResponse = await fetch(`${BOT_API_URL}/api/guild/${guild.id}/has-bot`, {
            signal: controller.signal
          })
          clearTimeout(timeoutId)
          
          if (botResponse.ok) {
            const data = await botResponse.json()
            hasMiku = data.hasMiku
          }
        } catch (error) {
          console.error(`Error checking bot status for guild ${guild.id}:`, error)
        }

        return {
          id: guild.id,
          name: guild.name,
          icon: guild.icon,
          memberCount: 0,
          hasMiku,
        }
      })
    )

    // Return the guilds with their status
    return res.status(200).json(guildsWithStatus)
  } catch (error) {
    console.error('Error fetching guilds:', error)
    return res.status(500).json({ error: 'Failed to fetch guilds' })
  }
}
