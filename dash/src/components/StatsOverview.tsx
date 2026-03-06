import { FaUsers, FaChartLine, FaTrophy, FaAward } from 'react-icons/fa'

interface ServerStats {
  totalMembers: number
  totalXP: number
  activeUsers: number
  averageLevel: number
  topUser: {
    username: string
    level: number
  }
}

interface StatsOverviewProps {
  stats: ServerStats
}

export default function StatsOverview({ stats }: StatsOverviewProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div className="bg-discord-gray p-6 rounded-lg border border-discord-light">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-400">Total Members</h3>
          <FaUsers className="text-discord-blue text-2xl" />
        </div>
        <p className="text-3xl font-bold">{stats.totalMembers.toLocaleString()}</p>
      </div>

      <div className="bg-discord-gray p-6 rounded-lg border border-discord-light">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-400">Active Users</h3>
          <FaChartLine className="text-discord-green text-2xl" />
        </div>
        <p className="text-3xl font-bold">{stats.activeUsers.toLocaleString()}</p>
      </div>

      <div className="bg-discord-gray p-6 rounded-lg border border-discord-light">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-400">Average Level</h3>
          <FaAward className="text-yellow-400 text-2xl" />
        </div>
        <p className="text-3xl font-bold">{stats.averageLevel.toFixed(1)}</p>
      </div>

      <div className="bg-discord-gray p-6 rounded-lg border border-discord-light">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-400">Top User</h3>
          <FaTrophy className="text-purple-400 text-2xl" />
        </div>
        <p className="text-xl font-bold truncate">{stats.topUser.username}</p>
        <p className="text-gray-400">Level {stats.topUser.level}</p>
      </div>
    </div>
  )
}
