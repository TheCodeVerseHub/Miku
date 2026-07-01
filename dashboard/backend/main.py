"""FastAPI dashboard backend for Miku Discord bot."""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
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
_pool: Optional[asyncpg.Pool] = None


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


def read_session(token: str) -> Optional[dict]:
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


async def require_guild_access(request: Request, guild_id: int) -> dict:
    session_data = await require_auth(request)
    guilds = await get_user_guilds(session_data["access_token"])
    guild = next((g for g in guilds if g["id"] == str(guild_id)), None)
    if not guild:
        raise HTTPException(404, "Guild not found")
    perms = int(guild.get("permissions", 0))
    if not (perms & 0x8 or perms & 0x20):  # ADMINISTRATOR or MANAGE_GUILD
        raise HTTPException(403, "Missing permissions")
    return session_data


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
    manageable = [
        g
        for g in guilds
        if int(g.get("permissions", 0)) & (0x8 | 0x20)
    ]
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
    await require_guild_access(request, guild_id)
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
    await require_guild_access(request, guild_id)
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
    await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT level, role_id FROM role_rewards WHERE guild_id = $1 ORDER BY level",
            guild_id,
        )
        return [dict(r) for r in rows]


@app.post("/api/guilds/{guild_id}/rewards")
async def add_role_reward(request: Request, guild_id: int):
    await require_guild_access(request, guild_id)
    body = await request.json()
    level = int(body["level"])
    role_id = int(body["role_id"])
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
    await require_guild_access(request, guild_id)
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
    await require_guild_access(request, guild_id)
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
        return {
            "users": [dict(r) for r in rows],
            "total": count_row["c"] if count_row else 0,
        }


@app.get("/api/guilds/{guild_id}/users/{user_id}")
async def get_user_profile(request: Request, guild_id: int, user_id: int):
    await require_guild_access(request, guild_id)
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
        return data


@app.get("/api/guilds/{guild_id}/analytics")
async def get_analytics(request: Request, guild_id: int):
    await require_guild_access(request, guild_id)
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
        return {
            "total_users": total_users or 0,
            "total_xp": total_xp or 0,
            "total_messages": total_messages or 0,
            "level_distribution": [dict(r) for r in level_dist],
            "top_users": [dict(r) for r in top_users],
        }


@app.get("/api/bot/stats")
async def bot_stats():
    db = await get_db()
    async with db.acquire() as conn:
        guild_count = await conn.fetchval(
            "SELECT COUNT(DISTINCT guild_id) FROM guild_settings"
        )
        user_count = await conn.fetchval("SELECT COUNT(*) FROM user_levels")
        total_xp = await conn.fetchval(
            "SELECT COALESCE(SUM(xp), 0) FROM user_levels"
        )
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
# Admin API - Level management
# ---------------------------------------------------------------------------


@app.post("/api/guilds/{guild_id}/users/{user_id}/setlevel")
async def api_set_level(request: Request, guild_id: int, user_id: int):
    await require_guild_access(request, guild_id)
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
    await require_guild_access(request, guild_id)
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
    await require_guild_access(request, guild_id)
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
    await require_guild_access(request, guild_id)
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_levels WHERE guild_id = $1", guild_id
        )
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


@app.get("/guilds/{guild_id}", response_class=HTMLResponse)
async def guild_overview(request: Request, guild_id: int):
    try:
        await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    return render("dashboard.html", request=request, page="overview", guild_id=gid)


@app.get("/guilds/{guild_id}/leveling", response_class=HTMLResponse)
async def guild_leveling(request: Request, guild_id: int):
    try:
        await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    return render("leveling.html", request=request, page="leveling", guild_id=gid)


@app.get("/guilds/{guild_id}/rewards", response_class=HTMLResponse)
async def guild_rewards(request: Request, guild_id: int):
    try:
        await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    return render("rewards.html", request=request, page="rewards", guild_id=gid)


@app.get("/guilds/{guild_id}/leaderboard", response_class=HTMLResponse)
async def guild_leaderboard(request: Request, guild_id: int):
    try:
        await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    return render("leaderboard.html", request=request, page="leaderboard", guild_id=gid)


@app.get("/guilds/{guild_id}/users/{user_id}", response_class=HTMLResponse)
async def guild_user(request: Request, guild_id: int, user_id: int):
    try:
        await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    return render("users.html", request=request, page="users", guild_id=gid, user_id=user_id)


@app.get("/guilds/{guild_id}/analytics", response_class=HTMLResponse)
async def guild_analytics(request: Request, guild_id: int):
    try:
        await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    return render("analytics.html", request=request, page="analytics", guild_id=gid)


@app.get("/guilds/{guild_id}/settings", response_class=HTMLResponse)
async def guild_settings_page(request: Request, guild_id: int):
    try:
        await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    return render("settings.html", request=request, page="settings", guild_id=gid)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@app.on_event("shutdown")
async def shutdown():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
