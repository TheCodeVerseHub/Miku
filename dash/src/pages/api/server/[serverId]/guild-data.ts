import type { NextApiRequest, NextApiResponse } from 'next'
import { getServerSession } from 'next-auth/next'
import { authOptions } from '../../auth/[...nextauth]'

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
    const accessToken = (session as any).accessToken
    
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
    // Fetch guild channels
    const channelsResponse = await fetch(
      `https://discord.com/api/v10/guilds/${serverId}/channels`,
      {
        headers: {
          Authorization: `Bot ${process.env.DISCORD_BOT_TOKEN}`,
        },
      }
    )

    if (!channelsResponse.ok) {
      return res.status(500).json({ error: 'Failed to fetch channels' })
    }

    const channels = await channelsResponse.json()

    // Filter text channels only (type 0 = GUILD_TEXT)
    const textChannels = channels
      .filter((channel: any) => channel.type === 0)
      .map((channel: any) => ({
        id: channel.id,
        name: channel.name,
        position: channel.position,
      }))
      .sort((a: any, b: any) => a.position - b.position)

    // Fetch guild roles
    const rolesResponse = await fetch(
      `https://discord.com/api/v10/guilds/${serverId}/roles`,
      {
        headers: {
          Authorization: `Bot ${process.env.DISCORD_BOT_TOKEN}`,
        },
      }
    )

    if (!rolesResponse.ok) {
      return res.status(500).json({ error: 'Failed to fetch roles' })
    }

    const roles = await rolesResponse.json()

    // Filter out @everyone role and managed roles (bot roles)
    const assignableRoles = roles
      .filter((role: any) => role.name !== '@everyone' && !role.managed)
      .map((role: any) => ({
        id: role.id,
        name: role.name,
        color: role.color,
        position: role.position,
      }))
      .sort((a: any, b: any) => b.position - a.position)

    res.status(200).json({
      channels: textChannels,
      roles: assignableRoles,
    })
  } catch (error) {
    console.error('Error fetching guild data:', error)
    res.status(500).json({ error: 'Internal server error' })
  }
}
