import { useRouter } from 'next/router'
import { useSession } from 'next-auth/react'
import Head from 'next/head'
import Navbar from '@/components/Navbar'
import LoadingSpinner from '@/components/LoadingSpinner'
import { useState, useEffect } from 'react'
import useSWR from 'swr'
import { GuildSettings, GuildData, RoleReward } from '@/types'

const fetcher = (url: string) => fetch(url).then((res) => res.json())

export default function ServerSettings() {
  const router = useRouter()
  const { serverId } = router.query
  const { data: session, status } = useSession()

  const { data: settings, error: settingsError, mutate } = useSWR<GuildSettings>(
    serverId ? `/api/server/${serverId}/settings` : null,
    fetcher
  )

  const { data: guildData, error: guildError } = useSWR<GuildData>(
    serverId ? `/api/server/${serverId}/guild-data` : null,
    fetcher
  )

  const [levelupChannelId, setLevelupChannelId] = useState<string>('')
  const [roleRewards, setRoleRewards] = useState<RoleReward[]>([])
  const [newRewardLevel, setNewRewardLevel] = useState<string>('')
  const [newRewardRoleId, setNewRewardRoleId] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (settings) {
      setLevelupChannelId(settings.levelupChannelId || '')
      setRoleRewards(settings.roleRewards || [])
    }
  }, [settings])

  if (status === 'loading' || !settings || !guildData) {
    return <LoadingSpinner />
  }

  if (status === 'unauthenticated') {
    router.push('/')
    return null
  }

  if (settingsError || guildError) {
    return (
      <div className="min-h-screen">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <p className="text-red-500">Failed to load settings</p>
        </div>
      </div>
    )
  }

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 5000)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const response = await fetch(`/api/server/${serverId}/settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          levelupChannelId: levelupChannelId || null,
          roleRewards: roleRewards.map((rr) => ({
            level: rr.level,
            roleId: rr.roleId,
          })),
        }),
      })

      if (response.ok) {
        showMessage('success', 'Settings saved successfully!')
        mutate()
      } else {
        showMessage('error', 'Failed to save settings')
      }
    } catch (error) {
      showMessage('error', 'An error occurred while saving')
    } finally {
      setSaving(false)
    }
  }

  const handleAddReward = () => {
    const level = parseInt(newRewardLevel)
    if (!level || level < 1) {
      showMessage('error', 'Please enter a valid level (1 or higher)')
      return
    }

    if (!newRewardRoleId) {
      showMessage('error', 'Please select a role')
      return
    }

    // Check if level already exists
    if (roleRewards.some((rr) => rr.level === level)) {
      showMessage('error', `Level ${level} already has a reward`)
      return
    }

    const role = guildData.roles.find((r) => r.id === newRewardRoleId)
    if (!role) {
      showMessage('error', 'Role not found')
      return
    }

    setRoleRewards([
      ...roleRewards,
      {
        level,
        roleId: role.id,
        roleName: role.name,
        roleColor: role.color,
      },
    ].sort((a, b) => a.level - b.level))

    setNewRewardLevel('')
    setNewRewardRoleId('')
  }

  const handleRemoveReward = (level: number) => {
    setRoleRewards(roleRewards.filter((rr) => rr.level !== level))
  }

  const getRoleColor = (color: number) => {
    if (color === 0) return '#99AAB5'
    return `#${color.toString(16).padStart(6, '0')}`
  }

  return (
    <>
      <Head>
        <title>Server Settings - Miku</title>
      </Head>

      <div className="min-h-screen">
        <Navbar />

        <div className="max-w-4xl mx-auto px-4 py-8">
          {/* Back Button */}
          <button
            onClick={() => router.push(`/server/${serverId}`)}
            className="mb-6 text-discord-blue hover:underline flex items-center"
          >
            ← Back to Server Stats
          </button>

          {/* Header */}
          <h1 className="text-4xl font-bold mb-8">⚙️ Leveling Settings</h1>

          {/* Message */}
          {message && (
            <div
              className={`mb-6 p-4 rounded-lg ${
                message.type === 'success'
                  ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                  : 'bg-red-500/20 text-red-400 border border-red-500/50'
              }`}
            >
              {message.text}
            </div>
          )}

          {/* Level-up Channel Setting */}
          <div className="bg-discord-gray p-6 rounded-lg mb-6">
            <h2 className="text-2xl font-semibold mb-4">📢 Level-Up Announcement Channel</h2>
            <p className="text-gray-400 mb-4">
              Choose where level-up messages should be sent. Leave empty to send in the current channel.
            </p>
            <select
              value={levelupChannelId}
              onChange={(e) => setLevelupChannelId(e.target.value)}
              className="w-full bg-discord-dark text-white p-3 rounded-lg border border-gray-700 focus:border-discord-blue focus:outline-none"
            >
              <option value="">No specific channel (use current channel)</option>
              {guildData.channels.map((channel) => (
                <option key={channel.id} value={channel.id}>
                  # {channel.name}
                </option>
              ))}
            </select>
          </div>

          {/* Role Rewards Setting */}
          <div className="bg-discord-gray p-6 rounded-lg mb-6">
            <h2 className="text-2xl font-semibold mb-4">🎁 Role Rewards</h2>
            <p className="text-gray-400 mb-4">
              Assign roles to users when they reach specific levels.
            </p>

            {/* Existing Rewards */}
            {roleRewards.length > 0 && (
              <div className="mb-6 space-y-2">
                {roleRewards.map((reward) => (
                  <div
                    key={reward.level}
                    className="flex items-center justify-between bg-discord-dark p-3 rounded-lg"
                  >
                    <div className="flex items-center gap-4">
                      <span className="font-semibold text-lg">Level {reward.level}</span>
                      <span className="text-gray-400">→</span>
                      <span
                        className="font-medium"
                        style={{ color: getRoleColor(reward.roleColor) }}
                      >
                        @{reward.roleName}
                      </span>
                    </div>
                    <button
                      onClick={() => handleRemoveReward(reward.level)}
                      className="text-red-400 hover:text-red-300 font-semibold px-3 py-1 rounded"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Add New Reward */}
            <div className="border-t border-gray-700 pt-4">
              <h3 className="text-lg font-semibold mb-3">Add New Role Reward</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <input
                  type="number"
                  min="1"
                  placeholder="Level (e.g., 10)"
                  value={newRewardLevel}
                  onChange={(e) => setNewRewardLevel(e.target.value)}
                  className="bg-discord-dark text-white p-3 rounded-lg border border-gray-700 focus:border-discord-blue focus:outline-none"
                />
                <select
                  value={newRewardRoleId}
                  onChange={(e) => setNewRewardRoleId(e.target.value)}
                  className="bg-discord-dark text-white p-3 rounded-lg border border-gray-700 focus:border-discord-blue focus:outline-none"
                >
                  <option value="">Select a role...</option>
                  {guildData.roles.map((role) => (
                    <option key={role.id} value={role.id}>
                      @{role.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleAddReward}
                  className="bg-discord-blue hover:bg-blue-600 text-white font-semibold px-4 py-3 rounded-lg transition-colors"
                >
                  Add Reward
                </button>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold px-8 py-3 rounded-lg transition-colors text-lg"
            >
              {saving ? 'Saving...' : '💾 Save Settings'}
            </button>
          </div>

          {/* Info Box */}
          <div className="mt-8 bg-discord-blue/10 border border-discord-blue/50 p-4 rounded-lg">
            <h3 className="font-semibold mb-2 text-discord-blue">ℹ️ Important Notes:</h3>
            <ul className="list-disc list-inside space-y-1 text-gray-300 text-sm">
              <li>Role rewards are automatically assigned when users reach the specified level</li>
              <li>Make sure the bot has permission to assign the roles</li>
              <li>The bot&apos;s role must be higher than the roles you want to assign</li>
              <li>Changes take effect immediately after saving</li>
            </ul>
          </div>
        </div>
      </div>
    </>
  )
}
