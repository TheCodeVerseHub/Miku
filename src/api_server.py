from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
import os
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Initialize FastAPI
app = FastAPI(title="Miku Bot API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
_pool = None

# Models
class UserLevel(BaseModel):
    user_id: int
    xp: int
    level: int
    messages: int

class ServerStats(BaseModel):
    totalMembers: int
    totalXP: int
    activeUsers: int
    averageLevel: float
    topUser: Optional[dict]

class RoleReward(BaseModel):
    level: int
    role_id: int

class GuildSettings(BaseModel):
    levelup_channel_id: Optional[int]
    roleRewards: List[RoleReward]

# Helper function to get database pool
async def get_pool():
    """Get or create database connection pool"""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool

@app.on_event("startup")
async def startup():
    """Initialize database connection on startup"""
    await get_pool()

@app.on_event("shutdown")
async def shutdown():
    """Close database connection on shutdown"""
    global _pool
    if _pool:
        await _pool.close()

# Health check
@app.get("/")
async def root():
    return {"status": "ok", "message": "Miku Bot API is running"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}

# Get server stats
@app.get("/api/server/{guild_id}/stats")
async def get_server_stats(guild_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get aggregate stats
        stats = await conn.fetchrow(
            """SELECT 
                COUNT(*) as activeUsers,
                COALESCE(SUM(xp), 0) as totalXP,
                COALESCE(AVG(level), 0) as averageLevel
            FROM user_levels 
            WHERE guild_id = $1""",
            guild_id
        )
        
        # Get top user
        top_user = await conn.fetchrow(
            """SELECT user_id, level, xp
            FROM user_levels 
            WHERE guild_id = $1 
            ORDER BY xp DESC 
            LIMIT 1""",
            guild_id
        )
        
        return {
            "totalMembers": stats['activeusers'] or 0,
            "totalXP": int(stats['totalxp']) or 0,
            "activeUsers": stats['activeusers'] or 0,
            "averageLevel": round(float(stats['averagelevel']) or 0, 1),
            "topUser": {
                "userId": str(top_user['user_id']),
                "level": top_user['level']
            } if top_user else None
        }

# Get leaderboard
@app.get("/api/server/{guild_id}/leaderboard")
async def get_leaderboard(guild_id: int, page: int = 1, limit: int = 50):
    pool = await get_pool()
    async with pool.acquire() as conn:
        offset = (page - 1) * limit
        
        # Get total count
        total = await conn.fetchval(
            'SELECT COUNT(*) FROM user_levels WHERE guild_id = $1',
            guild_id
        )
        
        # Get leaderboard page
        rows = await conn.fetch(
            """SELECT user_id, xp, level, messages
            FROM user_levels 
            WHERE guild_id = $1
            ORDER BY xp DESC
            LIMIT $2 OFFSET $3""",
            guild_id, limit, offset
        )
        
        data = []
        for idx, row in enumerate(rows, start=offset + 1):
            data.append({
                "rank": idx,
                "userId": str(row['user_id']),
                "xp": row['xp'],
                "level": row['level'],
                "messages": row['messages']
            })
        
        return {
            "data": data,
            "page": page,
            "totalPages": (total + limit - 1) // limit,
            "total": total
        }

# Get guild settings
@app.get("/api/server/{guild_id}/settings")
async def get_guild_settings(guild_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Get settings
        settings = await conn.fetchrow(
            'SELECT levelup_channel_id FROM guild_settings WHERE guild_id = $1',
            guild_id
        )
        
        # Get role rewards
        role_rewards = await conn.fetch(
            'SELECT level, role_id FROM role_rewards WHERE guild_id = $1 ORDER BY level',
            guild_id
        )
        
        return {
            "levelupChannelId": str(settings['levelup_channel_id']) if settings and settings['levelup_channel_id'] else None,
            "roleRewards": [
                {"level": rr['level'], "roleId": str(rr['role_id'])}
                for rr in role_rewards
            ]
        }

# Update guild settings
@app.post("/api/server/{guild_id}/settings")
async def update_guild_settings(guild_id: int, settings: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Update levelup channel
        if "levelupChannelId" in settings:
            channel_id = int(settings["levelupChannelId"]) if settings["levelupChannelId"] else None
            
            if channel_id is None:
                await conn.execute(
                    'DELETE FROM guild_settings WHERE guild_id = $1',
                    guild_id
                )
            else:
                await conn.execute(
                    """INSERT INTO guild_settings (guild_id, levelup_channel_id, updated_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        levelup_channel_id = EXCLUDED.levelup_channel_id,
                        updated_at = EXCLUDED.updated_at""",
                    guild_id, channel_id, __import__('time').time()
                )
        
        # Update role rewards
        if "roleRewards" in settings:
            # Clear existing
            await conn.execute('DELETE FROM role_rewards WHERE guild_id = $1', guild_id)
            
            # Add new ones
            for reward in settings["roleRewards"]:
                await conn.execute(
                    'INSERT INTO role_rewards (guild_id, level, role_id) VALUES ($1, $2, $3)',
                    guild_id, reward["level"], int(reward["roleId"])
                )
        
        return {"success": True}

# Check if guild has bot
@app.get("/api/guild/{guild_id}/has-bot")
async def check_guild_has_bot(guild_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            'SELECT COUNT(*) FROM user_levels WHERE guild_id = $1',
            guild_id
        )
        
        return {"hasMiku": count > 0}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
