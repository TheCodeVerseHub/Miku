"""
FastAPI dashboard backend for Miku Discord bot.

Security features:
- CSRF protection on state-changing requests
- Rate limiting on auth and API endpoints
- Security headers (CSP, HSTS, XSS, etc.)
- Input validation and sanitization
- Secure session cookies (HTTP-only, SameSite=Strict)
- Session rotation on login

Improvements:
- Shared formula module eliminates duplication with bot
- Health check endpoints for monitoring
- Pagination limits enforced
- Better error handling
- Graceful connection pooling
"""

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

# Add bot src/ and shared/ to path so we can reuse modules
BOT_SRC = str((Path(__file__).parent.parent.parent / "src").resolve())
SHARED_DIR = str((Path(__file__).parent.parent.parent).resolve())
for p in [BOT_SRC, SHARED_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from cachetools import TTLCache

from .config import config
from .discord_api import enrich_leaderboard, get_assignable_roles, get_guild_members, default_user
from .auth import (
    exchange_code,
    get_current_user as _get_current_user,
    get_user_guilds as _get_user_guilds,
    get_oauth_url,
)
from .security import setup_security, sanitize_search_query, validate_guild_id, validate_level, validate_user_id, validate_xp_amount
from .health import router as health_router
from .database import get_db, close_db

# Import shared formula (single source of truth)
from shared.formula import calculate_level, calculate_xp_for_level

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

app = FastAPI(
    title="Miku Dashboard",
    version="0.2.0",
    docs_url=None,  # Disable Swagger in production
    redoc_url=None,
)

# Setup security middleware (CSRF, rate limiting, headers)
setup_security(app, config.session_secret)

# Register health check routes
app.include_router(health_router)

# Templates (using raw Jinja2)
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

# Database pool is managed by .database module (imported above)


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
    """Initiate OAuth2 login with Discord."""
    state = os.urandom(16).hex()
    url = get_oauth_url(state)
    response = RedirectResponse(url=url)
    response.set_cookie("oauth_state", state, max_age=300, httponly=True, secure=True, samesite="lax")
    return response


@app.get("/auth/callback")
async def callback(request: Request, code: str, state: str):
    """Handle OAuth2 callback from Discord."""
    # Validate state to prevent CSRF on OAuth
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return HTMLResponse(
            "<h1>Authentication failed</h1><p>State mismatch. Please try logging in again.</p>",
            status_code=400,
        )

    token_data = await exchange_code(code)
    if not token_data:
        return HTMLResponse(
            "<h1>Authentication failed</h1><p>Token exchange with Discord failed. Please try again.</p>",
            status_code=400,
        )

    # Session rotation: generate new session
    session_data = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
    }
    token = make_session(session_data)

    response = RedirectResponse(url="/dashboard")
    response.set_cookie(
        "session",
        token,
        max_age=86400 * 7,
        httponly=True,
        secure=True,
        samesite="strict",
    )
    response.delete_cookie("oauth_state")
    return response


@app.get("/auth/logout")
async def logout():
    """Clear session and redirect to home."""
    response = RedirectResponse(url="/")
    response.delete_cookie("session")
    response.delete_cookie("oauth_state")
    return response


@app.get("/api/me")
async def api_me(request: Request):
    """Get current user info and manageable guilds."""
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
    """Get guild XP settings."""
    if not validate_guild_id(guild_id):
        raise HTTPException(400, "Invalid guild ID")
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
    """Update guild XP settings."""
    if not validate_guild_id(guild_id):
        raise HTTPException(400, "Invalid guild ID")
    _, _ = await require_guild_access(request, guild_id)

    body = await request.json()
    # Validate input
    min_xp = max(1, min(100, int(body.get("min_xp", 15))))
    max_xp = max(min_xp, min(100, int(body.get("max_xp", 25))))
    cooldown = max(1, min(3600, int(body.get("cooldown_seconds", 60))))

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
            bool(body.get("xp_enabled", True)),
            min_xp,
            max_xp,
            cooldown,
        )
        return {"ok": True}


@app.get("/api/guilds/{guild_id}/rewards")
async def get_role_rewards(request: Request, guild_id: int):
    """Get all role rewards for a guild."""
    if not validate_guild_id(guild_id):
        raise HTTPException(400, "Invalid guild ID")
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
    """Add or update a role reward."""
    if not validate_guild_id(guild_id):
        raise HTTPException(400, "Invalid guild ID")
    _, _ = await require_guild_access(request, guild_id)

    body = await request.json()
    level = int(body["level"])
    if not validate_level(level):
        raise HTTPException(400, "Invalid level (must be 0-100000)")

    role_id = int(body["role_id"])
    if not validate_user_id(role_id):
        raise HTTPException(400, "Invalid role ID")

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
    """Remove a role reward."""
    if not validate_guild_id(guild_id) or not validate_level(level):
        raise HTTPException(400, "Invalid parameters")
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
    """Get paginated leaderboard with optional search."""
    if not validate_guild_id(guild_id):
        raise HTTPException(400, "Invalid guild ID")

    # Enforce pagination limits
    limit = max(1, min(100, limit))
    offset = max(0, offset)

    _, _ = await require_guild_access(request, guild_id)
    db = await get_db()

    # Sanitize search input to prevent injection
    search_clean = sanitize_search_query(search) if search else ""

    async with db.acquire() as conn:
        if search_clean:
            # Use safe parameterized query with sanitized input
            search_param = f"%{search_clean}%"
            rows = await conn.fetch(
                """
                SELECT user_id, xp, level, messages
                FROM user_levels
                WHERE guild_id = $1 AND user_id::text LIKE $2
                ORDER BY xp DESC
                LIMIT $3 OFFSET $4
                """,
                guild_id,
                search_param,
                limit,
                offset,
            )
            count_row = await conn.fetchrow(
                "SELECT COUNT(*) as c FROM user_levels WHERE guild_id = $1 AND user_id::text LIKE $2",
                guild_id,
                search_param,
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
    """Get all assignable roles for a guild."""
    if not validate_guild_id(guild_id):
        raise HTTPException(400, "Invalid guild ID")
    _, _ = await require_guild_access(request, guild_id)
    roles = await get_assignable_roles(guild_id)
    return roles


@app.get("/api/guilds/{guild_id}/users/{user_id}")
async def get_user_profile(request: Request, guild_id: int, user_id: int):
    """Get a user's detailed leveling profile."""
    if not validate_guild_id(guild_id) or not validate_user_id(user_id):
        raise HTTPException(400, "Invalid IDs")
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
    """Get server analytics and statistics."""
    if not validate_guild_id(guild_id):
        raise HTTPException(400, "Invalid guild ID")
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
    """Get global bot statistics."""
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
# Admin API - Level management
# ---------------------------------------------------------------------------


@app.post("/api/guilds/{guild_id}/users/{user_id}/setlevel")
async def api_set_level(request: Request, guild_id: int, user_id: int):
    """Set a user's level (admin only)."""
    if not validate_guild_id(guild_id) or not validate_user_id(user_id):
        raise HTTPException(400, "Invalid IDs")
    _, _ = await require_guild_access(request, guild_id)

    body = await request.json()
    level = int(body["level"])
    if not validate_level(level):
        raise HTTPException(400, "Invalid level (must be 0-100000)")

    db = await get_db()
    async with db.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT * FROM user_levels WHERE user_id = $1 AND guild_id = $2",
            user_id,
            guild_id,
        )
        messages = user_row["messages"] if user_row else 0
        # Use shared formula module
        xp = calculate_xp_for_level(level)
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
    """Add XP to a user (admin only)."""
    if not validate_guild_id(guild_id) or not validate_user_id(user_id):
        raise HTTPException(400, "Invalid IDs")
    _, _ = await require_guild_access(request, guild_id)

    body = await request.json()
    amount = int(body["amount"])
    if not validate_xp_amount(amount):
        raise HTTPException(400, "Invalid XP amount (must be between -10M and 10M)")

    db = await get_db()
    async with db.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT * FROM user_levels WHERE user_id = $1 AND guild_id = $2",
            user_id,
            guild_id,
        )
        if user_row:
            new_xp = max(0, user_row["xp"] + amount)
            messages = user_row["messages"]
        else:
            new_xp = max(0, amount)
            messages = 0
        # Use shared formula module
        new_level = calculate_level(new_xp)
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
    """Reset a user's leveling data (admin only)."""
    if not validate_guild_id(guild_id) or not validate_user_id(user_id):
        raise HTTPException(400, "Invalid IDs")
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
    """Reset ALL leveling data for a guild (admin only, dangerous)."""
    if not validate_guild_id(guild_id):
        raise HTTPException(400, "Invalid guild ID")
    _, _ = await require_guild_access(request, guild_id)

    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_levels WHERE guild_id = $1", guild_id
        )
        return {"ok": True}


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page."""
    token = request.cookies.get("session")
    user = None
    if token:
        data = read_session(token)
        if data:
            user = await get_current_user(data.get("access_token", ""))
    return render("login.html", request=request, user=user)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Dashboard home with server list."""
    try:
        await require_auth(request)
    except HTTPException:
        return RedirectResponse(url="/auth/login")
    return render("dashboard.html", request=request, page="dashboard")


@app.get("/guilds/{guild_id}", response_class=HTMLResponse)
async def guild_overview(request: Request, guild_id: int):
    """Guild overview page."""
    try:
        _, guild = await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    guild_name = guild.get("name", "")
    guild_icon = guild.get("icon", "")
    return render(
        "dashboard.html", request=request, page="overview",
        guild_id=gid, guild_name=guild_name, guild_icon=guild_icon,
    )


@app.get("/guilds/{guild_id}/leveling", response_class=HTMLResponse)
async def guild_leveling(request: Request, guild_id: int):
    """Leveling configuration page."""
    try:
        _, guild = await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    guild_name = guild.get("name", "")
    guild_icon = guild.get("icon", "")
    return render(
        "leveling.html", request=request, page="leveling",
        guild_id=gid, guild_name=guild_name, guild_icon=guild_icon,
    )


@app.get("/guilds/{guild_id}/rewards", response_class=HTMLResponse)
async def guild_rewards(request: Request, guild_id: int):
    """Role rewards management page."""
    try:
        _, guild = await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    guild_name = guild.get("name", "")
    guild_icon = guild.get("icon", "")
    return render(
        "rewards.html", request=request, page="rewards",
        guild_id=gid, guild_name=guild_name, guild_icon=guild_icon,
    )


@app.get("/guilds/{guild_id}/leaderboard", response_class=HTMLResponse)
async def guild_leaderboard(request: Request, guild_id: int):
    """Leaderboard page."""
    try:
        _, guild = await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    guild_name = guild.get("name", "")
    guild_icon = guild.get("icon", "")
    return render(
        "leaderboard.html", request=request, page="leaderboard",
        guild_id=gid, guild_name=guild_name, guild_icon=guild_icon,
    )


@app.get("/guilds/{guild_id}/users/{user_id}", response_class=HTMLResponse)
async def guild_user(request: Request, guild_id: int, user_id: int):
    """User profile page."""
    try:
        _, guild = await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    guild_name = guild.get("name", "")
    guild_icon = guild.get("icon", "")
    return render(
        "users.html", request=request, page="users",
        guild_id=gid, user_id=user_id,
        guild_name=guild_name, guild_icon=guild_icon,
    )


@app.get("/guilds/{guild_id}/analytics", response_class=HTMLResponse)
async def guild_analytics(request: Request, guild_id: int):
    """Analytics dashboard page."""
    try:
        _, guild = await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    guild_name = guild.get("name", "")
    guild_icon = guild.get("icon", "")
    return render(
        "analytics.html", request=request, page="analytics",
        guild_id=gid, guild_name=guild_name, guild_icon=guild_icon,
    )


@app.get("/guilds/{guild_id}/settings", response_class=HTMLResponse)
async def guild_settings_page(request: Request, guild_id: int):
    """Server settings page."""
    try:
        _, guild = await require_guild_access(request, guild_id)
    except HTTPException:
        return RedirectResponse(url="/dashboard")
    gid = str(guild_id)
    guild_name = guild.get("name", "")
    guild_icon = guild.get("icon", "")
    return render(
        "settings.html", request=request, page="settings",
        guild_id=gid, guild_name=guild_name, guild_icon=guild_icon,
    )


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup():
    """Initialize logging and ensure DB schema is up to date."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Ensure guild_settings table has all columns
    try:
        db = await get_db()
        async with db.acquire() as conn:
            migrations = [
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS xp_enabled BOOLEAN DEFAULT TRUE",
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS min_xp INTEGER DEFAULT 15",
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS max_xp INTEGER DEFAULT 25",
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS cooldown_seconds INTEGER DEFAULT 60",
                "ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            ]
            for sql in migrations:
                try:
                    await conn.execute(sql)
                except Exception:
                    pass
    except Exception:
        logger.warning("Could not run guild_settings migrations (DB not ready yet)")


@app.on_event("shutdown")
async def shutdown():
    """Clean up database connections on shutdown."""
    await close_db()
