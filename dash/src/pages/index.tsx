import Head from 'next/head'
import Link from 'next/link'
import { useSession, signIn } from 'next-auth/react'
import Navbar from '@/components/Navbar'
import StatsCard from '@/components/StatsCard'
import { FaUsers, FaChartLine, FaTrophy, FaServer } from 'react-icons/fa'

export default function Home() {
  const { data: session } = useSession()

  return (
    <>
      <Head>
        <title>Miku - Discord Leveling Bot Dashboard</title>
      </Head>

      <div className="min-h-screen">
        <Navbar />

        {/* Hero Section */}
        <section className="py-20 px-4 text-center bg-gradient-to-b from-discord-gray to-discord-dark">
          <div className="max-w-6xl mx-auto">
            <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-discord-blue to-discord-green bg-clip-text text-transparent">
              Welcome to Miku
            </h1>
            <p className="text-xl md:text-2xl text-gray-300 mb-8">
              The ultimate Discord leveling bot with beautiful rank cards and engaging gameplay
            </p>
            
            {!session ? (
              <button
                onClick={() => signIn('discord')}
                className="bg-discord-blue hover:bg-blue-600 text-white font-bold py-4 px-8 rounded-lg text-lg transition-all transform hover:scale-105"
              >
                Login with Discord
              </button>
            ) : (
              <Link
                href="/dashboard"
                className="inline-block bg-discord-blue hover:bg-blue-600 text-white font-bold py-4 px-8 rounded-lg text-lg transition-all transform hover:scale-105"
              >
                Go to Dashboard
              </Link>
            )}
          </div>
        </section>

        {/* Features Section */}
        <section className="py-16 px-4">
          <div className="max-w-6xl mx-auto">
            <h2 className="text-4xl font-bold text-center mb-12">Features</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <StatsCard
                icon={<FaUsers className="text-4xl" />}
                title="User Tracking"
                description="Track XP and levels for all server members"
                color="blue"
              />
              <StatsCard
                icon={<FaChartLine className="text-4xl" />}
                title="Real-time Stats"
                description="Live leaderboards and progress tracking"
                color="green"
              />
              <StatsCard
                icon={<FaTrophy className="text-4xl" />}
                title="Rank Cards"
                description="Beautiful custom rank cards for every user"
                color="yellow"
              />
              <StatsCard
                icon={<FaServer className="text-4xl" />}
                title="Multi-Server"
                description="Manage multiple Discord servers from one place"
                color="purple"
              />
            </div>
          </div>
        </section>

        {/* Commands Preview */}
        <section className="py-16 px-4 bg-discord-gray">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-4xl font-bold text-center mb-12">Quick Commands</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-discord-dark p-6 rounded-lg border border-discord-light">
                <code className="text-discord-green">/rank [user]</code>
                <p className="mt-2 text-gray-400">Check your or another user's rank and level</p>
              </div>
              
              <div className="bg-discord-dark p-6 rounded-lg border border-discord-light">
                <code className="text-discord-green">/leaderboard [page]</code>
                <p className="mt-2 text-gray-400">View the server leaderboard</p>
              </div>
              
              <div className="bg-discord-dark p-6 rounded-lg border border-discord-light">
                <code className="text-discord-green">/setlevel &lt;user&gt; &lt;level&gt;</code>
                <p className="mt-2 text-gray-400">Set a user's level (Admin only)</p>
              </div>
              
              <div className="bg-discord-dark p-6 rounded-lg border border-discord-light">
                <code className="text-discord-green">/addxp &lt;user&gt; &lt;amount&gt;</code>
                <p className="mt-2 text-gray-400">Add XP to a user (Admin only)</p>
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="py-8 px-4 text-center border-t border-discord-light">
          <div className="max-w-6xl mx-auto">
            <p className="text-gray-400">
              Made with ❤️ by TheCodeVerseHub | 
              <Link href="https://github.com/TheCodeVerseHub/Miku" className="text-discord-blue hover:underline ml-2">
                GitHub
              </Link>
            </p>
          </div>
        </footer>
      </div>
    </>
  )
}
