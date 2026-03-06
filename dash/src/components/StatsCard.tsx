import { ReactNode } from 'react'

interface StatsCardProps {
  icon: ReactNode
  title: string
  description: string
  color: 'blue' | 'green' | 'yellow' | 'purple' | 'red'
}

export default function StatsCard({ icon, title, description, color }: StatsCardProps) {
  const colorClasses = {
    blue: 'text-discord-blue',
    green: 'text-discord-green',
    yellow: 'text-yellow-400',
    purple: 'text-purple-400',
    red: 'text-discord-red',
  }

  return (
    <div className="bg-discord-gray p-6 rounded-lg border border-discord-light hover:border-discord-blue transition-all transform hover:scale-105">
      <div className={`${colorClasses[color]} mb-4`}>{icon}</div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-gray-400">{description}</p>
    </div>
  )
}
