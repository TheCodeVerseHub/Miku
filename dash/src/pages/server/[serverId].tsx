import { useRouter } from 'next/router'
import { useSession } from 'next-auth/react'
import Head from 'next/head'
import Navbar from '@/components/Navbar'
import LoadingSpinner from '@/components/LoadingSpinner'
import LeaderboardTable from '@/components/LeaderboardTable'
import StatsOverview from '@/components/StatsOverview'
import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then((res) => {
  if (!res.ok) throw new Error('Failed to fetch')
  return res.json()
})

interface ServerStats {
  totalMembers: number
  totalXP: number
  activeUsers: number
  averageLevel: number
  topUser: {
    username: string
    level: number
  } | null
}

export default function ServerStats() {
  const router = useRouter()
  const { serverId } = router.query
  const { data: session, status } = useSession()

  const { data: stats, error: statsError, isLoading: statsLoading } = useSWR<ServerStats>(
    serverId ? `/api/server/${serverId}/stats` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  )

  const { data: leaderboard, error: lbError, isLoading: lbLoading } = useSWR(
    serverId ? `/api/server/${serverId}/leaderboard` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  )

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner />
        <p className="ml-4 text-gray-400">Loading session...</p>
      </div>
    )
  }

  if (status === 'unauthenticated') {
    router.push('/')
    return null
  }

  if (statsError || lbError) {
    return (
      <div className="min-h-screen">
        <Navbar />
        <div className="max-w-7xl mx-auto px-4 py-8">
          <button
            onClick={() => router.push('/dashboard')}
            className="mb-6 text-discord-blue hover:underline flex items-center"
          >
            ← Back to Dashboard
          </button>
          <div className="bg-red-900/20 border border-red-500 rounded-lg p-8 text-center">
            <p className="text-red-400 text-lg mb-4">Failed to load server data</p>
            <p className="text-gray-400 mb-4">The server may not have Miku or the API is unavailable.</p>
            <button
              onClick={() => window.location.reload()}
              className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg transition"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  const isLoading = statsLoading || lbLoading

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

          {/* Server Name and Settings Button */}
          <div className="flex justify-between items-center mb-8">
            <h1 className="text-4xl font-bold">Server Statistics</h1>
            <button
              onClick={() => router.push(`/server/${serverId}/settings`)}
              className="bg-discord-blue hover:bg-blue-600 text-white font-semibold px-6 py-3 rounded-lg transition-colors flex items-center gap-2"
            >
              ⚙️ Leveling Settings
            </button>
          </div>

          {/* Loading State */}
          {isLoading && (
            <div className="space-y-8">
              <div className="animate-pulse">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                  <div className="bg-discord-gray h-32 rounded-lg"></div>
                  <div className="bg-discord-gray h-32 rounded-lg"></div>
                  <div className="bg-discord-gray h-32 rounded-lg"></div>
                  <div className="bg-discord-gray h-32 rounded-lg"></div>
                </div>
                <div className="bg-discord-gray h-96 rounded-lg"></div>
              </div>
            </div>
          )}

          {/* Stats Overview */}
          {stats && <StatsOverview stats={stats} />}

          {/* Leaderboard */}
          {leaderboard && (
            <div className="mt-12">
              <h2 className="text-3xl font-bold mb-6">Leaderboard</h2>
              <LeaderboardTable data={leaderboard} />
            </div>
          )}

          {/* Charts Section */}
          {!isLoading && (
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
          )}
        </div>
      </div>
    </>
  )
}

