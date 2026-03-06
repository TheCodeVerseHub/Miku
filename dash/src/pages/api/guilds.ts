import type { NextApiRequest, NextApiResponse } from 'next'
import { getSession } from 'next-auth/react'
import { guildHasBot } from '@/lib/database'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const session = await getSession({ req })

  if (!session || !session.accessToken) {
    return res.status(401).json({ error: 'Unauthorized' })
  }

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

    // Check which guilds have the bot
    const guildsWithStatus = adminGuilds.map((guild: any) => ({
      id: guild.id,
      name: guild.name,
      icon: guild.icon,
      memberCount: 0, // Would be fetched from bot API
      hasMiku: guildHasBot(guild.id),
    }))

    res.status(200).json(guildsWithStatus)
  } catch (error) {
    console.error('Error fetching guilds:', error)
    res.status(500).json({ error: 'Failed to fetch guilds' })
  }
}
