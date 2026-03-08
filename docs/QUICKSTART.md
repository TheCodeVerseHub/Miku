# Quick Start Guide

## Step 1: Install Dependencies

Choose one of the following methods:

### Method 1: Using pip
```bash
pip install discord.py aiosqlite
```

### Method 2: Using requirements.txt
```bash
pip install -r requirements.txt
```

### Method 3: Using uv (faster)
```bash
uv pip install discord.py aiosqlite
```

## Step 2: Get Your Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name (e.g., "Miku Leveling Bot")
3. Go to the **Bot** section in the left sidebar
4. Click "Reset Token" to get your bot token (save it securely!)
5. Enable these **Privileged Gateway Intents**:
   - **Message Content Intent** (required)
   - **Server Members Intent** (required)
   - **Presence Intent** (optional)

## Step 3: Set Up Environment Variable

### Linux/Mac:
```bash
export DISCORD_BOT_TOKEN='your_bot_token_here'
```

### Windows (PowerShell):
```powershell
$env:DISCORD_BOT_TOKEN='your_bot_token_here'
```

### Or create a .env file:
```bash
cp .env.example .env
# Then edit .env and add your token
```

**Note:** If using .env file, install python-dotenv:
```bash
pip install python-dotenv
```

And add this to [src/bot.py](src/bot.py) before `TOKEN` line:
```python
from dotenv import load_dotenv
load_dotenv()
```

## Step 4: Invite Your Bot

1. In Discord Developer Portal, go to **OAuth2 > URL Generator**
2. Select scopes:
   - `bot`
   - `applications.commands`
3. Select bot permissions:
   - Send Messages
   - Embed Links
   - Read Message History
   - Use Slash Commands
4. Copy the generated URL and open it in your browser
5. Select a server and authorize the bot

## Step 5: Run the Bot

```bash
python main.py
```

You should see:
```
Loaded cog: cogs.leveling
Leveling database initialized
Logged in as YourBotName (ID: 123456789)
------
Synced X command(s)
```

## Step 6: Test Commands

In your Discord server, try:

### Prefix Commands (using &):
- `&rank` - Check your rank
- `&leaderboard` - View server leaderboard
- `&xp` - Check your XP details

### Slash Commands:
- `/rank` - Check your rank
- `/leaderboard` - View server leaderboard
- `/xp` - Check your XP details

## You're Done!

Your bot is now running and will:
- Award 15-25 XP per message (60-second cooldown)
- Track user levels and ranks
- Show leaderboards
- Send level-up notifications

## What's Next?

- Read the full [README.md](README.md) for all features
- Customize XP gain and cooldown in [src/cogs/leveling.py](src/cogs/leveling.py)
- Explore admin commands (requires Administrator permission)

## Troubleshooting

### "Import discord could not be resolved"
- Run: `pip install discord.py aiosqlite`

### Bot doesn't respond
- Check that Message Content Intent is enabled
- Verify the bot token is correct
- Make sure the bot is online in your server

### Slash commands not showing
- Wait up to 1 hour for commands to sync globally
- Try removing and re-inviting the bot, or
- Use guild-specific sync (see Discord.py docs)

## More Help

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/docs)

---

Happy leveling!
