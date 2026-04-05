# Miku - Discord Leveling Bot

A feature-rich Discord leveling bot inspired by Arcane, with support for both **slash commands** and **prefix commands** (prefix: `&`).

## Features

- **XP & Leveling System** - Users gain 15-25 XP per message (60-second cooldown)
- **Rank Cards** - Beautiful embeds showing user rank, level, and progress
- **Leaderboards** - View top members by XP with pagination
- **Hybrid Commands** - Works with both `/` slash commands and `&` prefix
- **PostgreSQL Database** - Persistent data storage via `asyncpg`
- **Rich Embeds** - Clean, visually appealing messages
- **Admin Tools** - Manage user levels and XP
- **GitHub Integration** - Look up repos/users and search GitHub
- **Utility / Fun / Info Commands** - General helpful commands and light games (no moderation)

## Commands

### Leveling Commands

| Command | Slash | Prefix | Description |
|---------|-------|--------|-------------|
| **rank** | `/rank [user]` | `&rank [user]` | Check your or another user's rank and level |
| **level** | `/level [user]` | `&level [user]` | Alias for rank command |
| **leaderboard** | `/leaderboard [page]` | `&leaderboard [page]` | View the server leaderboard (top 50) |
| **lb** | `/lb [page]` | `&lb [page]` | Alias for leaderboard |
| **xp** | `/xp [user]` | `&xp [user]` | Check detailed XP information |

### Utility Commands

| Command | Slash | Prefix | Description |
|---------|-------|--------|-------------|
| **ping** | `/ping` | `&ping` | Check if the bot is responsive and view latency |
| **uptime** | `/uptime` | `&uptime` | Show how long the bot has been online |
| **about** | `/about` | `&about` | Bot information and basic stats |
| **invite** | `/invite` | `&invite` | Get a bot invite link |
| **avatar** | `/avatar [user]` | `&avatar [user]` | Show a user's avatar |
| **userinfo** | `/userinfo [user]` | `&userinfo [user]` | Show information about a server member |
| **serverinfo** | `/serverinfo` | `&serverinfo` | Show information about the current server |

### Fun Commands

| Command | Slash | Prefix | Description |
|---------|-------|--------|-------------|
| **8ball** | `/8ball <question>` | `&8ball <question>` | Ask the magic 8-ball |
| **coinflip** | `/coinflip` | `&coinflip` | Flip a coin |
| **roll** | `/roll [sides]` | `&roll [sides]` | Roll a dice (default d6) |
| **choose** | `/choose <a, b, c>` | `&choose <a, b, c>` | Choose one option from a comma-separated list |
| **rps** | `/rps <choice>` | `&rps <choice>` | Play rock-paper-scissors |

### Info Commands

| Command | Slash | Prefix | Description |
|---------|-------|--------|-------------|
| **membercount** | `/membercount` | `&membercount` | Show the server member count |
| **roleinfo** | `/roleinfo <role>` | `&roleinfo <role>` | Show information about a role |
| **channelinfo** | `/channelinfo [channel]` | `&channelinfo [channel]` | Show information about a channel |

### GitHub Commands

All GitHub commands are under the `github` / `gh` group:

| Command | Slash | Prefix | Description |
|---------|-------|--------|-------------|
| **github repo** | `/github repo <owner/repo>` | `&github repo <owner/repo>` | View repository information |
| **github user** | `/github user <username>` | `&github user <username>` | View a user/organisation profile |
| **github search-repos** | `/github search-repos <query>` | `&github search-repos <query>` | Search repositories |
| **github search-users** | `/github search-users <query>` | `&github search-users <query>` | Search users |

### Admin Commands (Requires Administrator Permission)

| Command | Slash | Prefix | Description |
|---------|-------|--------|-------------|
| **setlevel** | `/setlevel <user> <level>` | `&setlevel <user> <level>` | Set a user's level |
| **addxp** | `/addxp <user> <amount>` | `&addxp <user> <amount>` | Add XP to a user |
| **resetlevel** | `/resetlevel <user>` | `&resetlevel <user>` | Reset a user's level data |
| **resetalllevels** | `/resetalllevels CONFIRM` | `&resetalllevels CONFIRM` | Reset all server levels (requires CONFIRM) |
| **setlevelchannel** | `/setlevelchannel <channel>` | `&setlevelchannel #channel` | Set channel for level-up announcements |
| **addrole** | `/addrole <level> <role>` | `&addrole <level> @role` | Add role reward for a level |
| **removerole** | `/removerole <level>` | `&removerole <level>` | Remove role reward for a level |
| **rolerewards** | `/rolerewards` | `&rolerewards` | List all configured role rewards |

## Setup

### Prerequisites

- Python 3.14+
- Discord Bot Token
- A PostgreSQL database URL (`DATABASE_URL`)
- Required intents: Message Content, Server Members, Guilds

### Installation

1. **Clone the repository**
```bash
cd "Miku"
```

2. **Install dependencies**
```bash
pip install -e .
# or
uv pip install -e .
```

3. **Configure environment**
Create a `.env` file or export the environment variable:
```bash
export DISCORD_BOT_TOKEN='your_bot_token_here'
export DATABASE_URL='postgresql+asyncpg://user:password@host:5432/database'
```

4. **Run the bot**
```bash
python main.py
```

## Bot Setup on Discord Developer Portal

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select your existing one
3. Go to the **Bot** section
4. Enable these **Privileged Gateway Intents**:
   - Message Content Intent
   - Server Members Intent
   - Presence Intent (optional)
5. Copy your bot token and set it as `DISCORD_BOT_TOKEN`
6. Go to **OAuth2 > URL Generator**
7. Select scopes: `bot` and `applications.commands`
8. Select permissions: 
   - Send Messages
   - Embed Links
   - Read Message History
   - Use Slash Commands
9. Use the generated URL to invite your bot

## Leveling Formula

The bot uses a formula similar to Arcane/MEE6:

```
XP Required = 5 × (level²) + (50 × level) + 100
```

- **XP per message**: 15-25 (random)
- **Cooldown**: 60 seconds between XP gains
- **Level calculation**: Based on total accumulated XP

### Example XP Requirements

| Level | Total XP Needed |
|-------|----------------|
| 1 | 155 |
| 5 | 1,000 |
| 10 | 3,850 |
| 20 | 14,600 |
| 50 | 89,250 |

## Project Structure

```
main.py                 # Entrypoint (adds src/ to path and runs the bot)
├── pyproject.toml       # Dependencies
├── requirements.txt     # Python dependencies (optional)
├── README.md            # Documentation
└── src/
   ├── bot.py            # Bot setup, DB init, cog loading
   ├── cogs/
   │   ├── leveling.py    # XP/levels/leaderboards
   │   ├── help.py        # Interactive help menu
   │   ├── github.py      # GitHub lookup/search
   │   ├── utilities.py   # Utility commands
   │   ├── fun.py         # Fun commands
   │   └── info.py        # Info commands
   └── utils/
      ├── database.py     # PostgreSQL (asyncpg) DB layer
      ├── github_client.py # GitHub API client
      └── rank_card.py     # Rank card generator
```

## Features Breakdown

### XP Gain System
- Automatic XP on every message (excluding bots and DMs)
- 60-second cooldown per user per guild
- Random XP gain (15-25) to prevent farming
- Level-up notifications with embeds

### Rank Card
Shows:
- User's rank in the server
- Current level
- Total messages sent
- Progress bar to next level
- Total XP earned

### Leaderboard
- Shows top 50 members
- Paginated display (10 per page)
- Medal emojis for top 3 ()
- Displays level, XP, and message count

### Database
- Async PostgreSQL operations (asyncpg)
- Tracks: user_id, guild_id, xp, level, messages, last_message_time
- Auto-creates tables on first run
- Data persists across restarts

## Customization

### Change XP Gain Range
Edit in `src/cogs/leveling.py`:
```python
xp_gain = random.randint(15, 25)  # Change these values
```

### Change Cooldown Time
Edit in `src/cogs/leveling.py`:
```python
self.cooldown_time = 60  # seconds
```

### Change Command Prefix
Edit in `src/bot.py`:
```python
command_prefix='&'  # Change to your preferred prefix
```

### Modify Level Formula
Edit the `calculate_level` and `calculate_xp_for_level` methods in `src/cogs/leveling.py`

## Troubleshooting

### Bot doesn't respond to commands
- Make sure Message Content intent is enabled
- Check that the bot has proper permissions in the server
- Verify the bot token is correct

### Slash commands not showing
- Wait up to 1 hour for global commands to sync
- Try kicking and re-inviting the bot
- Check bot has `applications.commands` scope

### Database errors
- Verify `DATABASE_URL` points to a reachable PostgreSQL instance
- Confirm the database user can create tables (first run)

## License

This project is open source and available for personal and educational use.

## Contributing

Feel free to fork, modify, and improve this bot! Contributions are welcome.

## Tips

- The bot works in multiple servers simultaneously
- Each server has its own leaderboard and levels
- Levels don't transfer between servers
- Admin commands require Discord administrator permission
- Level-up messages auto-delete after 10 seconds to reduce spam

---

Made with using discord.py
