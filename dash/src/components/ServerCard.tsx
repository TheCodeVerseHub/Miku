import Link from 'next/link'
import Image from 'next/image'

interface Guild {
  id: string
  name: string
  icon: string | null
  memberCount: number
  hasMiku: boolean
}

interface ServerCardProps {
  guild: Guild
  showInvite?: boolean
}

export default function ServerCard({ guild, showInvite = false }: ServerCardProps) {
  const iconUrl = guild.icon
    ? `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`
    : '/default-server-icon.png'

  const inviteUrl = `https://discord.com/api/oauth2/authorize?client_id=${process.env.NEXT_PUBLIC_CLIENT_ID}&permissions=8&scope=bot%20applications.commands&guild_id=${guild.id}`

  return (
    <div className="bg-discord-gray border border-discord-light rounded-lg p-6 hover:border-discord-blue transition-all">
      <div className="flex items-center space-x-4 mb-4">
        <div className="w-16 h-16 bg-discord-light rounded-full flex items-center justify-center overflow-hidden">
          {guild.icon ? (
            <Image src={iconUrl} alt={guild.name} width={64} height={64} />
          ) : (
            <span className="text-2xl font-bold">{guild.name.charAt(0)}</span>
          )}
        </div>
        <div>
          <h3 className="text-xl font-semibold">{guild.name}</h3>
          {guild.memberCount > 0 && (
            <p className="text-gray-400">{guild.memberCount.toLocaleString()} members</p>
          )}
        </div>
      </div>

      {guild.hasMiku ? (
        <Link
          href={`/server/${guild.id}`}
          className="w-full bg-discord-blue hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded transition-colors block text-center"
        >
          Manage Server
        </Link>
      ) : showInvite ? (
        <a
          href={inviteUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full bg-discord-green hover:bg-green-600 text-white font-semibold py-2 px-4 rounded transition-colors block text-center"
        >
          Add Miku
        </a>
      ) : null}
    </div>
  )
}
