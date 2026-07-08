<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/Miku-5865F2?style=for-the-badge&logo=discord&logoColor=white">
    <img alt="Miku" src="https://img.shields.io/badge/Miku-5865F2?style=for-the-badge&logo=discord&logoColor=white">
  </picture>

  <p align="center">
    <strong>A feature-rich Discord leveling bot with XP tracking, role rewards, analytics, and a modern web dashboard.</strong>
  </p>

  <p align="center">
    <a href="#features"><strong>Features</strong></a> ·
    <a href="#quick-start"><strong>Quick Start</strong></a> ·
    <a href="#configuration"><strong>Configuration</strong></a> ·
    <a href="#commands"><strong>Commands</strong></a> ·
    <a href="#dashboard"><strong>Dashboard</strong></a> ·
    <a href="#contributing"><strong>Contributing</strong></a>
  </p>

  <p align="center">
    <img src="https://img.shields.io/badge/python-3.14+-blue?style=flat-square&logo=python&logoColor=white" alt="Python 3.14+">
    <img src="https://img.shields.io/badge/discord.py-2.7+-blueviolet?style=flat-square&logo=discord&logoColor=white" alt="discord.py 2.7+">
    <img src="https://img.shields.io/badge/postgresql-16+-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL 16+">
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT License">
    <img src="https://img.shields.io/badge/status-active-success?style=flat-square" alt="Status">
  </p>
</div>

---

## Features

### 🎮 Leveling System
- **XP Tracking** — Earn XP by sending messages with configurable cooldowns
- **Rank Cards** — Beautiful generated rank cards with progress bars
- **Leaderboards** — Server-wide rankings with pagination and search
- **Multiple Formulas** — Quadratic, Linear, Cubic, and custom XP formulas
- **Role Rewards** — Automatically assign roles at configurable level thresholds

### ⚙️ Administration
- **Per-Guild Configuration** — Independent settings for every server
- **XP Multipliers** — Channel, role, and category-specific XP multipliers
- **XP Restrictions** — Block or allow channels, roles, and categories
- **Audit Logging** — Complete history of admin actions
- **Automatic Cleanup** — Removes departed users from leaderboards

### 📊 Web Dashboard
- **Real-Time Analytics** — XP trends, activity patterns, and member statistics
- **Leaderboard Browser** — Search, filter, and manage rankings
- **User Profiles** — Detailed user stats with XP history and activity timeline
- **Role Reward Manager** — Visual role picker with search and edit
- **Server Settings** — Configure everything from your browser
- **Responsive Design** — Full mobile support with dark theme

### 🔧 Technical
- **PostgreSQL** — Robust and scalable database backend
- **Async/Await** — Fully asynchronous Python with `asyncpg`
- **Hybrid Commands** — Works with both prefix (`&`) and slash (`/`) commands
- **Modular Architecture** — Cogs, services, and utilities separated by concern
- **CI/CD** — GitHub Actions for linting, testing, and security

---

## Quick Start

### Prerequisites
- Python 3.14+
- PostgreSQL 16+
- Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/miku.git
cd miku

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
```

### Configuration

Edit `.env` with your credentials:

```env
# Required
DISCORD_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://user:pass@localhost:5432/miku

# Dashboard (optional)
DASHBOARD_CLIENT_ID=your_oauth2_client_id
DASHBOARD_CLIENT_SECRET=your_oauth2_client_secret
DASHBOARD_REDIRECT_URI=http://localhost:8000/auth/callback
DASHBOARD_SESSION_SECRET=your_session_secret_here
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8000
```

### Running

```bash
# Start the bot
python main.py

# Start the dashboard (separate terminal)
cd dashboard
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
# Build and run with Docker Compose
docker compose up -d
```

---

## Commands

### 👤 User Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `&rank` / `/rank` | View rank card with XP progress | `&rank [user]` |
| `&xp` / `/xp` | View detailed XP statistics | `&xp [user]` |
| `&leaderboard` / `/leaderboard` | Server rankings by XP | `&leaderboard [page]` |
| `&rolerewards` / `/rolerewards` | View configured role rewards | `&rolerewards` |
| `&help` / `/help` | Interactive help system | `&help [command]` |

### 🛠️ Admin Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `&setlevel` / `/setlevel` | Set a user's level | `&setlevel <user> <level>` |
| `&addxp` / `/addxp` | Add XP to a user | `&addxp <user> <amount>` |
| `&removexp` / `/removexp` | Remove XP from a user | `&removexp <user> <amount>` |
| `&resetlevel` / `/resetlevel` | Reset a user's data | `&resetlevel <user>` |
| `&resetalllevels` / `/resetalllevels` | Reset all server data | `&resetalllevels CONFIRM` |
| `&clean-lb` / `/clean-lb` | Remove departed users from leaderboard | `&clean-lb` |
| `&setlevelchannel` / `/setlevelchannel` | Set announcement channel | `&setlevelchannel [#channel]` |
| `&addrole` / `/addrole` | Add a role reward | `&addrole <level> <role>` |
| `&removerole` / `/removerole` | Remove a role reward | `&removerole <level>` |

### 🎯 Fun Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `&8ball` / `/8ball` | Ask the magic 8-ball | `&8ball <question>` |
| `&coinflip` / `/coinflip` | Flip a coin | `&coinflip` |
| `&roll` / `/roll` | Roll a dice | `&roll [sides]` |
| `&choose` / `/choose` | Pick from options | `&choose <a, b, c>` |
| `&rps` / `/rps` | Rock-paper-scissors | `&rps <choice>` |

### ℹ️ Info Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `&ping` / `/ping` | Check bot latency | `&ping` |
| `&uptime` / `/uptime` | Show bot uptime | `&uptime` |
| `&about` / `/about` | Bot information | `&about` |
| `&invite` / `/invite` | Get invite link | `&invite` |
| `&serverinfo` / `/serverinfo` | Server information | `&serverinfo` |
| `&userinfo` / `/userinfo` | User information | `&userinfo [user]` |
| `&membercount` / `/membercount` | Server member count | `&membercount` |
| `&roleinfo` / `/roleinfo` | Role information | `&roleinfo <role>` |

### 📦 GitHub Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `&github repo` | View repository info | `&github repo <owner/repo>` |
| `&github user` | View GitHub profile | `&github user <username>` |
| `&github search-repos` | Search repositories | `&github search-repos <query>` |
| `&github search-users` | Search users | `&github search-users <query>` |

---

## Dashboard

The Miku Dashboard is a modern web interface for managing your server's leveling system.

### Pages

| Page | Description |
|------|-------------|
| **Overview** | Real-time server statistics and quick actions |
| **Leveling** | XP configuration, cooldowns, and formula preview |
| **Role Rewards** | Visual role reward management with search |
| **Leaderboard** | Searchable, paginated rankings with XP bars |
| **Analytics** | Charts for XP, messages, activity patterns |
| **User Profiles** | Detailed stats, XP history, and admin actions |
| **Settings** | General server configuration |

### Screenshots

> Screenshots coming soon.

### API

The dashboard exposes a REST API for programmatic access:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/me` | GET | Current user information |
| `/api/guilds/{id}/settings` | GET/POST | Guild settings |
| `/api/guilds/{id}/rewards` | GET/POST/DELETE | Role rewards |
| `/api/guilds/{id}/leaderboard` | GET | Paginated leaderboard |
| `/api/guilds/{id}/analytics` | GET | Server analytics |
| `/api/guilds/{id}/users/{uid}` | GET | User profile |
| `/api/guilds/{id}/users/{uid}/history` | GET | User XP history |
| `/api/guilds/{id}/stats/overview` | GET | Dashboard overview |

---

## Project Structure

```
miku/
├── main.py                     # Entry point
├── pyproject.toml              # Project configuration
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
│
├── src/
│   ├── bot.py                  # Bot initialization and setup
│   │
│   ├── cogs/
│   │   ├── leveling.py         # XP tracking and leveling commands
│   │   ├── help.py             # Interactive help system
│   │   ├── fun.py              # Fun and games commands
│   │   ├── utilities.py        # Utility commands
│   │   ├── info.py             # Information commands
│   │   └── github.py           # GitHub integration
│   │
│   ├── services/
│   │   ├── level_service.py    # XP calculation business logic
│   │   └── formula_registry.py # XP formula implementations
│   │
│   └── utils/
│       ├── database.py         # PostgreSQL (asyncpg) operations
│       ├── rank_card.py        # Rank card image generation
│       └── github_client.py    # GitHub API client
│
├── dashboard/
│   ├── backend/
│   │   ├── main.py             # FastAPI application
│   │   ├── auth.py             # Discord OAuth2
│   │   ├── config.py           # Dashboard configuration
│   │   ├── discord_api.py      # Discord REST API wrapper
│   │   └── templates/          # Jinja2 templates
│   └── static/
│       ├── style.css           # Dark theme stylesheet
│       └── api.js              # API client and helpers
│
├── .github/
│   ├── workflows/              # CI/CD pipelines
│   ├── dependabot.yml          # Dependency updates
│   └── CODEOWNERS              # Code ownership
│
├── docs/                       # Documentation
├── tests/                      # Test suite
└── bot/                        # Legacy extension system
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Discord Gateway                        │
├─────────────────────────────────────────────────────────┤
│                     src/bot.py                            │
│                  MikuBot(commands.Bot)                    │
├──────────┬──────────────┬────────────────┬──────────────┤
│  Cogs    │   Services    │    Utils       │  Dashboard   │
├──────────┼──────────────┼────────────────┼──────────────┤
│ leveling │ level_service│ database.py    │  FastAPI      │
│ help     │ formula_reg  │ rank_card.py   │  asyncpg      │
│ fun      │              │ github_client  │  Jinja2       │
│ utilities│              │                │  Alpine.js    │
│ info     │              │                │  Chart.js     │
│ github   │              │                │              │
└──────────┴──────────────┴────────────────┴──────────────┘
                       │
                       ▼
              ┌──────────────┐
              │  PostgreSQL  │
              │  (Neon.tech) │
              └──────────────┘
```

---

## Technology Stack

- **Runtime:** Python 3.14+ (async/await)
- **Framework:** discord.py 2.7+
- **Database:** PostgreSQL 16+ via asyncpg
- **Dashboard:** FastAPI + Jinja2 + Alpine.js + Chart.js
- **Images:** Pillow (rank cards)
- **HTTP:** httpx, aiohttp
- **Auth:** Discord OAuth2 (itsdangerous sessions)
- **CI/CD:** GitHub Actions (Ruff, Bandit, pip-audit)

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/miku.git
cd miku

# Install with dev dependencies
uv sync --group dev

# Create a branch
git checkout -b feature/your-feature

# Make your changes and run checks
uv run ruff check .
uv run ruff format --check .
uv run pytest

# Commit with conventional commit message
git commit -m "feat: add your feature"
```

### Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Roadmap

- [x] XP tracking and leveling system
- [x] Role rewards and leaderboards
- [x] Web dashboard with analytics
- [x] Interactive help system
- [x] GitHub integration
- [x] CI/CD pipelines
- [ ] Moderation commands suite
- [ ] Welcome/leave message system
- [ ] Temporary voice channel system
- [ ] Giveaway system
- [ ] Translation support (i18n)
- [ ] Docker Compose deployment
- [ ] Automated testing suite

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Credits

- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Dashboard powered by [FastAPI](https://fastapi.tiangolo.com/) and [Alpine.js](https://alpinejs.dev/)
- Charts by [Chart.js](https://www.chartjs.org/)
- Deployed on [Neon](https://neon.tech) PostgreSQL

---

<div align="center">
  <sub>Made with ❤️ by the Miku team</sub>
</div>
