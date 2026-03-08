# API Integration Guide

This guide explains how to integrate the Miku bot with the Next.js dashboard.

## Overview

The dashboard communicates with your Python bot through REST API endpoints. You'll need to add a web server to your bot to expose these endpoints.

## Setting Up the Bot API

### Step 1: Install FastAPI

Add FastAPI to your bot for handling HTTP requests:

```bash
pip install fastapi uvicorn
```

### Step 2: Create API Server

Create `src/api/server.py`:

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import discord

app = FastAPI(title="Miku Bot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Your dashboard URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store bot reference
bot_instance = None

def init_api(bot: discord.Bot):
    """Initialize API with bot instance"""
    global bot_instance
    bot_instance = bot

@app.get("/")
async def root():
    return {"status": "online", "bot": "Miku"}

@app.get("/api/server/{server_id}/stats")
async def get_server_stats(server_id: str):
    """Get server statistics"""
    guild = bot_instance.get_guild(int(server_id))
    if not guild:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Get stats from database
    # This is a simplified example - implement your actual logic
    from src.utils.database import Database
    db = Database()
    
    stats = await db.get_server_stats(guild.id)
    
    return {
        "totalMembers": guild.member_count,
        "totalXP": stats.get("total_xp", 0),
        "activeUsers": stats.get("active_users", 0),
        "averageLevel": stats.get("average_level", 0),
        "topUser": {
            "username": stats.get("top_user_name", "Unknown"),
            "level": stats.get("top_user_level", 0)
        }
    }

@app.get("/api/server/{server_id}/leaderboard")
async def get_leaderboard(server_id: str, page: int = 1, limit: int = 50):
    """Get server leaderboard"""
    from src.utils.database import Database
    db = Database()
    
    offset = (page - 1) * limit
    leaderboard = await db.get_leaderboard(int(server_id), limit=limit, offset=offset)
    total = await db.get_total_users(int(server_id))
    
    return {
        "data": leaderboard,
        "page": page,
        "totalPages": (total + limit - 1) // limit,
        "total": total
    }

@app.get("/api/user/{user_id}")
async def get_user_data(user_id: str, guild: str):
    """Get user data for specific guild"""
    from src.utils.database import Database
    db = Database()
    
    user_data = await db.get_user(int(user_id), int(guild))
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user_data

# Admin endpoints (add authentication middleware in production)
@app.post("/api/admin/setlevel")
async def set_user_level(user_id: str, guild_id: str, level: int):
    """Set user level (Admin only)"""
    from src.utils.database import Database
    db = Database()
    
    await db.set_user_level(int(user_id), int(guild_id), level)
    return {"success": True, "message": f"Set user {user_id} to level {level}"}

@app.post("/api/admin/addxp")
async def add_user_xp(user_id: str, guild_id: str, xp: int):
    """Add XP to user (Admin only)"""
    from src.utils.database import Database
    db = Database()
    
    await db.add_xp(int(user_id), int(guild_id), xp)
    return {"success": True, "message": f"Added {xp} XP to user {user_id}"}

@app.post("/api/admin/resetlevel")
async def reset_user_level(user_id: str, guild_id: str):
    """Reset user level (Admin only)"""
    from src.utils.database import Database
    db = Database()
    
    await db.reset_user(int(user_id), int(guild_id))
    return {"success": True, "message": f"Reset user {user_id}"}
```

### Step 3: Start API Server

Modify your `main.py` to run the API server:

```python
import asyncio
from src.bot import bot
from src.api.server import app, init_api
import uvicorn

async def main():
    # Initialize API
    init_api(bot)
    
    # Start API server in background
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    # Run both bot and API server
    await asyncio.gather(
        server.serve(),
        bot.start(os.getenv("DISCORD_BOT_TOKEN"))
    )

if __name__ == "__main__":
    asyncio.run(main())
```

## Database Methods

Add these methods to your `src/utils/database.py`:

```python
async def get_server_stats(self, guild_id: int) -> dict:
    """Get aggregated server statistics"""
    cursor = await self.db.execute(
        """
        SELECT 
            COUNT(*) as active_users,
            SUM(xp) as total_xp,
            AVG(level) as average_level
        FROM levels 
        WHERE guild_id = ?
        """,
        (guild_id,)
    )
    stats = await cursor.fetchone()
    
    # Get top user
    cursor = await self.db.execute(
        """
        SELECT user_id, level 
        FROM levels 
        WHERE guild_id = ? 
        ORDER BY xp DESC 
        LIMIT 1
        """,
        (guild_id,)
    )
    top_user = await cursor.fetchone()
    
    return {
        "active_users": stats[0] or 0,
        "total_xp": stats[1] or 0,
        "average_level": stats[2] or 0,
        "top_user_id": top_user[0] if top_user else None,
        "top_user_level": top_user[1] if top_user else 0
    }

async def get_leaderboard(self, guild_id: int, limit: int = 50, offset: int = 0) -> list:
    """Get paginated leaderboard"""
    cursor = await self.db.execute(
        """
        SELECT 
            user_id, xp, level, messages,
            ROW_NUMBER() OVER (ORDER BY xp DESC) as rank
        FROM levels 
        WHERE guild_id = ?
        ORDER BY xp DESC
        LIMIT ? OFFSET ?
        """,
        (guild_id, limit, offset)
    )
    rows = await cursor.fetchall()
    
    return [
        {
            "rank": row[4],
            "userId": str(row[0]),
            "username": "User",  # Fetch from Discord API
            "discriminator": "0000",
            "avatar": None,
            "level": row[2],
            "xp": row[1],
            "totalXp": row[1],  # Calculate based on level
        }
        for row in rows
    ]

async def get_total_users(self, guild_id: int) -> int:
    """Get total number of users with XP"""
    cursor = await self.db.execute(
        "SELECT COUNT(*) FROM levels WHERE guild_id = ?",
        (guild_id,)
    )
    result = await cursor.fetchone()
    return result[0] if result else 0
```

## Security Considerations

### 1. Add Authentication

Use JWT tokens or API keys to secure admin endpoints:

```python
from fastapi import Header, HTTPException

async def verify_token(authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {API_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")
```

### 2. Rate Limiting

Add rate limiting to prevent abuse:

```bash
pip install slowapi
```

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/server/{server_id}/stats")
@limiter.limit("10/minute")
async def get_server_stats(request: Request, server_id: str):
    # ... implementation
```

### 3. CORS Configuration

In production, update CORS to only allow your dashboard domain:

```python
allow_origins=[
    "https://yourdomain.com",
    "https://dashboard.yourdomain.com"
]
```

## Testing the API

### Using curl

```bash
# Get server stats
curl http://localhost:8000/api/server/123456789/stats

# Get leaderboard
curl http://localhost:8000/api/server/123456789/leaderboard?page=1
```

### Using the Dashboard

1. Start your bot with API server
2. Start the dashboard: `cd dash && npm run dev`
3. Login with Discord
4. Select a server to view stats

## Troubleshooting

### CORS Errors
- Check that dashboard URL is in `allow_origins`
- Ensure credentials are enabled

### 404 Errors
- Verify API server is running on correct port
- Check `API_URL` in dashboard `.env.local`

### Data Not Loading
- Check bot has access to the guild
- Verify database has data for the guild
- Look at browser console for errors

## Next Steps

- Add caching with Redis
- Implement WebSocket for real-time updates
- Add authentication middleware
- Create admin permission checking
- Add more detailed analytics endpoints

---

For more information, see the [dashboard README](../dash/README.md).
