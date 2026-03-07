import type { NextApiRequest, NextApiResponse } from 'next'
import { getSession } from 'next-auth/react'
import Database from 'better-sqlite3'
import path from 'path'

// Database path (same as bot)
const DB_PATH = path.join(process.cwd(), '../../data/leveling.db')

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

  try {
    const db = new Database(DB_PATH)

    if (req.method === 'GET') {
      // Get guild settings and role rewards
      const settings = db.prepare(
        'SELECT * FROM guild_settings WHERE guild_id = ?'
      ).get(serverId) as { levelup_channel_id?: number; updated_at?: number } | undefined

      const roleRewards = db.prepare(
        'SELECT level, role_id FROM role_rewards WHERE guild_id = ? ORDER BY level'
      ).all(serverId) as Array<{ level: number; role_id: number }>

      // Fetch channel and role info from Discord API
      let channelInfo = null
      if (settings?.levelup_channel_id) {
        try {
          const channelResponse = await fetch(
            `https://discord.com/api/v10/channels/${settings.levelup_channel_id}`,
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
      const roleRewardsWithNames = roleRewards.map((rr) => {
        const role = guildInfo?.roles?.find((r: any) => r.id === rr.role_id.toString())
        return {
          level: rr.level,
          roleId: rr.role_id.toString(),
          roleName: role?.name || 'Unknown Role',
          roleColor: role?.color || 0,
        }
      })

      db.close()

      return res.status(200).json({
        levelupChannelId: settings?.levelup_channel_id?.toString() || null,
        levelupChannelName: channelInfo?.name || null,
        roleRewards: roleRewardsWithNames,
      })
    } else if (req.method === 'POST') {
      // Update guild settings
      const { levelupChannelId, roleRewards } = req.body

      // Update levelup channel if provided
      if (levelupChannelId !== undefined) {
        if (levelupChannelId === null) {
          // Remove channel setting
          db.prepare(
            'UPDATE guild_settings SET levelup_channel_id = NULL WHERE guild_id = ?'
          ).run(serverId)
        } else {
          db.prepare(
            `INSERT INTO guild_settings (guild_id, levelup_channel_id, updated_at)
             VALUES (?, ?, ?)
             ON CONFLICT(guild_id) DO UPDATE SET
               levelup_channel_id = excluded.levelup_channel_id,
               updated_at = excluded.updated_at`
          ).run(serverId, levelupChannelId, Date.now() / 1000)
        }
      }

      // Update role rewards if provided
      if (roleRewards !== undefined) {
        // Clear existing role rewards
        db.prepare('DELETE FROM role_rewards WHERE guild_id = ?').run(serverId)

        // Add new role rewards
        const insertStmt = db.prepare(
          `INSERT INTO role_rewards (guild_id, level, role_id) VALUES (?, ?, ?)`
        )
        for (const reward of roleRewards) {
          insertStmt.run(serverId, reward.level, reward.roleId)
        }
      }

      db.close()

      return res.status(200).json({ success: true })
    } else {
      db.close()
      return res.status(405).json({ error: 'Method not allowed' })
    }
  } catch (error) {
    console.error('Error handling settings:', error)
    return res.status(500).json({ error: 'Internal server error' })
  }
}
