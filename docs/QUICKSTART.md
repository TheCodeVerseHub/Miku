# Quick Start Guide

## Step 1: Install Dependencies using UV

```bash
uv sync
```

## Step 2: Get Your Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name (e.g., "Miku Bot")
3. Go to the **Bot** section in the left sidebar
4. Click "Reset Token" to get your bot token (save it securely!)
5. Enable these **Privileged Gateway Intents**:
   - **Message Content Intent** (required)
   - **Server Members Intent** (required)
   - **Presence Intent** (optional -- currently unused)

## Step 3: Set Up Environment Variable

### Using an environment file

First copy the example environment file as `.env`:

```bash
cp .env.example .env
```

Then edit the new `.env` file and add your token.

### Using the command line or custom start script

1. On Linux/Mac

   ```bash
   export DISCORD_TOKEN='your_bot_token_here'
   ```

2. On Windows (using Powershell)

   ```powershell
   $env:DISCORD_TOKEN='your_bot_token_here'
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
   - _(or just click Administrator if you're feeling brave - **NOT RECOMMENDED OUTSIDE OF DEVELOPMENT PURPOSES**)_
4. Copy the generated URL and open it in your browser
5. Select a server and authorize the bot

## Step 5: Run the Bot

Open your terminal (or use your existing one) and run this command:

```bash
uv run main.py
```

You should see something like this:

```log
Loaded cog: cogs.leveling
Leveling database initialized
Logged in as YourBotName (ID: 123456789)
------
Synced X command(s)
```

## Step 6: Test Commands

In your Discord server, try:

### Prefix Commands (using &)

- `&rank` - Check your rank
- `&leaderboard` - View server leaderboard
- `&xp` - Check your XP details

### Slash Commands

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

- Read the full [README.md](README.md) for an overview of all features
<!--
This got nuked in the refactor, maybe we'll remember to update this.
- Customize XP gain and cooldown in [src/cogs/leveling.py](src/cogs/leveling.py)
  -->
- Explore additional admin-only configuration commands (for members with Administrator permissions)

## Troubleshooting and Common Mistakes

### "Import discord could not be resolved"

Your virtual environment did not install all the required packages.

Try: `uv sync`

If that doesn't fix the issue, please verify that you're running the bot from the correct virtual environment.
You can tell you're using the correct virtual environment when your bash prompt looks like the one below:

```sh
(Miku) [script@script-pc Miku]$
```

### Bot doesn't respond

- Check that Message Content Intent is enabled
- Verify the bot token is correct
- Make sure the bot is online in your server

### Slash commands not showing

- You may need to wait up to 1 hour for commands to sync globally
- Try removing and re-inviting the bot, or
- Use guild-specific sync (see Discord.py docs)

## More Help

- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/docs)

---

Happy leveling!
