import { useRouter } from 'next/router'
import { useSession } from 'next-auth/react'
import Head from 'next/head'
import Navbar from '@/components/Navbar'
import LoadingSpinner from '@/components/LoadingSpinner'
import LeaderboardTable from '@/components/LeaderboardTable'
import StatsOverview from '@/components/StatsOverview'
import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then((res) => res.json())

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

export default function ServerStats() {
  const router = useRouter()
  const { serverId } = router.query
  const { data: session, status } = useSession()

  const { data: stats, error: statsError } = useSWR<ServerStats>(
    serverId ? `/api/server/${serverId}/stats` : null,
    fetcher
  )

  const { data: leaderboard, error: lbError } = useSWR(
    serverId ? `/api/server/${serverId}/leaderboard` : null,
    fetcher
  )

  if (status === 'loading' || !stats || !leaderboard) {
    return <LoadingSpinner />
  }

  if (status === 'unauthenticated') {
    router.push('/')
    return null
  }

  if (statsError || lbError) {
    return (
      <div className="min-h-screen">
        <Navbar />
        <div className="flex items-center justify-center h-96">
          <p className="text-red-500">Failed to load server data</p>
        </div>
      </div>
    )
  }

  return (
    <>
      <Head>
        <title>Server Stats - Miku</title>
      </Head>

      <div className="min-h-screen">
        <Navbar />

        <div className="max-w-7xl mx-auto px-4 py-8">
          {/* Back Button */}
          <button
            onClick={() => router.push('/dashboard')}
            className="mb-6 text-discord-blue hover:underline flex items-center"
          >
            ← Back to Dashboard
          </button>

          {/* Server Name */}
          <h1 className="text-4xl font-bold mb-8">Server Statistics</h1>

          {/* Stats Overview */}
          <StatsOverview stats={stats} />

          {/* Leaderboard */}
          <div className="mt-12">
            <h2 className="text-3xl font-bold mb-6">Leaderboard</h2>
            <LeaderboardTable data={leaderboard} />
          </div>

          {/* Charts Section */}
          <div className="mt-12 grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-discord-gray p-6 rounded-lg">
              <h3 className="text-xl font-semibold mb-4">XP Distribution</h3>
              <p className="text-gray-400">Coming soon: Chart showing XP distribution across levels</p>
            </div>

            <div className="bg-discord-gray p-6 rounded-lg">
              <h3 className="text-xl font-semibold mb-4">Activity Trends</h3>
              <p className="text-gray-400">Coming soon: Chart showing user activity over time</p>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
