import { useSession } from 'next-auth/react'
import { useRouter } from 'next/router'
import { useEffect, useState } from 'react'
import Head from 'next/head'
import Navbar from '@/components/Navbar'
import ServerCard from '@/components/ServerCard'
import LoadingSpinner from '@/components/LoadingSpinner'
import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then((res) => res.json())

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

  const { data: guilds, error } = useSWR<Guild[]>(
    session ? '/api/guilds' : null,
    fetcher
  )

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/')
    }
  }, [status, router])

  if (status === 'loading' || !guilds) {
    return <LoadingSpinner />
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-red-500">Failed to load servers. Please try again.</p>
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
        </div>
      </div>
    </>
  )
}
