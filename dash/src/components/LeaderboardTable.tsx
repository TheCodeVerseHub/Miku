import { useState } from 'react'
import Image from 'next/image'

interface LeaderboardEntry {
  rank: number
  userId: string
  username: string
  discriminator: string
  avatar: string | null
  level: number
  xp: number
  totalXp: number
}

interface LeaderboardData {
  data: LeaderboardEntry[]
  page: number
  totalPages: number
  total: number
}

interface LeaderboardTableProps {
  data: LeaderboardData
}

export default function LeaderboardTable({ data }: LeaderboardTableProps) {
  const [currentPage, setCurrentPage] = useState(data.page)

  const getMedalEmoji = (rank: number) => {
    if (rank === 1) return '🥇'
    if (rank === 2) return '🥈'
    if (rank === 3) return '🥉'
    return null
  }

  const getAvatarUrl = (userId: string, avatar: string | null) => {
    if (avatar) {
      return `https://cdn.discordapp.com/avatars/${userId}/${avatar}.png`
    }
    return '/default-avatar.png'
  }

  const calculateXpForNextLevel = (level: number) => {
    return 100 * level + 50 * (level - 1)
  }

  return (
    <div className="bg-discord-gray rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-discord-dark border-b border-discord-light">
            <tr>
              <th className="px-6 py-4 text-left text-sm font-semibold">Rank</th>
              <th className="px-6 py-4 text-left text-sm font-semibold">User</th>
              <th className="px-6 py-4 text-left text-sm font-semibold">Level</th>
              <th className="px-6 py-4 text-left text-sm font-semibold">XP</th>
              <th className="px-6 py-4 text-left text-sm font-semibold">Total XP</th>
              <th className="px-6 py-4 text-left text-sm font-semibold">Progress</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-discord-light">
            {data.data.map((entry) => {
              const xpForNext = calculateXpForNextLevel(entry.level + 1)
              const progress = (entry.xp / xpForNext) * 100

              return (
                <tr key={entry.userId} className="hover:bg-discord-light transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-2">
                      <span className="text-lg">{getMedalEmoji(entry.rank)}</span>
                      <span className="font-semibold">#{entry.rank}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 rounded-full overflow-hidden bg-discord-light">
                        <Image
                          src={getAvatarUrl(entry.userId, entry.avatar)}
                          alt={entry.username}
                          width={40}
                          height={40}
                        />
                      </div>
                      <span className="font-medium">
                        {entry.username}#{entry.discriminator}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="bg-discord-blue px-3 py-1 rounded-full text-sm font-semibold">
                      {entry.level}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-300">
                    {entry.xp.toLocaleString()} / {xpForNext.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-gray-300">
                    {entry.totalXp.toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    <div className="w-32">
                      <div className="bg-discord-dark rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-discord-green h-full rounded-full transition-all"
                          style={{ width: `${progress}%` }}
                        ></div>
                      </div>
                      <p className="text-xs text-gray-400 mt-1">{progress.toFixed(1)}%</p>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-discord-light">
        <div className="text-sm text-gray-400">
          Showing {(data.page - 1) * 50 + 1} to {Math.min(data.page * 50, data.total)} of{' '}
          {data.total} entries
        </div>
        <div className="flex space-x-2">
          <button
            disabled={data.page === 1}
            className="px-4 py-2 bg-discord-dark rounded hover:bg-discord-light disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <button
            disabled={data.page === data.totalPages}
            className="px-4 py-2 bg-discord-dark rounded hover:bg-discord-light disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  )
}
