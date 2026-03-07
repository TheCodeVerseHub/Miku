import { useSession } from 'next-auth/react'
import { useRouter } from 'next/router'
import { useEffect, useState } from 'react'
import Head from 'next/head'
import Navbar from '@/components/Navbar'
import ServerCard from '@/components/ServerCard'
import LoadingSpinner from '@/components/LoadingSpinner'
import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then((res) => {
  if (!res.ok) throw new Error('Failed to fetch')
  return res.json()
})

interface Guild {
  id: string
  name: string
  icon: string | null
  memberCount: number
  hasMiku: boolean
}

export default function Dashboard() {
  const { data: session, status } = useSession()
  const router = useRouter()
  const [selectedServer, setSelectedServer] = useState<string | null>(null)

  const { data: guilds, error, isLoading } = useSWR<Guild[]>(
    session ? '/api/guilds' : null,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 60000, // 1 minute
      errorRetryCount: 2,
      errorRetryInterval: 3000,
      shouldRetryOnError: true,
    }
  )

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/')
    }
  }, [status, router])

  // Show loading only when authenticating or on initial load
  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner />
        <p className="ml-4 text-gray-400">Authenticating...</p>
      </div>
    )
  }

  // Show error state
  if (error) {
    return (
      <div className="min-h-screen">
        <Navbar />
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="bg-red-900/20 border border-red-500 rounded-lg p-6 text-center">
            <p className="text-red-400 text-lg mb-4">Failed to load servers</p>
            <p className="text-gray-400 mb-4">Please try refreshing the page or check your connection.</p>
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

  const serversWithMiku = guilds?.filter(guild => guild.hasMiku) || []
  const serversWithoutMiku = guilds?.filter(guild => !guild.hasMiku) || []

  return (
    <>
      <Head>
        <title>Dashboard - Miku</title>
      </Head>

      <div className="min-h-screen">
        <Navbar />

        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="mb-8">
            <h1 className="text-4xl font-bold mb-2">Your Servers</h1>
            <p className="text-gray-400">Select a server to manage Miku's settings and view stats</p>
          </div>

          {/* Loading state - show skeleton */}
          {isLoading && (
            <div className="space-y-8">
              <div className="animate-pulse">
                <div className="h-8 bg-discord-gray rounded w-48 mb-4"></div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="bg-discord-gray h-40 rounded-lg"></div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Show servers after loading */}
          {!isLoading && guilds && (
            <>
              {/* Servers with Miku */}
              <div className="mb-12">
                <h2 className="text-2xl font-semibold mb-4 flex items-center">
                  <span className="w-3 h-3 bg-discord-green rounded-full mr-3"></span>
                  Active Servers ({serversWithMiku.length})
                </h2>
                
                {serversWithMiku.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {serversWithMiku.map((guild) => (
                      <ServerCard key={guild.id} guild={guild} />
                    ))}
                  </div>
                ) : (
                  <div className="bg-discord-gray p-8 rounded-lg text-center">
                    <p className="text-gray-400">No servers with Miku found</p>
                    <a
                      href={`https://discord.com/api/oauth2/authorize?client_id=${process.env.NEXT_PUBLIC_DISCORD_CLIENT_ID || '1234567890'}&permissions=8&scope=bot%20applications.commands`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block mt-4 bg-discord-blue hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition"
                    >
                      Invite Miku to a Server
                    </a>
                  </div>
                )}
              </div>

              {/* Servers without Miku */}
              {serversWithoutMiku.length > 0 && (
                <div>
                  <h2 className="text-2xl font-semibold mb-4 flex items-center">
                    <span className="w-3 h-3 bg-gray-500 rounded-full mr-3"></span>
                    Add Miku to These Servers ({serversWithoutMiku.length})
                  </h2>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {serversWithoutMiku.map((guild) => (
                      <ServerCard key={guild.id} guild={guild} showInvite />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}
