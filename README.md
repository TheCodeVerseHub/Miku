# Miku - Discord Leveling Bot

A feature-rich Discord leveling bot inspired by Arcane, with support for both **slash commands** and **prefix commands** (prefix: `&`).

## Features

- **XP & Leveling System** - Users gain 15-25 XP per message (60-second cooldown)
- **Rank Cards** - Beautiful embeds showing user rank, level, and progress
- **Leaderboards** - View top members by XP with pagination
- **Hybrid Commands** - Works with both `/` slash commands and `&` prefix
- **SQLite Database** - Persistent data storage with async operations
- **Rich Embeds** - Clean, visually appealing messages
- **Admin Tools** - Manage user levels and XP
- **Web Dashboard** - Modern Next.js dashboard with real-time statistics and management

## Commands

### User Commands

| Command | Slash | Prefix | Description |
|---------|-------|--------|-------------|
| **rank** | `/rank [user]` | `&rank [user]` | Check your or another user's rank and level |
| **level** | `/level [user]` | `&level [user]` | Alias for rank command |
| **leaderboard** | `/leaderboard [page]` | `&leaderboard [page]` | View the server leaderboard (top 50) |
| **lb** | `/lb [page]` | `&lb [page]` | Alias for leaderboard |
| **xp** | `/xp [user]` | `&xp [user]` | Check detailed XP information |

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

## Web Dashboard

Miku comes with a modern web dashboard built with **Next.js 14** and **React** for managing your bot and viewing statistics.

### Dashboard Features

- 🔐 **Discord OAuth2 Login** - Secure authentication
- 📊 **Live Statistics** - Real-time server stats and analytics
- 🏆 **Interactive Leaderboards** - View top members with pagination
- ⚙️ **Leveling Configuration** - Set level-up channels and role rewards
- 🎮 **Multi-Server Management** - Manage all servers from one place
- 📱 **Responsive Design** - Works on desktop, tablet, and mobile
- 🎨 **Beautiful UI** - Discord-themed design with Tailwind CSS

### Quick Start (Local Development)

```bash
cd dash
npm install
cp .env.example .env.local
# Edit .env.local with your Discord OAuth2 credentials
npm run dev
```

Dashboard will be available at [http://localhost:3000](http://localhost:3000)

### Production Deployment (FREE!)

The dashboard can be deployed for **completely free** on Vercel while your bot runs on WispByte or any other hosting service.

**Quick Deploy:**
1. Bot runs on WispByte (includes API server)
2. Dashboard deploys to Vercel
3. They communicate via REST API

See complete deployment guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**

For detailed setup instructions, see:
- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete deployment guide
- [dash/QUICK_DEPLOY.md](dash/QUICK_DEPLOY.md) - Quick reference
- [dash/SETUP.md](dash/SETUP.md) - Local development setup

## Running Bot with Dashboard Support

To enable dashboard connectivity, run both the bot and API server:

```bash
python start_all.py
```

This starts:
- Discord bot (handles messages, commands)
- REST API server (serves data to dashboard)

For production deployment guide, see [DEPLOYMENT.md](DEPLOYMENT.md)

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
start_all.py           # Run bot + API server (for deployment)
├── pyproject.toml         # Dependencies
├── requirements.txt       # Python dependencies
├── README.md              # Documentation
├── DEPLOYMENT.md          # Production deployment guide
├── LEVELING_CONFIG.md     # Leveling configuration guide
├── data/                  # Database files (auto-created)
│   └── leveling.db
├── src/
│   ├── bot.py            # Bot setup and initialization
│   ├── api_server.py     # FastAPI server for dashboard
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── leveling.py   # Leveling system cog
│   │   └── help.py       # Help command
│   └── utils/
│       ├── __init__.py
│       ├── database.py   # Database operations
│       └── rank_card.py  # Rank card generator
└── dash/                 # Next.js Dashboard
    ├── src/
    │   ├── pages/        # Next.js pages
    │   ├── components/   # React components
    │   ├── lib/          # Utility functions
    │   └── types/        # TypeScript types
    ├── public/           # Static files
    ├── vercel.json       # Vercel deployment config
    ├── QUICK_DEPLOY.md   # Quick deployment guide
    └── package.json      # Node dependencie
    │   └── leveling.py   # Leveling system cog
    └── utils/
        ├── __init__.py
        └── database.py   # Database operations
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
- Async SQLite operations
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
- Ensure the `data/` directory is writable
- Check file permissions for `leveling.db`

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
