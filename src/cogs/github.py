"""
GitHub Cog - Look up repositories, users, and search GitHub.

Commands (all under the ``github`` / ``gh`` group):
    &github repo <owner/repo>       - Repository information
    &github user <username>          - User or organisation profile
    &github search-repos <query>     - Search repositories
    &github search-users <query>     - Search users

Hybrid command notes (same as leveling cog):
- ``ephemeral=True`` and ``ctx.defer()`` only work for slash (interaction) mode.
- The ``_send`` / ``_maybe_defer`` helpers keep both modes working.
"""

import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.github_client import (
    GitHubAPIError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
)

logger = logging.getLogger("miku.github")

EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord blurple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(iso: str | None) -> str:
    """Convert an ISO-8601 date string to a Discord relative timestamp."""
    if not iso:
        return "N/A"
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return f"<t:{int(dt.timestamp())}:R>"


def _trunc(text: str | None, length: int = 200) -> str:
    """Truncate *text* to *length* characters, adding an ellipsis if needed."""
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= length else text[: length - 1] + "\u2026"


def _fmt(n: int | None) -> str:
    """Format a number with thousand separators."""
    return f"{n:,}" if n is not None else "0"


def _parse_repo(raw: str) -> tuple[str, str] | None:
    """Parse *raw* into ``(owner, repo)``.

    Accepts ``owner/repo``, ``owner repo``, and full GitHub URLs.
    Returns ``None`` if the input cannot be parsed.
    """
    raw = (
        raw.strip()
        .removeprefix("https://github.com/")
        .removeprefix("http://github.com/")
        .strip("/")
    )
    parts = raw.replace(" ", "/").split("/")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return None


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class GitHub(commands.Cog):
    """GitHub integration - look up repos, users, and search GitHub."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._client = GitHubClient(token=os.getenv("GITHUB_TOKEN"))

    async def cog_load(self) -> None:
        """Called when cog is loaded."""
        logger.info("GitHub cog loaded")

    async def cog_unload(self) -> None:
        """Called when cog is unloaded."""
        logger.info("GitHub cog unloaded")
        try:
            await self._client.close()
        except Exception:
            logger.exception("Failed to close GitHubClient")

    # -- hybrid-command helpers (same pattern as leveling cog) ---------------

    async def _send(self, ctx: commands.Context, *args, **kwargs):
        """Send helper that strips interaction-only kwargs in prefix mode."""
        if getattr(ctx, "interaction", None) is None:
            kwargs.pop("ephemeral", None)
        return await ctx.send(*args, **kwargs)

    async def _maybe_defer(self, ctx: commands.Context) -> None:
        """Defer only when invoked as a slash command."""
        if getattr(ctx, "interaction", None) is not None:
            await ctx.defer()

    # -- shared error handler ------------------------------------------------

    async def _handle_error(self, ctx: commands.Context, exc: GitHubAPIError) -> None:
        """Send a user-friendly error embed for a GitHub API exception."""
        if isinstance(exc, GitHubNotFoundError):
            embed = discord.Embed(
                title="Not Found",
                description=str(exc),
                color=discord.Color.red(),
            )
        elif isinstance(exc, GitHubRateLimitError):
            embed = discord.Embed(
                title="Rate Limited",
                description=str(exc),
                color=discord.Color.orange(),
            )
        else:
            embed = discord.Embed(
                title="GitHub API Error",
                description=f"Something went wrong: {exc}",
                color=discord.Color.red(),
            )
        await self._send(ctx, embed=embed, ephemeral=True)

    # ========================================================================
    # Command group
    # ========================================================================

    @commands.hybrid_group(
        name="github",
        aliases=["gh"],
        description="Look up GitHub repositories and users",
        fallback="help",
    )
    async def github(self, ctx: commands.Context) -> None:
        """Show a short usage overview when invoked without a subcommand."""
        embed = discord.Embed(
            title="GitHub Commands",
            description=(
                "Use a subcommand to look up GitHub data:\n\n"
                "**`github repo <owner/repo>`** - Repository info\n"
                "**`github user <username>`** - User profile\n"
                "**`github search-repos <query>`** - Search repositories\n"
                "**`github search-users <query>`** - Search users"
            ),
            color=EMBED_COLOR,
        )
        embed.set_footer(text="Alias: gh | Both prefix (&) and slash (/) work")
        await self._send(ctx, embed=embed)

    # -- /github repo -------------------------------------------------------

    @github.command(name="repo", description="View GitHub repository information")
    @app_commands.describe(repository="Repository in owner/repo format (or a GitHub URL)")
    async def github_repo(self, ctx: commands.Context, *, repository: str) -> None:
        """Display detailed information about a GitHub repository."""
        parsed = _parse_repo(repository)
        if not parsed:
            await self._send(
                ctx,
                embed=discord.Embed(
                    title="Invalid Format",
                    description=(
                        "Please provide a repository in `owner/repo` format.\n"
                        "Examples: `python/cpython`, `https://github.com/python/cpython`"
                    ),
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        owner, repo = parsed
        await self._maybe_defer(ctx)

        try:
            data = await self._client.get_repo(owner, repo)
        except GitHubAPIError as exc:
            await self._handle_error(ctx, exc)
            return

        full_name = data.get("full_name", f"{owner}/{repo}")
        html_url = data.get("html_url", f"https://github.com/{owner}/{repo}")

        embed = discord.Embed(
            title=full_name,
            url=html_url,
            description=_trunc(data.get("description"), 300) or "No description provided",
            color=EMBED_COLOR,
        )

        if data.get("owner", {}).get("avatar_url"):
            embed.set_thumbnail(url=data["owner"]["avatar_url"])

        embed.add_field(name="Language", value=data.get("language") or "N/A", inline=True)
        embed.add_field(name="Stars", value=_fmt(data.get("stargazers_count")), inline=True)
        embed.add_field(name="Forks", value=_fmt(data.get("forks_count")), inline=True)

        embed.add_field(name="Open Issues", value=_fmt(data.get("open_issues_count")), inline=True)

        license_info = data.get("license")
        license_name = license_info.get("spdx_id") or license_info.get("name") if license_info else None
        embed.add_field(name="License", value=license_name or "None", inline=True)

        embed.add_field(name="Default Branch", value=data.get("default_branch", "N/A"), inline=True)

        embed.add_field(name="Created", value=_ts(data.get("created_at")), inline=True)
        embed.add_field(name="Last Updated", value=_ts(data.get("updated_at")), inline=True)

        topics = data.get("topics")
        if topics:
            embed.add_field(
                name="Topics",
                value=", ".join(f"`{t}`" for t in topics[:15]),
                inline=False,
            )

        embed.set_footer(text="GitHub")
        await self._send(ctx, embed=embed)

    # -- /github user -------------------------------------------------------

    @github.command(name="user", description="View a GitHub user or organisation profile")
    @app_commands.describe(username="GitHub username")
    async def github_user(self, ctx: commands.Context, *, username: str) -> None:
        """Display a GitHub user or organisation profile."""
        await self._maybe_defer(ctx)

        try:
            data = await self._client.get_user(username.strip())
        except GitHubAPIError as exc:
            await self._handle_error(ctx, exc)
            return

        display_name = data.get("name") or data.get("login", username)
        html_url = data.get("html_url", f"https://github.com/{username}")
        user_type = data.get("type", "User")

        embed = discord.Embed(
            title=f"{display_name} ({user_type})" if data.get("name") else display_name,
            url=html_url,
            description=_trunc(data.get("bio"), 300) or "No bio provided",
            color=EMBED_COLOR,
        )

        if data.get("avatar_url"):
            embed.set_thumbnail(url=data["avatar_url"])

        embed.add_field(name="Username", value=data.get("login", "N/A"), inline=True)
        embed.add_field(name="Public Repos", value=_fmt(data.get("public_repos")), inline=True)

        followers = _fmt(data.get("followers"))
        following = _fmt(data.get("following"))
        embed.add_field(name="Followers / Following", value=f"{followers} / {following}", inline=True)

        if data.get("location"):
            embed.add_field(name="Location", value=data["location"], inline=True)
        if data.get("company"):
            embed.add_field(name="Company", value=data["company"], inline=True)
        if data.get("blog"):
            blog = data["blog"]
            if not blog.startswith(("http://", "https://")):
                blog = f"https://{blog}"
            embed.add_field(name="Website", value=blog, inline=True)

        embed.add_field(name="Joined", value=_ts(data.get("created_at")), inline=True)

        embed.set_footer(text="GitHub")
        await self._send(ctx, embed=embed)

    # -- /github search-repos -----------------------------------------------

    @github.command(
        name="search-repos",
        aliases=["sr"],
        description="Search GitHub repositories",
    )
    @app_commands.describe(query="Search query")
    async def github_search_repos(self, ctx: commands.Context, *, query: str) -> None:
        """Search GitHub repositories and show the top results."""
        await self._maybe_defer(ctx)

        try:
            data = await self._client.search_repos(query)
        except GitHubAPIError as exc:
            await self._handle_error(ctx, exc)
            return

        total = data.get("total_count", 0)
        items = data.get("items", [])

        if not items:
            embed = discord.Embed(
                title="No Results",
                description=f"No repositories found for **{_trunc(query, 100)}**.",
                color=EMBED_COLOR,
            )
            await self._send(ctx, embed=embed)
            return

        embed = discord.Embed(
            title="Repository Search Results",
            description=f"Results for **{_trunc(query, 100)}**",
            color=EMBED_COLOR,
        )

        for repo in items[:5]:
            name = repo.get("full_name", "unknown")
            url = repo.get("html_url", "")
            desc = _trunc(repo.get("description"), 100) or "No description"
            stars = _fmt(repo.get("stargazers_count"))
            lang = repo.get("language") or ""
            lang_str = f" | {lang}" if lang else ""

            embed.add_field(
                name=f"{name}",
                value=f"[View on GitHub]({url})\n{desc}\n{stars} stars{lang_str}",
                inline=False,
            )

        embed.set_footer(text=f"Showing {len(items[:5])} of {total:,} results")
        await self._send(ctx, embed=embed)

    # -- /github search-users -----------------------------------------------

    @github.command(
        name="search-users",
        aliases=["su"],
        description="Search GitHub users",
    )
    @app_commands.describe(query="Search query")
    async def github_search_users(self, ctx: commands.Context, *, query: str) -> None:
        """Search GitHub users and show the top results."""
        await self._maybe_defer(ctx)

        try:
            data = await self._client.search_users(query)
        except GitHubAPIError as exc:
            await self._handle_error(ctx, exc)
            return

        total = data.get("total_count", 0)
        items = data.get("items", [])

        if not items:
            embed = discord.Embed(
                title="No Results",
                description=f"No users found for **{_trunc(query, 100)}**.",
                color=EMBED_COLOR,
            )
            await self._send(ctx, embed=embed)
            return

        embed = discord.Embed(
            title="User Search Results",
            description=f"Results for **{_trunc(query, 100)}**",
            color=EMBED_COLOR,
        )

        for user in items[:5]:
            login = user.get("login", "unknown")
            url = user.get("html_url", "")
            user_type = user.get("type", "User")

            embed.add_field(
                name=login,
                value=f"[View on GitHub]({url}) | {user_type}",
                inline=False,
            )

        embed.set_footer(
            text=f"Showing {len(items[:5])} of {total:,} results | Use /github user <name> for full profile"
        )
        await self._send(ctx, embed=embed)


async def setup(bot: commands.Bot) -> None:
    """Setup function to add cog to bot."""
    await bot.add_cog(GitHub(bot))
