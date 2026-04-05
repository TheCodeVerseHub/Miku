"""
Miku - Discord Leveling Bot
Clean rewrite with PostgreSQL only

Contributing quick map (start here):
- Bot entrypoint: `Miku/main.py` imports `src/bot.py` and runs `main()`.
- Cogs (features/commands/events): `src/cogs/` (e.g. `leveling.py`, `help.py`).
- Database layer: `src/utils/database.py` (asyncpg, tables, queries).

Typical flow:
1) Bot starts -> `setup_hook()` initializes DB and loads cogs.
2) Cogs register listeners/commands.
3) For XP: `Leveling.on_message` -> read/update DB -> optionally announce level-up.
"""

import discord
from discord.ext import commands
import os
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from utils import database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('miku')

# Load environment variables
load_dotenv()

# Bot configuration
class BotConfig:
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    PREFIX = '&'
    EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord blurple

# Bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = False  # Not needed for this bot

class MikuBot(commands.Bot):
    """Custom bot class for Miku"""
    
    def __init__(self):
        super().__init__(
            command_prefix=BotConfig.PREFIX,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True
        )
        self.config = BotConfig
        # Used by the Utility cog for `uptime`.
        self.start_time = datetime.now(timezone.utc)
        
    async def setup_hook(self):
        """Setup hook called when bot starts"""
        # Startup order matters:
        # 1) Ensure DB schema exists (tables/indexes)
        # 2) Load cogs (they may query the DB)
        # 3) Sync slash commands (so /commands appear in Discord)

        # Initialize database
        await database.init_db()
        logger.info("Database initialized")
        
        # Load cogs
        await self.load_cogs()
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def load_cogs(self):
        """Load all cogs"""
        cogs = [
            'cogs.leveling',
            'cogs.help',
            'cogs.github',
            'cogs.utilities',
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info(f'Connected to {len(self.guilds)} guilds')
        logger.info('Bot is ready!')
        
        # Set bot activity
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | {BotConfig.PREFIX}help"
            )
        )

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Global command error handler.

        We intentionally ignore unknown commands so random messages like
        `&rewards` don't spam the console.
        """
        # Ignore unknown commands completely.
        if isinstance(error, commands.CommandNotFound):
            return

        # If a command defines its own error handler, don't double-handle.
        if ctx.command is not None and ctx.command.has_error_handler():
            return

        # For everything else, fall back to default logging/behavior.
        raise error
    
    async def on_guild_join(self, guild):
        """Called when bot joins a guild"""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | {BotConfig.PREFIX}help"
            )
        )
    
    async def on_guild_remove(self, guild):
        """Called when bot leaves a guild"""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | {BotConfig.PREFIX}help"
            )
        )
    
    async def close(self):
        """Cleanup when bot shuts down"""
        logger.info("Shutting down...")
        await database.close_pool()
        await super().close()

async def main():
    """Main entry point"""
    bot = MikuBot()

    token = BotConfig.TOKEN
    if not token:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN is not set. Add it to your environment or a `.env` file."
        )
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await bot.close()

if __name__ == '__main__':
    asyncio.run(main())
