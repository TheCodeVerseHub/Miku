import Link from 'next/link'
import { useSession, signIn, signOut } from 'next-auth/react'
import Image from 'next/image'

export default function Navbar() {
  const { data: session } = useSession()

  return (
    <nav className="bg-discord-gray border-b border-discord-light">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-discord-blue rounded-full flex items-center justify-center">
              <span className="text-xl font-bold">M</span>
            </div>
            <span className="text-xl font-bold">Miku</span>
          </Link>

          {/* Navigation Links */}
          <div className="hidden md:flex items-center space-x-6">
            <Link href="/" className="hover:text-discord-blue transition-colors">
              Home
            </Link>
            {session && (
              <Link href="/dashboard" className="hover:text-discord-blue transition-colors">
                Dashboard
              </Link>
            )}
            <a
              href="https://github.com/TheCodeVerseHub/Miku"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-discord-blue transition-colors"
            >
              GitHub
            </a>
          </div>

          {/* Auth Button */}
          <div className="flex items-center space-x-4">
            {session ? (
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  {session.user?.image && (
                    <Image
                      src={session.user.image}
                      alt="User Avatar"
                      width={32}
                      height={32}
                      className="rounded-full"
                    />
                  )}
                  <span className="hidden sm:inline">{session.user?.name}</span>
                </div>
                <button
                  onClick={() => signOut()}
                  className="bg-discord-red hover:bg-red-600 px-4 py-2 rounded transition-colors"
                >
                  Logout
                </button>
              </div>
            ) : (
              <button
                onClick={() => signIn('discord')}
                className="bg-discord-blue hover:bg-blue-600 px-4 py-2 rounded transition-colors"
              >
                Login
              </button>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
