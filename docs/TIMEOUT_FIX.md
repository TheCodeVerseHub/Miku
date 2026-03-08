# Timeout & Settings Fix Guide 🔧

## Issues Fixed

### 1. AbortError on Production (FIXED ✅)
**Error:** `DOMException [AbortError]: This operation was aborted`

**Root Cause:** 
- Timeout was set to 3 seconds for batch-check
- On Render's free tier, services "spin down" after inactivity
- Cold start takes 30-60 seconds to wake up
- 3 second timeout was too short for cold starts

**Solution:**
- Increased timeout from 3 to 10 seconds
- Added better error handling to identify AbortError specifically
- Added warning message for timeouts vs other errors
- Dashboard continues to work even if batch-check times out

**Files Updated:**
- `dash/src/pages/api/guilds.ts`

### 2. Settings Save Failure (FIXED ✅)
**Error:** Settings page couldn't save level-up channel configuration

**Root Causes:**
- No timeout handling on POST request
- Generic error messages didn't show actual problem
- No logging to debug issues

**Solutions:**
- Added 10-second timeout to POST request
- Display actual error message from API
- Added console logging for debugging
- Better error feedback to users

**Files Updated:**
- `dash/src/pages/api/server/[serverId]/settings.ts`
- `dash/src/pages/server/[serverId]/settings.tsx`

---

## Understanding Render Free Tier

### How It Works

On Render's free tier:
1. **Service spins down** after 15 minutes of inactivity
2. **First request** after spin-down wakes it up (30-60 seconds)
3. **Subsequent requests** are fast while service is awake

### Why This Causes Timeouts

```
User opens dashboard
    ↓
Dashboard calls /api/guilds/batch-check
    ↓
Render service is asleep 💤
    ↓
Takes 30-60 seconds to wake up
    ↓
Old 3-second timeout triggers ❌
    ↓
New 10-second timeout may still fail on very slow cold starts
```

### Solutions

**Option 1: Keep Trying (Current)**
- Dashboard retries automatically
- Second attempt is fast (service now awake)
- User sees "No servers found" briefly, then they appear

**Option 2: Keep Service Awake**
Use a cron job to ping every 10 minutes:
```bash
# Use a service like cron-job.org or UptimeRobot
GET https://your-api.onrender.com/api/health
```

**Option 3: Upgrade to Paid Plan**
- Render paid plans don't spin down
- No cold starts
- Always fast

---

## Testing the Fixes

### 1. Test Cold Start Behavior

Simulate a cold start:
```bash
# Wait 15+ minutes for service to spin down
# Then try to load dashboard

# You should see:
# - Loading spinner
# - "Loading servers..." message
# - First attempt may timeout (expected)
# - Dashboard still loads with retry
```

### 2. Test Settings Save

```bash
# Go to server settings page
# Change level-up channel
# Click Save

# You should see:
# - "Saving..." state
# - Success message: "Settings saved successfully!"
# OR
# - Error message with specific reason
```

### 3. Check Logs

**Vercel Logs:**
```bash
# In Vercel dashboard
Deployments → Your Deployment → View Function Logs

# Look for:
[API] Updating settings for guild...
[API] Settings updated successfully
```

**Render Logs:**
```bash
# In Render dashboard
Your Service → Logs

# Look for:
[INFO] Starting API server on port 8000
POST /api/guilds/batch-check
POST /api/server/{id}/settings
```

---

## New Error Messages

### Before (Unhelpful ❌)
```
Error checking bot status for guild...
Failed to save settings
An error occurred while saving
```

### After (Helpful ✅)
```
Batch check timed out after 10 seconds - API may be on cold start
Request timed out - API may be on cold start. Please try again.
Network error - check if API server is running and try again
```

---

## Environment Variables Check

Make sure these are set in **Render Dashboard**:

```bash
DATABASE_URL=postgresql://...
ALLOWED_ORIGINS=https://your-dashboard.vercel.app
PORT=8000  # Render sets this automatically
```

Make sure these are set in **Vercel Dashboard**:

```bash
API_URL=https://your-api.onrender.com
BOT_API_URL=https://your-api.onrender.com
NEXTAUTH_URL=https://your-dashboard.vercel.app
NEXTAUTH_SECRET=...
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_BOT_TOKEN=...
```

---

## Common Issues & Solutions

### Issue 1: "Batch check timed out" on Every Load

**Cause:** API service is constantly sleeping

**Solutions:**
1. **Set up Uptime Monitor** (Recommended)
   - Sign up at https://uptimerobot.com (free)
   - Add monitor: `https://your-api.onrender.com/api/health`
   - Set interval: 10 minutes
   - This keeps your service awake

2. **Use GitHub Actions**
   Create `.github/workflows/keep-alive.yml`:
   ```yaml
   name: Keep Render Service Alive
   on:
     schedule:
       - cron: '*/10 * * * *'  # Every 10 minutes
   
   jobs:
     ping:
       runs-on: ubuntu-latest
       steps:
         - name: Ping health endpoint
           run: curl https://your-api.onrender.com/api/health
   ```

3. **Upgrade to Render Paid Plan**
   - $7/month
   - No sleeping
   - Faster performance

### Issue 2: Settings Save Fails Immediately

**Possible Causes:**
- API server is down
- CORS not configured
- Wrong API_URL in Vercel

**Check:**
```bash
# 1. Test API health
curl https://your-api.onrender.com/api/health

# 2. Test settings endpoint
curl -X POST https://your-api.onrender.com/api/server/123/settings \
  -H "Content-Type: application/json" \
  -d '{"levelupChannelId":null,"roleRewards":[]}'

# 3. Check CORS
# Open dashboard, F12 → Console
# Look for CORS errors
```

**Fix:**
1. Ensure ALLOWED_ORIGINS in Render includes your Vercel URL
2. Ensure API_URL in Vercel points to correct Render URL
3. Redeploy both services

### Issue 3: "Failed to load settings" Error

**Causes:**
- Database not connected
- Settings table doesn't exist
- Bot hasn't been used in server yet

**Fix:**
```bash
# Check if guild has data
curl https://your-api.onrender.com/api/server/YOUR_GUILD_ID/stats

# If 500 error, check database:
# 1. Verify DATABASE_URL is set
# 2. Check if tables exist
# 3. Run migrations if needed
```

### Issue 4: Settings Save Shows Success But Doesn't Work

**Cause:** Settings are saving to database, but bot isn't reading them

**Check:**
1. Bot is running and connected to same database
2. Bot cogs are loaded properly
3. Bot has permission to read guild_settings table

**Verify:**
```sql
-- Connect to your database
SELECT * FROM guild_settings WHERE guild_id = YOUR_GUILD_ID;

-- Should show your levelup_channel_id
```

---

## Performance Monitoring

### Check Response Times

```bash
# Test batch-check speed
time curl -X POST https://your-api.onrender.com/api/guilds/batch-check \
  -H "Content-Type: application/json" \
  -d '[123,456,789]'

# Should be:
# - Cold start: 30-60 seconds (first time)
# - Warm: < 1 second
```

### Check Dashboard Speed

1. Open dashboard
2. F12 → Network tab
3. Look at timing for `/api/guilds`
4. Should be:
   - Cold start: 10-15 seconds (expected)
   - Warm: 2-5 seconds

---

## Best Practices for Production

### 1. Use Uptime Monitoring
Prevents cold starts by keeping service awake

### 2. Add Database Indexes
```sql
CREATE INDEX IF NOT EXISTS idx_user_levels_guild_id 
ON user_levels(guild_id);

CREATE INDEX IF NOT EXISTS idx_guild_settings_guild_id 
ON guild_settings(guild_id);
```

### 3. Enable Logging
In Render environment variables:
```bash
LOG_LEVEL=info
```

### 4. Set Proper Timeouts
- 10 seconds for API calls (current)
- 5 seconds for database queries
- 30 seconds for Discord API

### 5. Add Health Checks
Render automatically uses `/` for health checks.
Make sure it returns 200 OK.

---

## Summary of Changes

| File | Change | Impact |
|------|--------|--------|
| `dash/src/pages/api/guilds.ts` | Increased timeout 3→10s | Handles cold starts better |
| `dash/src/pages/api/server/[serverId]/settings.ts` | Added timeout & logging | Better error handling |
| `dash/src/pages/server/[serverId]/settings.tsx` | Improved error messages | Better user feedback |
| `dash/src/pages/server/[serverId]/settings.tsx` | Added SWR config | Better caching & retries |

---

## Need More Help?

### Check These First:
1. ✅ API health endpoint returns 200
2. ✅ DATABASE_URL is set in Render
3. ✅ ALLOWED_ORIGINS includes Vercel URL
4. ✅ API_URL in Vercel points to Render
5. ✅ Discord OAuth redirect is configured

### Still Having Issues?

**Check Logs:**
- Vercel: Deployments → Function Logs
- Render: Your Service → Logs
- Browser: F12 → Console & Network tabs

**Test Manually:**
```bash
# Test each endpoint
curl https://your-api.onrender.com/api/health
curl https://your-api.onrender.com/api/server/123/stats
curl -X POST https://your-api.onrender.com/api/guilds/batch-check \
  -H "Content-Type: application/json" -d '[]'
```

Your dashboard should now handle cold starts gracefully and show better error messages! 🎉
