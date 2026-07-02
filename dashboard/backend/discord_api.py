"""Discord REST API wrapper for the dashboard.

Calls Discord's API using the bot token to enrich database data
with usernames, avatars, role names, etc. Results are cached briefly
to avoid hitting rate limits.
"""

import logging
from typing import Any
from cachetools import TTLCache
import httpx

from .config import config

logger = logging.getLogger("dashboard.discord_api")

BASE = "https://discord.com/api/v10"

# Caches keyed by guild_id
_role_cache: TTLCache = TTLCache(maxsize=64, ttl=60)
_member_cache: TTLCache = TTLCache(maxsize=64, ttl=30)
_bot_user_id: str | None = None
_bot_id_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)

_headers: dict[str, str] | None = None


def _auth() -> dict[str, str]:
    global _headers
    if _headers is None:
        token = config.bot_token
        if not token:
            logger.warning("DISCORD_BOT_TOKEN not configured — Discord API calls will fail")
        _headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    return _headers


async def _get(path: str) -> list[Any] | dict[str, Any] | None:
    """Make a GET request to Discord's REST API."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{BASE}{path}", headers=_auth(), timeout=10)
            if resp.status_code == 429:
                retry = float(resp.headers.get("Retry-After", 5))
                logger.warning("Rate limited, retrying after %.1fs", retry)
                import asyncio
                await asyncio.sleep(retry)
                return await _get(path)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Discord API %s %s: %s", e.request.method, e.request.url, e.response.text)
            return None
        except Exception as e:
            logger.error("Discord API request failed: %s", e)
            return None


# ---------------------------------------------------------------------------
# Bot user info
# ---------------------------------------------------------------------------


async def _get_bot_user_id() -> str | None:
    """Fetch the bot's own user ID from Discord and cache it."""
    global _bot_user_id
    if _bot_user_id is not None:
        return _bot_user_id

    cached = _bot_id_cache.get(0)
    if cached:
        _bot_user_id = cached
        return _bot_user_id

    data = await _get("/users/@me")
    if data and isinstance(data, dict):
        _bot_user_id = data["id"]
        _bot_id_cache[0] = _bot_user_id
        return _bot_user_id
    return None


async def get_bot_member(guild_id: int) -> dict[str, Any] | None:
    """Fetch the bot's own member object in a guild."""
    bot_id = await _get_bot_user_id()
    if not bot_id:
        return None
    return await _get(f"/guilds/{guild_id}/members/{bot_id}")


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


async def get_guild_roles(guild_id: int) -> list[dict[str, Any]]:
    """Fetch all roles for a guild, cached for 60s."""
    if guild_id in _role_cache:
        return _role_cache[guild_id]

    data = await _get(f"/guilds/{guild_id}/roles")
    if data is None:
        return []

    roles: list[dict[str, Any]] = []
    for r in data:
        roles.append({
            "id": r["id"],
            "name": r["name"],
            "color": r["color"],
            "position": r["position"],
            "managed": r["managed"],
            "permissions": r["permissions"],
            "icon": r.get("icon"),
        })

    roles.sort(key=lambda r: r["position"], reverse=True)
    _role_cache[guild_id] = roles
    return roles


async def get_assignable_roles(guild_id: int) -> list[dict[str, Any]]:
    """Return assignable roles — excludes @everyone, managed, and roles above the bot's highest role."""
    roles = await get_guild_roles(guild_id)

    # Fetch the bot's member info to determine its top role position.
    bot_top = 0
    bot_member = await get_bot_member(guild_id)
    if bot_member and isinstance(bot_member, dict):
        bot_role_ids = bot_member.get("roles", [])
        if bot_role_ids:
            bot_top = max(
                (r["position"] for r in roles if r["id"] in bot_role_ids),
                default=0,
            )

    return [
        r for r in roles
        if r["name"] != "@everyone"
        and not r["managed"]
        and r["position"] < bot_top
    ]


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


async def get_guild_members(guild_id: int) -> dict[str, dict[str, Any]]:
    """Fetch all guild members, returned as {user_id: member_data}, cached for 30s."""
    if guild_id in _member_cache:
        return _member_cache[guild_id]

    members: dict[str, dict[str, Any]] = {}
    after = None

    while True:
        params = f"?limit=1000"
        if after:
            params += f"&after={after}"

        data = await _get(f"/guilds/{guild_id}/members{params}")
        if not data or not isinstance(data, list):
            break

        for m in data:
            uid = m["user"]["id"]
            user = m["user"]
            avatar_hash = user.get("avatar")
            disc = user.get("discriminator", "0")

            if avatar_hash:
                ext = "gif" if avatar_hash.startswith("a_") else "png"
                avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar_hash}.{ext}"
            else:
                default = int(disc) % 5 if disc != "0" else 0
                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{default}.png"

            members[uid] = {
                "user_id": uid,
                "username": user.get("name", "Unknown"),
                "display_name": user.get("global_name") or user.get("name", "Unknown"),
                "discriminator": disc if disc != "0" else None,
                "avatar_url": avatar_url,
            }

        if len(data) < 1000:
            break
        after = data[-1]["user"]["id"]

    _member_cache[guild_id] = members
    return members


def default_user(user_id: int | str) -> dict[str, Any]:
    """Return a fallback user object for a user not found in the guild."""
    uid = str(user_id)
    default = int(uid[-1]) % 5
    return {
        "user_id": uid,
        "username": "Unknown User",
        "display_name": "Unknown User",
        "discriminator": None,
        "avatar_url": f"https://cdn.discordapp.com/embed/avatars/{default}.png",
    }


async def enrich_leaderboard(guild_id: int, db_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge Discord member data into raw DB leaderboard rows."""
    members = await get_guild_members(guild_id)

    enriched: list[dict[str, Any]] = []
    for row in db_rows:
        uid = str(row["user_id"])
        member = members.get(uid) or default_user(uid)
        enriched.append({
            **member,
            "level": row.get("level", 0),
            "xp": row.get("xp", 0),
            "messages": row.get("messages", 0),
        })
    return enriched
