/**
 * Calculate XP required for a specific level
 * Formula matches bot: 5 * (level²) + (50 * level) + 100
 */
export function calculateXpForLevel(level: number): number {
  return 5 * (level ** 2) + (50 * level) + 100
}

/**
 * Calculate total XP required to reach a specific level
 */
export function calculateTotalXpForLevel(level: number): number {
  let totalXp = 0
  for (let i = 1; i <= level; i++) {
    totalXp += calculateXpForLevel(i)
  }
  return totalXp
}

/**
 * Calculate level from total XP
 */
export function calculateLevelFromXp(totalXp: number): {
  level: number
  currentLevelXp: number
  requiredXp: number
} {
  let level = 0
  let xpUsed = 0

  while (true) {
    const xpForNextLevel = calculateXpForLevel(level + 1)
    if (xpUsed + xpForNextLevel > totalXp) {
      break
    }
    xpUsed += xpForNextLevel
    level++
  }

  const currentLevelXp = totalXp - xpUsed
  const requiredXp = calculateXpForLevel(level + 1)

  return { level, currentLevelXp, requiredXp }
}

/**
 * Format number with ordinal suffix (1st, 2nd, 3rd, etc.)
 */
export function getOrdinalSuffix(num: number): string {
  const j = num % 10
  const k = num % 100

  if (j === 1 && k !== 11) {
    return num + 'st'
  }
  if (j === 2 && k !== 12) {
    return num + 'nd'
  }
  if (j === 3 && k !== 13) {
    return num + 'rd'
  }
  return num + 'th'
}

/**
 * Format large numbers with K, M, B suffixes
 */
export function formatNumber(num: number): string {
  if (num >= 1000000000) {
    return (num / 1000000000).toFixed(1) + 'B'
  }
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

/**
 * Get Discord avatar URL
 */
export function getAvatarUrl(userId: string, avatar: string | null): string {
  if (avatar) {
    return `https://cdn.discordapp.com/avatars/${userId}/${avatar}.png?size=256`
  }
  return '/default-avatar.png'
}

/**
 * Get Discord guild icon URL
 */
export function getGuildIconUrl(guildId: string, icon: string | null): string {
  if (icon) {
    return `https://cdn.discordapp.com/icons/${guildId}/${icon}.png?size=256`
  }
  return '/default-server-icon.png'
}
