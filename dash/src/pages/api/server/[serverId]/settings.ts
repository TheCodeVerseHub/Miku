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

  if (typeof serverId !== 'string') {
    return res.status(400).json({ error: 'Invalid server ID' })
  }

  // Check if user has access to this guild
  try {
    const accessToken = (session as any).accessToken
    console.log('[API] Checking guild access for user, serverId:', serverId, 'hasToken:', !!accessToken)
    
    if (!accessToken) {
      console.error('[API] No access token in session')
      return res.status(401).json({ error: 'Authentication token missing. Please sign out and sign in again.' })
    }

    const guildsResponse = await fetch('https://discord.com/api/v10/users/@me/guilds', {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })

    if (!guildsResponse.ok) {
      console.error('[API] Failed to fetch user guilds:', guildsResponse.status, guildsResponse.statusText)
      return res.status(401).json({ error: 'Failed to verify guild access. Please sign out and sign in again.' })
    }

    const userGuilds = await guildsResponse.json()
    const guild = userGuilds.find((g: any) => g.id === serverId)

    if (!guild) {
      console.warn('[API] User does not have access to guild:', serverId)
      return res.status(403).json({ error: 'You do not have access to this server' })
    }

    // Check if user has MANAGE_GUILD permission (0x20) or is owner
    const permissions = BigInt(guild.permissions)
    const hasManageGuild = (permissions & BigInt(0x20)) === BigInt(0x20)
    const hasPermission = guild.owner || hasManageGuild

    console.log('[API] Guild access check:', { owner: guild.owner, hasManageGuild, hasPermission })

    if (!hasPermission) {
      return res.status(403).json({ error: 'You do not have permission to manage this server' })
    }
  } catch (error) {
    console.error('[API] Error checking guild permissions:', error)
    return res.status(500).json({ error: 'Failed to verify permissions' })
  }

  try {
    if (req.method === 'GET') {
      // Get guild settings from bot API
      const response = await fetch(`${BOT_API_URL}/api/server/${serverId}/settings`)
      
      if (!response.ok) {
        throw new Error('Failed to fetch settings from bot API')
      }
      
      const settings = await response.json()

      // Fetch channel info if set
      let channelInfo = null
      if (settings.levelupChannelId) {
        try {
          const channelResponse = await fetch(
            `https://discord.com/api/v10/channels/${settings.levelupChannelId}`,
            {
              headers: {
                Authorization: `Bot ${process.env.DISCORD_BOT_TOKEN}`,
              },
            }
          )
          if (channelResponse.ok) {
            channelInfo = await channelResponse.json()
          }
        } catch (error) {
          console.error('Error fetching channel info:', error)
        }
      }

      // Fetch guild info for roles
      let guildInfo = null
      try {
        const guildResponse = await fetch(
          `https://discord.com/api/v10/guilds/${serverId}`,
          {
            headers: {
              Authorization: `Bot ${process.env.DISCORD_BOT_TOKEN}`,
            },
          }
        )
        if (guildResponse.ok) {
          guildInfo = await guildResponse.json()
        }
      } catch (error) {
        console.error('Error fetching guild info:', error)
      }

      // Get role names
      const roleRewardsWithNames = settings.roleRewards.map((rr: any) => {
        const role = guildInfo?.roles?.find((r: any) => r.id === rr.roleId)
        return {
          level: rr.level,
          roleId: rr.roleId,
          roleName: role?.name || 'Unknown Role',
          roleColor: role?.color || 0,
        }
      })

      return res.status(200).json({
        levelupChannelId: settings.levelupChannelId || null,
        levelupChannelName: channelInfo?.name || null,
        roleRewards: roleRewardsWithNames,
      })
    } else if (req.method === 'POST') {
      // Update guild settings via bot API
      const { levelupChannelId, roleRewards } = req.body

      console.log(`[API] Updating settings for guild ${serverId}:`, { levelupChannelId, roleRewardsCount: roleRewards?.length })

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10000) // 10 second timeout

      try {
        const response = await fetch(`${BOT_API_URL}/api/server/${serverId}/settings`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            levelupChannelId,
            roleRewards,
          }),
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        if (!response.ok) {
          const errorText = await response.text().catch(() => 'Unknown error')
          console.error(`[API] Failed to update settings: ${response.status} ${response.statusText}`, errorText)
          return res.status(response.status).json({ error: `Failed to update settings: ${errorText}` })
        }

        const result = await response.json()
        console.log('[API] Settings updated successfully')
        return res.status(200).json(result)
      } catch (error) {
        clearTimeout(timeoutId)
        if ((error as Error).name === 'AbortError') {
          console.error('[API] Settings update timed out')
          return res.status(504).json({ error: 'Request timed out - API may be on cold start. Please try again.' })
        }
        throw error
      }
    } else {
      return res.status(405).json({ error: 'Method not allowed' })
    }
  } catch (error) {
    console.error('Error handling settings:', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
}
