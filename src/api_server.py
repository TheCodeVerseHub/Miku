from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import aiosqlite
from pathlib import Path
import os
from typing import List, Optional
from pydantic import BaseModel

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

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "leveling.db"

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

# Helper function to get database connection
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

# Health check
@app.get("/")
async def root():
    return {"status": "ok", "message": "Miku Bot API is running"}

# Get server stats
@app.get("/api/server/{guild_id}/stats")
async def get_server_stats(guild_id: int):
    db = await get_db()
    try:
        # Get aggregate stats
        async with db.execute(
            """SELECT 
                COUNT(*) as activeUsers,
                COALESCE(SUM(xp), 0) as totalXP,
                COALESCE(AVG(level), 0) as averageLevel
            FROM user_levels 
            WHERE guild_id = ?""",
            (guild_id,)
        ) as cursor:
            stats = await cursor.fetchone()
        
        # Get top user
        async with db.execute(
            """SELECT user_id, level, xp
            FROM user_levels 
            WHERE guild_id = ? 
            ORDER BY xp DESC 
            LIMIT 1""",
            (guild_id,)
        ) as cursor:
            top_user = await cursor.fetchone()
        
        return {
            "totalMembers": stats[0] or 0,
            "totalXP": stats[1] or 0,
            "activeUsers": stats[0] or 0,
            "averageLevel": round(stats[2] or 0, 1),
            "topUser": {
                "userId": str(top_user[0]),
                "level": top_user[1]
            } if top_user else None
        }
    finally:
        await db.close()

# Get leaderboard
@app.get("/api/server/{guild_id}/leaderboard")
async def get_leaderboard(guild_id: int, page: int = 1, limit: int = 50):
    db = await get_db()
    try:
        offset = (page - 1) * limit
        
        # Get total count
        async with db.execute(
            'SELECT COUNT(*) FROM user_levels WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            total = (await cursor.fetchone())[0]
        
        # Get leaderboard page
        async with db.execute(
            """SELECT user_id, xp, level, messages
            FROM user_levels 
            WHERE guild_id = ?
            ORDER BY xp DESC
            LIMIT ? OFFSET ?""",
            (guild_id, limit, offset)
        ) as cursor:
            rows = await cursor.fetchall()
        
        data = []
        for idx, row in enumerate(rows, start=offset + 1):
            data.append({
                "rank": idx,
                "userId": str(row[0]),
                "xp": row[1],
                "level": row[2],
                "messages": row[3]
            })
        
        return {
            "data": data,
            "page": page,
            "totalPages": (total + limit - 1) // limit,
            "total": total
        }
    finally:
        await db.close()

# Get guild settings
@app.get("/api/server/{guild_id}/settings")
async def get_guild_settings(guild_id: int):
    db = await get_db()
    try:
        # Get settings
        async with db.execute(
            'SELECT levelup_channel_id FROM guild_settings WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            settings = await cursor.fetchone()
        
        # Get role rewards
        async with db.execute(
            'SELECT level, role_id FROM role_rewards WHERE guild_id = ? ORDER BY level',
            (guild_id,)
        ) as cursor:
            role_rewards = await cursor.fetchall()
        
        return {
            "levelupChannelId": str(settings[0]) if settings and settings[0] else None,
            "roleRewards": [
                {"level": rr[0], "roleId": str(rr[1])}
                for rr in role_rewards
            ]
        }
    finally:
        await db.close()

# Update guild settings
@app.post("/api/server/{guild_id}/settings")
async def update_guild_settings(guild_id: int, settings: dict):
    db = await get_db()
    try:
        # Update levelup channel
        if "levelupChannelId" in settings:
            channel_id = int(settings["levelupChannelId"]) if settings["levelupChannelId"] else None
            
            if channel_id is None:
                await db.execute(
                    'DELETE FROM guild_settings WHERE guild_id = ?',
                    (guild_id,)
                )
            else:
                await db.execute(
                    """INSERT INTO guild_settings (guild_id, levelup_channel_id, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        levelup_channel_id = excluded.levelup_channel_id,
                        updated_at = excluded.updated_at""",
                    (guild_id, channel_id, __import__('time').time())
                )
        
        # Update role rewards
        if "roleRewards" in settings:
            # Clear existing
            await db.execute('DELETE FROM role_rewards WHERE guild_id = ?', (guild_id,))
            
            # Add new ones
            for reward in settings["roleRewards"]:
                await db.execute(
                    'INSERT INTO role_rewards (guild_id, level, role_id) VALUES (?, ?, ?)',
                    (guild_id, reward["level"], int(reward["roleId"]))
                )
        
        await db.commit()
        return {"success": True}
    finally:
        await db.close()

# Check if guild has bot
@app.get("/api/guild/{guild_id}/has-bot")
async def check_guild_has_bot(guild_id: int):
    db = await get_db()
    try:
        async with db.execute(
            'SELECT COUNT(*) FROM user_levels WHERE guild_id = ?',
            (guild_id,)
        ) as cursor:
            count = (await cursor.fetchone())[0]
        
        return {"hasMiku": count > 0}
    finally:
        await db.close()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
