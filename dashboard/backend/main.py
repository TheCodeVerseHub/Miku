"""FastAPI dashboard backend for Miku Discord bot."""

# ruff: noqa: E402 — sys.path.insert before local imports

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer
from jinja2 import Environment, FileSystemLoader
import asyncpg

# Add bot src/ to path so we can reuse the bot's database module
BOT_SRC = str((Path(__file__).parent.parent.parent / "src").resolve())
if BOT_SRC not in sys.path:
    sys.path.insert(0, BOT_SRC)

from cachetools import TTLCache

from .config import config
from .discord_api import (
    enrich_leaderboard,
    get_assignable_roles,
    get_guild_members,
    default_user,
)
from .auth import (
    exchange_code,
    get_current_user as _get_current_user,
    get_user_guilds as _get_user_guilds,
    get_oauth_url,
)

logger = logging.getLogger("dashboard")

# Cache Discord API responses to avoid rate limits
_user_cache: TTLCache = TTLCache(maxsize=256, ttl=60)
_guild_cache: TTLCache = TTLCache(maxsize=256, ttl=30)


async def get_current_user(access_token: str) -> dict | None:
    if access_token in _user_cache:
        return _user_cache[access_token]
    user = await _get_current_user(access_token)
    if user:
        _user_cache[access_token] = user
    return user


async def get_user_guilds(access_token: str) -> list[dict]:
    if access_token in _guild_cache:
        return _guild_cache[access_token]
    guilds = await _get_user_guilds(access_token)
    if guilds is not None:
        _guild_cache[access_token] = guilds
    return guilds or []


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Miku Dashboard")

# Templates (using raw Jinja2 to avoid Starlette 1.x compat issues)
_templates_dir = str(Path(__file__).parent / "templates")
_jinja_env = Environment(loader=FileSystemLoader(_templates_dir))


def render(name: str, **context) -> HTMLResponse:
    template = _jinja_env.get_template(name)
    html = template.render(**context)
    return HTMLResponse(html)


# Static files
static_dir = str(Path(__file__).parent.parent / "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Session serializer
serializer = URLSafeTimedSerializer(config.session_secret, salt="session")

# Database pool (lazy-init, same style as bot)
_pool: asyncpg.Pool | None = None


async def get_db() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        if not config.database_url:
            raise RuntimeError("DATABASE_URL not configured")
        _pool = await asyncpg.create_pool(
            config.database_url,
            min_size=1,
            max_size=5,
            command_timeout=30,
            statement_cache_size=0,
        )
    return _pool


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def make_session(data: dict) -> str:
    return serializer.dumps(data)


def read_session(token: str) -> dict | None:
    try:
        return serializer.loads(token, max_age=86400 * 7)
    except Exception:
        return None


async def require_auth(request: Request) -> dict:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(401, "Not authenticated")
    data = read_session(token)
    if not data or "access_token" not in data:
        raise HTTPException(401, "Session expired")
    user = await get_current_user(data["access_token"])
    if not user:
        raise HTTPException(401, "Token invalid")
    return data


async def require_guild_access(request: Request, guild_id: int) -> tuple[dict, dict]:
    session_data = await require_auth(request)
    guilds = await get_user_guilds(session_data["access_token"])
    guild = next((g for g in guilds if g["id"] == str(guild_id)), None)
    if not guild:
        raise HTTPException(404, "Guild not found")
    perms = int(guild.get("permissions", 0))
    if not (perms & 0x8 or perms & 0x20):  # ADMINISTRATOR or MANAGE_GUILD
        raise HTTPException(403, "Missing permissions")
    return session_data, guild


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@app.get("/auth/login")
async def login():
    state = os.urandom(16).hex()
    url = get_oauth_url(state)
    response = RedirectResponse(url=url)
    response.set_cookie("oauth_state", state, max_age=300, httponly=True)
    return response


@app.get("/auth/callback")
async def callback(request: Request, code: str, state: str):
    stored_state = request.cookies.get("oauth_state")
    if stored_state and stored_state != state:
        return HTMLResponse("State mismatch", status_code=400)
    token_data = await exchange_code(code)
    if not token_data:
        return HTMLResponse("Token exchange failed", status_code=400)
    session_data = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
    }
    token = make_session(session_data)
    response = RedirectResponse(url="/dashboard")
    response.set_cookie(
        "session", token, max_age=86400 * 7, httponly=True, samesite="lax"
    )
    response.delete_cookie("oauth_state")
    return response


@app.get("/auth/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("session")
    return response


@app.get("/api/me")
async def api_me(request: Request):
    try:
        session_data = await require_auth(request)
    except HTTPException:
        return JSONResponse({"authenticated": False}, status_code=401)
    user = await get_current_user(session_data["access_token"])
    guilds = await get_user_guilds(session_data["access_token"])
    manageable = [g for g in guilds if int(g.get("permissions", 0)) & (0x8 | 0x20)]
    return {
        "authenticated": True,
        "user": user,
        "guilds": manageable,
    }


# ---------------------------------------------------------------------------
# API routes - Leveling
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/settings")
async def get_guild_settings(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)

    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM guild_settings WHERE guild_id = $1", guild_id
        )
        if row:
            return dict(row)
        return {
            "guild_id": guild_id,
            "levelup_channel_id": None,
            "xp_enabled": True,
            "min_xp": 15,
            "max_xp": 25,
            "cooldown_seconds": 60,
        }


@app.post("/api/guilds/{guild_id}/settings")
async def update_guild_settings(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)
    body = await request.json()
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO guild_settings (guild_id, levelup_channel_id, xp_enabled, min_xp, max_xp, cooldown_seconds, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            ON CONFLICT (guild_id) DO UPDATE SET
                levelup_channel_id = EXCLUDED.levelup_channel_id,
                xp_enabled = EXCLUDED.xp_enabled,
                min_xp = EXCLUDED.min_xp,
                max_xp = EXCLUDED.max_xp,
                cooldown_seconds = EXCLUDED.cooldown_seconds,
                updated_at = NOW()
            """,
            guild_id,
            body.get("levelup_channel_id"),
            body.get("xp_enabled", True),
            body.get("min_xp", 15),
            body.get("max_xp", 25),
            body.get("cooldown_seconds", 60),
        )
        return {"ok": True}


@app.get("/api/guilds/{guild_id}/rewards")
async def get_role_rewards(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT level, role_id FROM role_rewards WHERE guild_id = $1 ORDER BY level",
            guild_id,
        )
        return [{"level": r["level"], "role_id": str(r["role_id"])} for r in rows]


@app.post("/api/guilds/{guild_id}/rewards")
async def add_role_reward(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)
    body = await request.json()
    level = int(body["level"])
    raw_role_id = body["role_id"]
    role_id = int(raw_role_id)
    logger.info(
        "add_role_reward: guild_id=%s level=%s raw_role_id=%s (type=%s) role_id=%s",
        guild_id,
        level,
        raw_role_id,
        type(raw_role_id).__name__,
        role_id,
    )
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO role_rewards (guild_id, level, role_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, level) DO UPDATE SET role_id = EXCLUDED.role_id
            """,
            guild_id,
            level,
            role_id,
        )
        return {"ok": True}


@app.delete("/api/guilds/{guild_id}/rewards/{level}")
async def remove_role_reward(request: Request, guild_id: int, level: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM role_rewards WHERE guild_id = $1 AND level = $2",
            guild_id,
            level,
        )
        return {"ok": result != "DELETE 0"}


@app.get("/api/guilds/{guild_id}/leaderboard")
async def get_leaderboard(
    request: Request,
    guild_id: int,
    limit: int = 10,
    offset: int = 0,
    search: str = "",
):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        if search:
            rows = await conn.fetch(
                """
                SELECT user_id, xp, level, messages
                FROM user_levels
                WHERE guild_id = $1 AND user_id::text LIKE $2
                ORDER BY xp DESC
                LIMIT $3 OFFSET $4
                """,
                guild_id,
                f"%{search}%",
                limit,
                offset,
            )
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as c FROM user_levels WHERE guild_id = $1 AND user_id::text LIKE $2",
                guild_id,
                f"%{search}%",
            )
        else:
            rows = await conn.fetch(
                """
                SELECT user_id, xp, level, messages
                FROM user_levels
                WHERE guild_id = $1
                ORDER BY xp DESC
                LIMIT $2 OFFSET $3
                """,
                guild_id,
                limit,
                offset,
            )
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as c FROM user_levels WHERE guild_id = $1",
                guild_id,
            )
        raw_users = [dict(r) for r in rows]
        users = await enrich_leaderboard(guild_id, raw_users)
        return {
            "users": users,
            "total": count_row["c"] if count_row else 0,
        }


@app.get("/api/guilds/{guild_id}/roles")
async def list_guild_roles(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)
    roles = await get_assignable_roles(guild_id)
    return roles


@app.get("/api/guilds/{guild_id}/users/{user_id}")
async def get_user_profile(request: Request, guild_id: int, user_id: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_levels WHERE user_id = $1 AND guild_id = $2",
            user_id,
            guild_id,
        )
        if not row:
            raise HTTPException(404, "User not found")
        rank_row = await conn.fetchrow(
            """
            SELECT COUNT(*) + 1 as rank
            FROM user_levels
            WHERE guild_id = $1 AND xp > (SELECT COALESCE(xp, 0) FROM user_levels WHERE user_id = $2 AND guild_id = $1)
            """,
            guild_id,
            user_id,
        )
        data = dict(row)
        data["rank"] = rank_row["rank"] if rank_row else 0
        members = await get_guild_members(guild_id)
        member = members.get(str(user_id)) or default_user(user_id)
        data["username"] = member["username"]
        data["display_name"] = member["display_name"]
        data["avatar_url"] = member["avatar_url"]
        data["discriminator"] = member["discriminator"]
        return data


@app.get("/api/guilds/{guild_id}/analytics")
async def get_analytics(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        total_users = await conn.fetchval(
            "SELECT COUNT(*) FROM user_levels WHERE guild_id = $1", guild_id
        )
        total_xp = await conn.fetchval(
            "SELECT COALESCE(SUM(xp), 0) FROM user_levels WHERE guild_id = $1",
            guild_id,
        )
        total_messages = await conn.fetchval(
            "SELECT COALESCE(SUM(messages), 0) FROM user_levels WHERE guild_id = $1",
            guild_id,
        )
        level_dist = await conn.fetch(
            """
            SELECT level, COUNT(*) as count
            FROM user_levels
            WHERE guild_id = $1
            GROUP BY level
            ORDER BY level
            """,
            guild_id,
        )
        top_users = await conn.fetch(
            """
            SELECT user_id, xp, level, messages
            FROM user_levels
            WHERE guild_id = $1
            ORDER BY xp DESC
            LIMIT 5
            """,
            guild_id,
        )
        raw_users = [dict(r) for r in top_users]
        enriched_users = await enrich_leaderboard(guild_id, raw_users)
        return {
            "total_users": total_users or 0,
            "total_xp": total_xp or 0,
            "total_messages": total_messages or 0,
            "level_distribution": [dict(r) for r in level_dist],
            "top_users": enriched_users,
        }


@app.get("/api/bot/stats")
async def bot_stats():
    db = await get_db()
    async with db.acquire() as conn:
        guild_count = await conn.fetchval(
            "SELECT COUNT(DISTINCT guild_id) FROM guild_settings"
        )
        user_count = await conn.fetchval("SELECT COUNT(*) FROM user_levels")
        total_xp = await conn.fetchval("SELECT COALESCE(SUM(xp), 0) FROM user_levels")
        total_messages = await conn.fetchval(
            "SELECT COALESCE(SUM(messages), 0) FROM user_levels"
        )
        return {
            "guild_count": guild_count or 0,
            "user_count": user_count or 0,
            "total_xp": total_xp or 0,
            "total_messages": total_messages or 0,
        }


# ---------------------------------------------------------------------------
# Enhanced API endpoints
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/stats/overview")
async def guild_stats_overview(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        total_users = await conn.fetchval(
            "SELECT COUNT(*) FROM user_levels WHERE guild_id = $1", guild_id
        )
        total_xp = await conn.fetchval(
            "SELECT COALESCE(SUM(xp), 0) FROM user_levels WHERE guild_id = $1",
            guild_id,
        )
        total_messages = await conn.fetchval(
            "SELECT COALESCE(SUM(messages), 0) FROM user_levels WHERE guild_id = $1",
            guild_id,
        )
        top_users_raw = await conn.fetch(
            "SELECT user_id, xp, level, messages FROM user_levels WHERE guild_id = $1 ORDER BY xp DESC LIMIT 5",
            guild_id,
        )
        top_users = await enrich_leaderboard(guild_id, [dict(r) for r in top_users_raw])
        members = await get_guild_members(guild_id)
        member_count = len(members)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        xp_earned_today = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_log WHERE guild_id = $1 AND created_at >= $2 AND source = 'message'",
            guild_id,
            today,
        )
        messages_today = await conn.fetchval(
            "SELECT COUNT(*) FROM xp_log WHERE guild_id = $1 AND created_at >= $2 AND source = 'message'",
            guild_id,
            today,
        )
        active_members_today = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM xp_log WHERE guild_id = $1 AND created_at >= $2 AND source = 'message'",
            guild_id,
            today,
        )
        level_range = await conn.fetchrow(
            "SELECT MIN(level) as min_level, MAX(level) as max_level FROM user_levels WHERE guild_id = $1",
            guild_id,
        )
        return {
            "total_users": total_users or 0,
            "total_xp": total_xp or 0,
            "total_messages": total_messages or 0,
            "member_count": member_count,
            "top_users": top_users,
            "xp_earned_today": xp_earned_today or 0,
            "messages_today": messages_today or 0,
            "active_members_today": active_members_today or 0,
            "level_range": {
                "min": level_range["min_level"] if level_range else 0,
                "max": level_range["max_level"] if level_range else 0,
            },
        }


@app.get("/api/guilds/{guild_id}/users/{user_id}/history")
async def user_xp_history(
    request: Request, guild_id: int, user_id: int, limit: int = 50, offset: int = 0
):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, user_id, guild_id, amount, source, reason, created_at FROM xp_log WHERE guild_id = $1 AND user_id = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4",
            guild_id,
            user_id,
            limit,
            offset,
        )
        return [dict(r) for r in rows]


@app.get("/api/guilds/{guild_id}/analytics/extended")
async def extended_analytics(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        total_users = await conn.fetchval(
            "SELECT COUNT(*) FROM user_levels WHERE guild_id = $1", guild_id
        )
        total_xp = await conn.fetchval(
            "SELECT COALESCE(SUM(xp), 0) FROM user_levels WHERE guild_id = $1",
            guild_id,
        )
        total_messages = await conn.fetchval(
            "SELECT COALESCE(SUM(messages), 0) FROM user_levels WHERE guild_id = $1",
            guild_id,
        )
        level_dist = await conn.fetch(
            "SELECT level, COUNT(*) as count FROM user_levels WHERE guild_id = $1 GROUP BY level ORDER BY level",
            guild_id,
        )
        top_users_raw = await conn.fetch(
            "SELECT user_id, xp, level, messages FROM user_levels WHERE guild_id = $1 ORDER BY xp DESC LIMIT 5",
            guild_id,
        )
        enriched_users = await enrich_leaderboard(
            guild_id, [dict(r) for r in top_users_raw]
        )
        xp_by_day = await conn.fetch(
            """
            SELECT DATE(created_at) as date, COALESCE(SUM(amount), 0) as xp
            FROM xp_log
            WHERE guild_id = $1 AND created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date
            """,
            guild_id,
        )
        messages_by_day = await conn.fetch(
            """
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM xp_log
            WHERE guild_id = $1 AND source = 'message' AND created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date
            """,
            guild_id,
        )
        active_users_by_day = await conn.fetch(
            """
            SELECT DATE(created_at) as date, COUNT(DISTINCT user_id) as count
            FROM xp_log
            WHERE guild_id = $1 AND created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            ORDER BY date
            """,
            guild_id,
        )
        hourly_activity = await conn.fetch(
            """
            SELECT EXTRACT(HOUR FROM created_at)::int as hour, COUNT(*) as count
            FROM xp_log
            WHERE guild_id = $1 AND created_at >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hour
            """,
            guild_id,
        )
        return {
            "total_users": total_users or 0,
            "total_xp": total_xp or 0,
            "total_messages": total_messages or 0,
            "level_distribution": [dict(r) for r in level_dist],
            "top_users": enriched_users,
            "xp_by_day": [{"date": str(r["date"]), "xp": r["xp"]} for r in xp_by_day],
            "messages_by_day": [
                {"date": str(r["date"]), "count": r["count"]} for r in messages_by_day
            ],
            "active_users_by_day": [
                {"date": str(r["date"]), "count": r["count"]}
                for r in active_users_by_day
            ],
            "hourly_activity": [
                {"hour": r["hour"], "count": r["count"]} for r in hourly_activity
            ],
            "top_channels": [],
        }


@app.delete("/api/guilds/{guild_id}/users/{user_id}/rewards/{level}")
async def remove_user_reward(request: Request, guild_id: int, user_id: int, level: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM role_rewards WHERE guild_id = $1 AND level = $2",
            guild_id,
            level,
        )
        return {"ok": result != "DELETE 0"}


# ---------------------------------------------------------------------------
# Admin API - Level management
# ---------------------------------------------------------------------------


@app.post("/api/guilds/{guild_id}/users/{user_id}/setlevel")
async def api_set_level(request: Request, guild_id: int, user_id: int):
    _, _ = await require_guild_access(request, guild_id)
    body = await request.json()
    level = int(body["level"])
    db = await get_db()
    async with db.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT * FROM user_levels WHERE user_id = $1 AND guild_id = $2",
            user_id,
            guild_id,
        )
        messages = user_row["messages"] if user_row else 0
        xp = _calc_xp_for_level(level)
        await conn.execute(
            """
            INSERT INTO user_levels (user_id, guild_id, xp, level, messages, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (user_id, guild_id) DO UPDATE SET
                xp = EXCLUDED.xp, level = EXCLUDED.level, updated_at = NOW()
            """,
            user_id,
            guild_id,
            xp,
            level,
            messages,
        )
        return {"ok": True, "level": level, "xp": xp}


@app.post("/api/guilds/{guild_id}/users/{user_id}/addxp")
async def api_add_xp(request: Request, guild_id: int, user_id: int):
    _, _ = await require_guild_access(request, guild_id)
    body = await request.json()
    amount = int(body["amount"])
    db = await get_db()
    async with db.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT * FROM user_levels WHERE user_id = $1 AND guild_id = $2",
            user_id,
            guild_id,
        )
        if user_row:
            new_xp = user_row["xp"] + amount
            messages = user_row["messages"]
        else:
            new_xp = max(0, amount)
            messages = 0
        new_level = _calc_level(new_xp)
        await conn.execute(
            """
            INSERT INTO user_levels (user_id, guild_id, xp, level, messages, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (user_id, guild_id) DO UPDATE SET
                xp = EXCLUDED.xp, level = EXCLUDED.level, updated_at = NOW()
            """,
            user_id,
            guild_id,
            new_xp,
            new_level,
            messages,
        )
        return {"ok": True, "xp": new_xp, "level": new_level}


@app.delete("/api/guilds/{guild_id}/users/{user_id}")
async def api_reset_user(request: Request, guild_id: int, user_id: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_levels WHERE user_id = $1 AND guild_id = $2",
            user_id,
            guild_id,
        )
        return {"ok": True}


@app.delete("/api/guilds/{guild_id}/levels")
async def api_reset_all(request: Request, guild_id: int):
    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute("DELETE FROM user_levels WHERE guild_id = $1", guild_id)
        return {"ok": True}


# ---------------------------------------------------------------------------
# Level formula helpers (mirrors bot's logic)
# ---------------------------------------------------------------------------


def _calc_level(xp: int) -> int:
    level = 0
    needed = 0
    while needed <= xp:
        level += 1
        needed += 5 * (level**2) + (50 * level) + 100
    return max(0, level - 1)


def _calc_xp_for_level(level: int) -> int:
    total = 0
    for lvl in range(1, level + 1):
        total += 5 * (lvl**2) + (50 * lvl) + 100
    return total


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get("session")
    user = None
    if token:
        data = read_session(token)
        if data:
            user = await get_current_user(data.get("access_token", ""))
    return render("login.html", request=request, user=user)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    try:
        await require_auth(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login")
    return render("dashboard.html", request=request, page="dashboard")


async def _render_guild_page(
    request: Request,
    guild_id: int,
    template: str,
    page: str,
    **extra: Any,
):
    """Render a guild-scoped dashboard page with shared auth/context extraction."""
    try:
        _, guild = await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    return render(
        template,
        request=request,
        page=page,
        guild_id=gid,
        guild_name=guild.get("name", ""),
        guild_icon=guild.get("icon", ""),
        **extra,
    )


@app.get("/guilds/{guild_id}", response_class=HTMLResponse)
async def guild_overview(request: Request, guild_id: int):
    return await _render_guild_page(request, guild_id, "dashboard.html", "overview")


@app.get("/guilds/{guild_id}/leveling", response_class=HTMLResponse)
async def guild_leveling(request: Request, guild_id: int):
    return await _render_guild_page(request, guild_id, "leveling.html", "leveling")


@app.get("/guilds/{guild_id}/rewards", response_class=HTMLResponse)
async def guild_rewards(request: Request, guild_id: int):
    return await _render_guild_page(request, guild_id, "rewards.html", "rewards")


@app.get("/guilds/{guild_id}/leaderboard", response_class=HTMLResponse)
async def guild_leaderboard(request: Request, guild_id: int):
    return await _render_guild_page(
        request, guild_id, "leaderboard.html", "leaderboard"
    )


@app.get("/guilds/{guild_id}/users/{user_id}", response_class=HTMLResponse)
async def guild_user(request: Request, guild_id: int, user_id: int):
    return await _render_guild_page(
        request, guild_id, "users.html", "users", user_id=user_id
    )


@app.get("/guilds/{guild_id}/analytics", response_class=HTMLResponse)
async def guild_analytics(request: Request, guild_id: int):
    return await _render_guild_page(request, guild_id, "analytics.html", "analytics")


@app.get("/guilds/{guild_id}/settings", response_class=HTMLResponse)
async def guild_settings_page(request: Request, guild_id: int):
    return await _render_guild_page(request, guild_id, "settings.html", "settings")


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Ensure guild_settings table has all columns
    try:
        db = await get_db()
        async with db.acquire() as conn:
            for col_sql in [
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS xp_enabled BOOLEAN DEFAULT TRUE",
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS min_xp INTEGER DEFAULT 15",
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS max_xp INTEGER DEFAULT 25",
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS cooldown_seconds INTEGER DEFAULT 60",
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            ]:
                try:
                    await conn.execute(col_sql)
                except Exception:
                    logger.debug("Migration already applied: %s", col_sql.split()[-1])
    except Exception:
        logger.warning("Could not run guild_settings migrations (DB not ready yet)")


@app.on_event("shutdown")
async def shutdown():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
