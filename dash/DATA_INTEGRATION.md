# Real Database Integration Complete! 🎉

The dashboard now displays **real data** from your bot's SQLite database instead of mock data!

## What Changed

### ✅ New Database Module
Created `src/lib/database.ts` with functions to query the bot's database:
- `guildHasBot()` - Check if a guild has the bot
- `getServerStats()` - Get server statistics (member count, total XP, active users, average level, top user)
- `getLeaderboard()` - Get paginated leaderboard with real user data
- `getUserData()` - Get specific user's stats and rank

### ✅ Updated API Endpoints
1. **`/api/guilds`** - Now checks which servers actually have the bot in the database
2. **`/api/server/[serverId]/stats`** - Returns real statistics from the database
3. **`/api/server/[serverId]/leaderboard`** - Shows real users ranked by XP

## Setup Required

### 1. Add Bot Token to .env.local

Open `.env.local` and replace `your_bot_token_here` with your actual bot token:

```env
DISCORD_BOT_TOKEN=your_actual_bot_token_here
```

You can find your bot token in:
- Your bot's `.env` file (look for `DISCORD_TOKEN`)
- Discord Developer Portal: https://discord.com/developers/applications
  - Select your application → Bot → Token

### 2. Current Database Status

Your database currently has **1 user record**:
- **Guild ID**: `1410939321812258928`
- **User ID**: `955695820999639120`
- **XP**: 113
- **Level**: 0
- **Messages**: 5

### 3. Test the Dashboard

1. Start the development server:
   ```bash
   cd dash
   npm run dev
   ```

2. Visit http://localhost:3000

3. Login with Discord

4. You should see:
   - Only guilds that have data in the database will show "Miku Active"
   - Real statistics for guild `1410939321812258928`
   - Real leaderboard with Discord usernames and avatars

## How It Works

### Database Connection
The dashboard connects to your bot's SQLite database at `../data/leveling.db` in **read-only mode** to ensure it doesn't interfere with the bot.

### Data Flow
1. User logs in with Discord OAuth
2. Dashboard fetches user's guilds from Discord API
3. For each guild, checks if it exists in the database
4. When viewing a server:
   - Queries database for stats and leaderboard
   - Fetches Discord user data (usernames, avatars) using bot token
   - Displays real-time data from the database

### API Endpoints
All endpoints now use the database:

**GET /api/guilds**
- Returns user's Discord servers
- Marks which ones have the bot (by checking database)

**GET /api/server/[serverId]/stats**
- Total members (active users in DB)
- Total XP earned
- Active users count
- Average level
- Top user with their Discord username

**GET /api/server/[serverId]/leaderboard?page=1**
- Paginated list (50 per page)
- Ranked by XP
- Includes Discord usernames and avatars
- Shows level, XP, and message count

## Features

### ✅ Real-Time Data
- All data is fetched directly from the bot's database
- No caching or delays
- Accurate statistics

### ✅ Discord Integration
- Fetches Discord usernames and avatars
- Shows real user profiles
- Displays guild information

### ✅ Responsive Leaderboard
- Pagination (50 users per page)
- Sortable by rank
- Shows user stats (level, XP, messages)

### ✅ Server Statistics
- Total member count
- Total XP earned in the server
- Active user count
- Average level
- Top player with username

## Troubleshooting

### Empty Dashboard
**Problem**: No servers showing "Miku Active"
**Solution**: 
- Make sure your bot is actively being used in servers
- Users need to send messages for data to be recorded
- Check the database: `sqlite3 data/leveling.db "SELECT * FROM user_levels;"`

### Missing Usernames
**Problem**: Leaderboard shows "User#1234" instead of real usernames
**Solution**:
- Add `DISCORD_BOT_TOKEN` to `.env.local`
- Make sure the token is valid
- Restart the dev server after adding the token

### Database Errors
**Problem**: "Database connection failed"
**Solution**:
- Verify the database exists at `../data/leveling.db`
- Check file permissions (dashboard needs read access)
- Make sure the bot has created the database

### Build Errors
**Problem**: TypeScript errors during build
**Solution**:
- Run `npm install` to ensure all dependencies are installed
- Run `npm run build` to verify everything compiles

## Database Schema

The dashboard reads from the `user_levels` table:

```sql
CREATE TABLE user_levels (
    user_id INTEGER,
    guild_id INTEGER,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    messages INTEGER DEFAULT 0,
    last_message_time REAL DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
)
```

## Security Notes

- Database is opened in **read-only mode** to prevent accidental writes
- Bot token is stored in `.env.local` (not committed to git)
- All API routes require authentication
- User data is fetched securely via Discord API

## Next Steps

To see more data in your dashboard:
1. Invite your bot to more servers
2. Have users chat in those servers
3. The bot will record XP and levels
4. Dashboard will automatically show the new data

## Performance

- Database queries are optimized with indexes
- Discord API calls are batched where possible
- Pagination prevents loading too much data at once
- Read-only access ensures no conflicts with the bot

## Need Help?

If you encounter issues:
1. Check the browser console for errors (F12)
2. Check the terminal running `npm run dev` for server errors
3. Verify your `.env.local` has all required variables
4. Make sure the bot is running and recording data

---

**All mock data has been replaced with real database integration!** 🚀
