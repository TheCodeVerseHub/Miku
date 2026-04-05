"""
Help Cog - Interactive help system with dropdown menu
Complete rewrite for Miku Bot

Beginner notes:
- This cog uses Discord "UI components" (a dropdown/select) to let users switch
    between help categories without sending multiple messages.
- The UI is handled by a `discord.ui.View` + `discord.ui.Select`.

Hybrid command gotcha:
- `@commands.hybrid_command` can be used as BOTH prefix and slash.
- `ephemeral=True` and `ctx.defer()` only work for slash (interactions).
    In prefix mode, passing `ephemeral` raises errors.
    That's why `help_command()` uses a small local `send()` wrapper.

Select option gotcha:
- Discord rejects an empty emoji value. If you don't want an emoji, omit the
    `emoji=` field entirely.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging

logger = logging.getLogger('miku.help')

EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord blurple

# ============================================================================
# Help Embed Builders
# ============================================================================

def create_main_help_embed(bot: commands.Bot) -> discord.Embed:
    """Create the main help menu embed"""
    embed = discord.Embed(
        title=" Miku - Help",
        description="A feature-rich Discord leveling bot with XP tracking and customizable rewards",
        color=EMBED_COLOR
    )
    
    embed.add_field(
        name=" Command Prefix",
        value="**Text:** `&` (e.g., `&help`)\n**Slash:** `/` (e.g., `/help`)",
        inline=False
    )
    
    embed.add_field(
        name=" Available Categories",
        value=(
            "**Leveling** - XP tracking, ranks, and leaderboards\n"
            "**Admin** - Server management and configuration commands\n"
            "**Utility** - Helpful general commands\n"
            "**GitHub** - Repository and user lookup\n\n"
            "Use the dropdown menu below to explore categories!"
        ),
        inline=False
    )
    
    embed.add_field(
        name=" Support",
        value="Need help? Found a bug? Contact the bot owner!",
        inline=False
    )
    
    embed.set_footer(text=f"Connected to {len(bot.guilds)} servers | Made with ")
    
    return embed

def create_utility_help_embed() -> discord.Embed:
    """Create utility category help embed"""
    embed = discord.Embed(
        title=" Utility Commands",
        description="Helpful commands that work in any server (no moderation)",
        color=EMBED_COLOR,
    )

    commands_list = [
        {
            "name": "ping",
            "usage": "&ping",
            "description": "Check if the bot is responsive and view latency",
        },
        {
            "name": "uptime",
            "usage": "&uptime",
            "description": "Show how long the bot has been online",
        },
        {
            "name": "about",
            "usage": "&about",
            "description": "Bot information and basic stats",
        },
        {
            "name": "invite",
            "usage": "&invite",
            "description": "Get an invite link for the bot",
        },
        {
            "name": "avatar",
            "usage": "&avatar [user]",
            "description": "Show a user's avatar",
        },
        {
            "name": "userinfo",
            "usage": "&userinfo [user]",
            "description": "Show information about a member",
        },
        {
            "name": "serverinfo",
            "usage": "&serverinfo",
            "description": "Show information about the current server",
        },
    ]

    for cmd in commands_list:
        embed.add_field(
            name=f"&{cmd['name']}",
            value=f"**Usage:** `{cmd['usage']}`\n{cmd['description']}",
            inline=False,
        )

    embed.set_footer(text=" Tip: Both prefix (&) and slash (/) commands work!")
    return embed

def create_leveling_help_embed() -> discord.Embed:
    """Create leveling category help embed"""
    embed = discord.Embed(
        title=" Leveling Commands",
        description="Commands for checking ranks, XP, leaderboards, and progression",
        color=EMBED_COLOR
    )
    
    commands = [
        {
            "name": "rank",
            "aliases": "level, lvl",
            "usage": "&rank [user]",
            "description": "View rank card with level, XP progress, and server rank"
        },
        {
            "name": "xp",
            "aliases": "",
            "usage": "&xp [user]",
            "description": "View detailed XP statistics and progression to next level"
        },
        {
            "name": "leaderboard",
            "aliases": "lb, top",
            "usage": "&leaderboard [page]",
            "description": "Display server leaderboard showing top members by XP"
        },
        {
            "name": "rolerewards",
            "aliases": "listroles",
            "usage": "&rolerewards",
            "description": "View all configured role rewards for leveling up"
        }
    ]
    
    for cmd in commands:
        alias_text = f"\n**Aliases:** {cmd['aliases']}" if cmd['aliases'] else ""
        embed.add_field(
            name=f"{'&' if cmd['usage'].startswith('&') else '/'}{cmd['name']}",
            value=f"**Usage:** `{cmd['usage']}`{alias_text}\n{cmd['description']}",
            inline=False
        )
    
    embed.set_footer(text=" Tip: Both prefix (&) and slash (/) commands work!")
    
    return embed

def create_admin_help_embed() -> discord.Embed:
    """Create admin category help embed"""
    embed = discord.Embed(
        title=" Admin Commands",
        description="Server administration commands (requires Administrator permission)",
        color=EMBED_COLOR
    )
    
    commands = [
        {
            "name": "setlevel",
            "usage": "&setlevel <user> <level>",
            "description": "Set a user's level to a specific value"
        },
        {
            "name": "addxp",
            "usage": "&addxp <user> <amount>",
            "description": "Add a specific amount of XP to a user"
        },
        {
            "name": "resetlevel",
            "usage": "&resetlevel <user>",
            "description": "Reset a user's level and XP data"
        },
        {
            "name": "resetalllevels",
            "usage": "&resetalllevels CONFIRM",
            "description": " Reset ALL server level data (requires typing CONFIRM)"
        },
        {
            "name": "setlevelchannel",
            "usage": "&setlevelchannel [channel]",
            "description": "Set or remove the level-up announcement channel"
        },
        {
            "name": "addrole",
            "usage": "&addrole <level> <role>",
            "description": "Add a role reward for reaching a specific level"
        },
        {
            "name": "removerole",
            "usage": "&removerole <level>",
            "description": "Remove a role reward from a specific level"
        }
    ]
    
    for cmd in commands:
        embed.add_field(
            name=f"{'&' if cmd['usage'].startswith('&') else '/'}{cmd['name']}",
            value=f"**Usage:** `{cmd['usage']}`\n{cmd['description']}",
            inline=False
        )
    
    embed.set_footer(text=" All admin commands require Administrator permission")

    return embed

def create_github_help_embed() -> discord.Embed:
    """Create GitHub category help embed"""
    embed = discord.Embed(
        title="GitHub Commands",
        description="Commands for looking up GitHub repositories, users, and searching GitHub",
        color=EMBED_COLOR
    )

    commands = [
        {
            "name": "github repo",
            "aliases": "",
            "usage": "&github repo <owner/repo>",
            "description": "View repository info (stars, forks, language, license, topics, and more)"
        },
        {
            "name": "github user",
            "aliases": "",
            "usage": "&github user <username>",
            "description": "View a GitHub user or organisation profile"
        },
        {
            "name": "github search-repos",
            "aliases": "sr",
            "usage": "&github search-repos <query>",
            "description": "Search GitHub repositories and show the top results"
        },
        {
            "name": "github search-users",
            "aliases": "su",
            "usage": "&github search-users <query>",
            "description": "Search GitHub users and show the top results"
        }
    ]

    for cmd in commands:
        alias_text = f"\n**Aliases:** {cmd['aliases']}" if cmd['aliases'] else ""
        embed.add_field(
            name=f"&{cmd['name']}",
            value=f"**Usage:** `{cmd['usage']}`{alias_text}\n{cmd['description']}",
            inline=False
        )

    embed.set_footer(text=" Tip: Use &gh as a shorthand for &github")

    return embed

# ============================================================================
# Interactive View Components
# ============================================================================

class CategorySelect(discord.ui.Select):
    """Dropdown menu for selecting help categories"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        options = [
            discord.SelectOption(
                label="Home",
                description="Return to main help menu",
                value="home"
            ),
            discord.SelectOption(
                label="Leveling",
                description="XP tracking and rank commands",
                value="leveling"
            ),
            discord.SelectOption(
                label="Admin",
                description="Server administration commands",
                value="admin"
            ),
            discord.SelectOption(
                label="Utility",
                description="General helpful commands",
                value="utility"
            ),
            discord.SelectOption(
                label="GitHub",
                description="Repository and user lookup",
                value="github"
            )
        ]
        
        super().__init__(
            placeholder="Select a category...",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection"""
        category = self.values[0]
        
        if category == "home":
            embed = create_main_help_embed(self.bot)
        elif category == "leveling":
            embed = create_leveling_help_embed()
        elif category == "admin":
            embed = create_admin_help_embed()
        elif category == "utility":
            embed = create_utility_help_embed()
        elif category == "github":
            embed = create_github_help_embed()
        else:
            embed = create_main_help_embed(self.bot)
        
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    """Interactive view for help menu"""
    
    def __init__(self, bot: commands.Bot, author_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.author_id = author_id
        self.add_item(CategorySelect(bot))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to interact"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This help menu is not for you! Use `/help` to get your own.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self):
        """Called when the view times out"""
        # Disable all components
        for item in self.children:
            if hasattr(item, "disabled"):
                setattr(item, "disabled", True)

# ============================================================================
# Help Cog
# ============================================================================

class Help(commands.Cog):
    """Interactive help command system"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def cog_load(self):
        """Called when cog is loaded"""
        logger.info("Help cog loaded")
    
    @commands.hybrid_command(
        name='help',
        description='Display bot commands and information'
    )
    @app_commands.describe(command='Get help for a specific command')
    async def help_command(self, ctx: commands.Context, command: Optional[str] = None):
        """Display interactive help menu or help for a specific command"""

        async def send(*args, **kwargs):
            # `ephemeral` is only valid for interaction responses.
            if getattr(ctx, "interaction", None) is None:
                kwargs.pop("ephemeral", None)
            return await ctx.send(*args, **kwargs)
        
        if command:
            # Show help for specific command
            cmd = self.bot.get_command(command)
            
            if not cmd:
                embed = discord.Embed(
                    title=" Command Not Found",
                    description=f"Command `{command}` doesn't exist.\nUse `/help` to see all commands.",
                    color=discord.Color.red()
                )
                await send(embed=embed, ephemeral=True)
                return
            
            # Build specific command help
            embed = discord.Embed(
                title=f"Command: {cmd.name}",
                description=cmd.description or cmd.help or "No description available",
                color=EMBED_COLOR
            )
            
            # Add aliases
            if hasattr(cmd, 'aliases') and cmd.aliases:
                embed.add_field(
                    name="Aliases",
                    value=", ".join(f"`{alias}`" for alias in cmd.aliases),
                    inline=False
                )
            
            # Add usage
            usage = f"`&{cmd.name}`"
            if cmd.signature:
                usage = f"`&{cmd.name} {cmd.signature}`"
            embed.add_field(name="Usage", value=usage, inline=False)
            
            # Add permissions if any
            if hasattr(cmd, 'checks') and cmd.checks:
                perms = []
                for check in cmd.checks:
                    if hasattr(check, '__name__'):
                        if 'administrator' in check.__name__:
                            perms.append("Administrator")
                if perms:
                    embed.add_field(
                        name="Required Permissions",
                        value=", ".join(perms),
                        inline=False
                    )
            
            await send(embed=embed)
        
        else:
            # Show interactive help menu
            embed = create_main_help_embed(self.bot)
            view = HelpView(self.bot, ctx.author.id)
            await send(embed=embed, view=view)

async def setup(bot: commands.Bot):
    """Setup function to add cog to bot"""
    await bot.add_cog(Help(bot))

