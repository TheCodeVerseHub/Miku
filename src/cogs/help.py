"""
Help Cog - Interactive help system with category navigation, search, and pagination.
"""

from __future__ import annotations

import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger('miku.help')

BLURPLE = 0x5865F2
PREFIX = "&"
COMMANDS_PER_PAGE = 6

CATEGORIES: dict[str, dict] = {
    "leveling": {
        "emoji": "🎮",
        "name": "Leveling",
        "description": "XP tracking, ranks, and leaderboards",
        "commands": [
            {"name": "rank", "description": "View your or another user's rank card", "usage": f"{PREFIX}rank [user]", "aliases": ["level", "lvl"]},
            {"name": "xp", "description": "View detailed XP information", "usage": f"{PREFIX}xp [user]", "aliases": []},
            {"name": "leaderboard", "description": "View the server leaderboard", "usage": f"{PREFIX}leaderboard [page]", "aliases": ["lb", "top"]},
            {"name": "rolerewards", "description": "View all configured role rewards", "usage": f"{PREFIX}rolerewards", "aliases": ["listroles"]},
            {"name": "clean-lb", "description": "Remove departed users from the leaderboard", "usage": f"{PREFIX}clean-lb", "aliases": [], "permissions": ["Administrator"]},
        ],
    },
    "admin": {
        "emoji": "⚙️",
        "name": "Admin",
        "description": "Server management and configuration commands",
        "commands": [
            {"name": "setlevel", "description": "Set a user's level to a specific value", "usage": f"{PREFIX}setlevel <user> <level>", "aliases": [], "permissions": ["Administrator"]},
            {"name": "addxp", "description": "Add XP to a user", "usage": f"{PREFIX}addxp <user> <amount>", "aliases": [], "permissions": ["Administrator"]},
            {"name": "removexp", "description": "Remove XP from a user", "usage": f"{PREFIX}removexp <user> <amount>", "aliases": [], "permissions": ["Administrator"]},
            {"name": "resetlevel", "description": "Reset a user's level and XP data", "usage": f"{PREFIX}resetlevel <user>", "aliases": [], "permissions": ["Administrator"]},
            {"name": "resetalllevels", "description": "Reset ALL server level data", "usage": f"{PREFIX}resetalllevels CONFIRM", "aliases": [], "permissions": ["Administrator"]},
            {"name": "setlevelchannel", "description": "Set the level-up announcement channel", "usage": f"{PREFIX}setlevelchannel [channel]", "aliases": [], "permissions": ["Administrator"]},
            {"name": "addrole", "description": "Add a role reward for reaching a level", "usage": f"{PREFIX}addrole <level> <role>", "aliases": [], "permissions": ["Administrator"]},
            {"name": "removerole", "description": "Remove a role reward from a level", "usage": f"{PREFIX}removerole <level>", "aliases": [], "permissions": ["Administrator"]},
        ],
    },
    "utility": {
        "emoji": "🛠️",
        "name": "Utility",
        "description": "Helpful commands that work in any server",
        "commands": [
            {"name": "ping", "description": "Check if the bot is responsive and view latency", "usage": f"{PREFIX}ping", "aliases": []},
            {"name": "uptime", "description": "Show how long the bot has been online", "usage": f"{PREFIX}uptime", "aliases": []},
            {"name": "about", "description": "Bot information, stats, and version info", "usage": f"{PREFIX}about", "aliases": []},
            {"name": "invite", "description": "Get an invite link to add the bot to your server", "usage": f"{PREFIX}invite", "aliases": []},
            {"name": "avatar", "description": "Show a user's avatar", "usage": f"{PREFIX}avatar [user]", "aliases": []},
        ],
    },
    "fun": {
        "emoji": "🎯",
        "name": "Fun",
        "description": "Games and random commands",
        "commands": [
            {"name": "8ball", "description": "Ask the magic 8-ball a question", "usage": f"{PREFIX}8ball <question>", "aliases": []},
            {"name": "coinflip", "description": "Flip a coin for heads or tails", "usage": f"{PREFIX}coinflip", "aliases": []},
            {"name": "roll", "description": "Roll a dice with custom sides", "usage": f"{PREFIX}roll [sides]", "aliases": []},
            {"name": "choose", "description": "Pick one option from a comma-separated list", "usage": f"{PREFIX}choose <a, b, c>", "aliases": []},
            {"name": "rps", "description": "Play rock-paper-scissors against the bot", "usage": f"{PREFIX}rps <rock|paper|scissors>", "aliases": []},
        ],
    },
    "info": {
        "emoji": "ℹ️",
        "name": "Info",
        "description": "Server, role, channel, and user information",
        "commands": [
            {"name": "membercount", "description": "Show the server's total member count", "usage": f"{PREFIX}membercount", "aliases": []},
            {"name": "roleinfo", "description": "Show detailed information about a role", "usage": f"{PREFIX}roleinfo <role>", "aliases": []},
            {"name": "channelinfo", "description": "Show information about a channel", "usage": f"{PREFIX}channelinfo [channel]", "aliases": []},
            {"name": "userinfo", "description": "Show information about a server member", "usage": f"{PREFIX}userinfo [user]", "aliases": []},
            {"name": "serverinfo", "description": "Show information about the current server", "usage": f"{PREFIX}serverinfo", "aliases": []},
        ],
    },
    "github": {
        "emoji": "📦",
        "name": "GitHub",
        "description": "Repository and user lookup via the GitHub API",
        "commands": [
            {"name": "github repo", "description": "View repository information (stars, forks, language, license)", "usage": f"{PREFIX}github repo <owner/repo>", "aliases": []},
            {"name": "github user", "description": "View a GitHub user or organisation profile", "usage": f"{PREFIX}github user <username>", "aliases": []},
            {"name": "github search-repos", "description": "Search GitHub repositories by query", "usage": f"{PREFIX}github search-repos <query>", "aliases": ["sr"]},
            {"name": "github search-users", "description": "Search GitHub users by query", "usage": f"{PREFIX}github search-users <query>", "aliases": ["su"]},
        ],
    },
}


def build_main_embed(bot: commands.Bot) -> discord.Embed:
    embed = discord.Embed(
        title="Miku - Help",
        description="A feature-rich Discord leveling bot with XP tracking, ranks, and customizable role rewards.",
        color=BLURPLE,
    )
    embed.add_field(
        name="Command Prefix",
        value=f"**Text:** `{PREFIX}` (e.g., `{PREFIX}help`)\n**Slash:** `/` (e.g., `/help`)",
        inline=False,
    )
    cats = []
    for cfg in CATEGORIES.values():
        count = len(cfg["commands"])
        cats.append(f"{cfg['emoji']} **{cfg['name']}** — {cfg['description']} ({count} commands)")
    embed.add_field(
        name="Categories",
        value="\n".join(cats),
        inline=False,
    )
    embed.add_field(
        name="Need Help?",
        value=f"Use the **select menu** below to browse a category, or type `{PREFIX}help <command>` for details on a specific command.",
        inline=False,
    )
    embed.set_footer(text=f"Connected to {len(bot.guilds)} servers")
    return embed


def build_category_embed(category_key: str, page: int = 0) -> discord.Embed:
    cfg = CATEGORIES[category_key]
    cmds = cfg["commands"]
    total_pages = max(1, (len(cmds) + COMMANDS_PER_PAGE - 1) // COMMANDS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * COMMANDS_PER_PAGE
    end = start + COMMANDS_PER_PAGE
    page_cmds = cmds[start:end]

    embed = discord.Embed(
        title=f"{cfg['emoji']} {cfg['name']} Commands",
        description=cfg["description"],
        color=BLURPLE,
    )

    for cmd in page_cmds:
        parts = [cmd["description"]]
        parts.append(f"Usage: `{cmd['usage']}`")
        if cmd.get("aliases"):
            parts.append(f"Aliases: {', '.join(f'`{a}`' for a in cmd['aliases'])}")
        if cmd.get("permissions"):
            parts.append(f"Permissions: {', '.join(f'`{p}`' for p in cmd['permissions'])}")
        embed.add_field(
            name=f"{PREFIX}{cmd['name']}",
            value="\n".join(parts),
            inline=True,
        )

    if total_pages > 1:
        embed.set_footer(text=f"Page {page + 1} of {total_pages} \u2022 {len(cmds)} commands")
    else:
        embed.set_footer(text=f"{len(cmds)} commands")
    return embed


def build_command_detail_embed(cmd_name: str) -> discord.Embed | None:
    for cfg in CATEGORIES.values():
        for cmd in cfg["commands"]:
            if cmd["name"] == cmd_name:
                embed = discord.Embed(
                    title=f"Command: {PREFIX}{cmd['name']}",
                    description=cmd["description"],
                    color=BLURPLE,
                )
                embed.add_field(name="Usage", value=f"`{cmd['usage']}`", inline=False)
                if cmd.get("aliases"):
                    embed.add_field(
                        name="Aliases",
                        value=", ".join(f"`{a}`" for a in cmd["aliases"]),
                        inline=False,
                    )
                if cmd.get("permissions"):
                    embed.add_field(
                        name="Required Permissions",
                        value=", ".join(f"`{p}`" for p in cmd["permissions"]),
                        inline=False,
                    )
                embed.set_footer(text=f"Category: {cfg['emoji']} {cfg['name']}")
                return embed
    return None


def build_search_embed(query: str) -> discord.Embed:
    results = []
    for cfg in CATEGORIES.values():
        for cmd in cfg["commands"]:
            if query.lower() in cmd["name"].lower() or query.lower() in cmd["description"].lower():
                results.append((cfg, cmd))

    embed = discord.Embed(
        title="Search Results",
        color=BLURPLE,
    )

    if not results:
        embed.description = f"No commands found matching `{query}`."
        embed.set_footer(text="Try a different search term")
        return embed

    embed.description = f"Found **{len(results)}** result{'s' if len(results) != 1 else ''} for `{query}`:"
    for cfg, cmd in results[:10]:
        embed.add_field(
            name=f"{cfg['emoji']} {PREFIX}{cmd['name']}",
            value=f"{cmd['description']}\nUsage: `{cmd['usage']}`",
            inline=True,
        )
    if len(results) > 10:
        embed.set_footer(text=f"Showing 10 of {len(results)} results — use a more specific query")
    else:
        embed.set_footer(text=f"{len(results)} result{'s' if len(results) != 1 else ''} found")
    return embed


def _get_required_permissions(cmd: commands.Command) -> list[str]:
    perms = []
    for check in cmd.checks:
        req = getattr(check, "__required_permissions__", None)
        if req:
            for perm, value in req.items():
                if value:
                    perms.append(perm.replace("_", " ").title())
        elif hasattr(check, "__name__"):
            name = check.__name__.lower()
            if "administrator" in name:
                perms.append("Administrator")
    return perms


def _get_cooldown(cmd: commands.Command) -> str | None:
    try:
        buckets = cmd._buckets
        if buckets is not None:
            cooldown = buckets._cooldown
            if cooldown is not None:
                return f"{cooldown.rate} use{'s' if cooldown.rate > 1 else ''} per {cooldown.per:.0f}s"
    except Exception:
        logger.debug("Failed to read cooldown for command %s", cmd.name)
    return None


def build_real_command_embed(cmd: commands.Command) -> discord.Embed:
    embed = discord.Embed(
        title=f"Command: {PREFIX}{cmd.qualified_name}",
        description=cmd.description or cmd.help or "No description available.",
        color=BLURPLE,
    )

    usage_parts = [f"{PREFIX}{cmd.qualified_name}"]
    if cmd.signature:
        usage_parts.append(cmd.signature)
    embed.add_field(name="Usage", value=f"`{' '.join(usage_parts)}`", inline=False)

    if cmd.aliases:
        embed.add_field(
            name="Aliases",
            value=", ".join(f"`{a}`" for a in cmd.aliases),
            inline=False,
        )

    perms = _get_required_permissions(cmd)
    if perms:
        embed.add_field(
            name="Required Permissions",
            value=", ".join(f"`{p}`" for p in perms),
            inline=False,
        )

    cooldown = _get_cooldown(cmd)
    if cooldown:
        embed.add_field(name="Cooldown", value=cooldown, inline=False)

    return embed


class SearchModal(discord.ui.Modal, title="Search Commands"):
    query = discord.ui.TextInput(
        label="Search query",
        placeholder="Type a command name or description to search...",
        min_length=1,
        max_length=100,
    )

    def __init__(self, bot: commands.Bot, author_id: int, message: discord.Message):
        super().__init__()
        self.bot = bot
        self.author_id = author_id
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        embed = build_search_embed(self.query.value)
        await interaction.response.edit_message(embed=embed, view=self.view)


class CategorySelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label="Home",
                description="Return to the main help menu",
                emoji="🏠",
                value="home",
            ),
        ]
        for key, cfg in CATEGORIES.items():
            options.append(discord.SelectOption(
                label=cfg["name"],
                description=cfg["description"],
                emoji=cfg["emoji"],
                value=key,
            ))
        super().__init__(placeholder="Select a category...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        view: HelpView = self.view
        if value == "home":
            view.current_category = None
            view.current_page = 0
            embed = build_main_embed(self.bot)
        else:
            view.current_category = value
            view.current_page = 0
            embed = build_category_embed(value, 0)
        view._update_buttons()
        await interaction.response.edit_message(embed=embed, view=view)


class HomeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="🏠", label="Home", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        view.current_category = None
        view.current_page = 0
        view._update_buttons()
        embed = build_main_embed(view.bot)
        await interaction.response.edit_message(embed=embed, view=view)


class SearchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="🔍", label="Search", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        modal = SearchModal(bot=view.bot, author_id=view.author_id, message=interaction.message)
        modal.view = view
        await interaction.response.send_modal(modal)


class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="◀", label="Prev", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        if view.current_category and view.current_page > 0:
            view.current_page -= 1
            embed = build_category_embed(view.current_category, view.current_page)
            view._update_buttons()
            await interaction.response.edit_message(embed=embed, view=view)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="▶", label="Next", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: HelpView = self.view
        if view.current_category:
            cmds = CATEGORIES[view.current_category]["commands"]
            total_pages = max(1, (len(cmds) + COMMANDS_PER_PAGE - 1) // COMMANDS_PER_PAGE)
            if view.current_page < total_pages - 1:
                view.current_page += 1
                embed = build_category_embed(view.current_category, view.current_page)
                view._update_buttons()
                await interaction.response.edit_message(embed=embed, view=view)


class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author_id: int):
        super().__init__(timeout=180)
        self.bot = bot
        self.author_id = author_id
        self.current_category: str | None = None
        self.current_page: int = 0

        self.add_item(CategorySelect(bot))
        self.add_item(HomeButton())
        self.add_item(PrevButton())
        self.add_item(NextButton())
        self.add_item(SearchButton())

    def _update_buttons(self):
        for item in self.children:
            if isinstance(item, PrevButton):
                item.disabled = self.current_category is None or self.current_page <= 0
            elif isinstance(item, NextButton):
                if self.current_category is None:
                    item.disabled = True
                else:
                    cmds = CATEGORIES[self.current_category]["commands"]
                    total_pages = max(1, (len(cmds) + COMMANDS_PER_PAGE - 1) // COMMANDS_PER_PAGE)
                    item.disabled = self.current_page >= total_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This help menu is not for you! Use `/help` to get your own.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        message = self.message
        if message is not None:
            try:
                await message.edit(view=self)
            except Exception:
                logger.debug("Failed to disable buttons on help timeout")


class Help(commands.Cog):
    """Interactive help command system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        logger.info("Help cog loaded")

    @commands.hybrid_command(name="help", description="Display bot commands and information")
    @app_commands.describe(command="Get help for a specific command")
    async def help_command(self, ctx: commands.Context, command: str | None = None):
        async def send(*args, **kwargs):
            if getattr(ctx, "interaction", None) is None:
                kwargs.pop("ephemeral", None)
            return await ctx.send(*args, **kwargs)

        if command:
            cmd = self.bot.get_command(command)
            if cmd is not None:
                embed = build_real_command_embed(cmd)
            else:
                embed = build_command_detail_embed(command)

            if embed is None:
                embed = discord.Embed(
                    title="Command Not Found",
                    description=f"Command `{command}` doesn't exist.\nUse `{PREFIX}help` to see all commands.",
                    color=discord.Color.red(),
                )
            await send(embed=embed, ephemeral=embed.color == discord.Color.red())
            return

        embed = build_main_embed(self.bot)
        view = HelpView(self.bot, ctx.author.id)
        message = await send(embed=embed, view=view)
        if isinstance(message, discord.Message):
            view.message = message


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
