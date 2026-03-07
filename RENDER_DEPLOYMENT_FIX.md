# Render Deployment Fix Guide 🚀

## Issues Fixed

1. **LeaderboardTable Error** - Fixed `Cannot read properties of undefined (reading 'toLocaleString')`
2. **Environment Variables** - Setup guide for Render environment variables

---

## Part 1: LeaderboardTable Fix ✅

### Problem
The component expected both `xp` (level progress) and `totalXp` (total XP), but the API only returns `xp` as total XP.

### Solution
Updated the component to:
- Use `xp` as the total XP
- Calculate current level progress from total XP and level
- Added proper null checks

**File Updated:** `dash/src/components/LeaderboardTable.tsx`

---

## Part 2: Render Environment Variables Setup

### Required Environment Variables for API Server (Backend)

Go to your Render Dashboard → Your API Service → Environment → Add the following:

#### 1. Database Configuration
```
DATABASE_URL=postgresql://user:password@host:5432/database
```
**Where to get it:**
- If using Render PostgreSQL: Copy from your Render database "Internal Database URL"
- Format: `postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE_NAME`

#### 2. CORS Configuration
```
ALLOWED_ORIGINS=https://your-dashboard.vercel.app,https://your-dashboard-git-*.vercel.app,http://localhost:3000
```
**Replace with:**
- Your Vercel dashboard URL(s)
- Include preview deployments if needed
- Keep localhost for testing

#### 3. API Port (Optional)
```
API_PORT=8000
```
**Note:** Render automatically sets PORT, so this might not be needed

---

## Part 3: Vercel Environment Variables Setup

### For Dashboard (Frontend on Vercel)

Go to Vercel Dashboard → Your Project → Settings → Environment Variables:

#### 1. NextAuth Configuration
```
NEXTAUTH_URL=https://your-dashboard.vercel.app
NEXTAUTH_SECRET=your_random_secret_here
```

**Generate NEXTAUTH_SECRET:**
```bash
openssl rand -base64 32
```

#### 2. Discord OAuth2
```
DISCORD_CLIENT_ID=your_discord_client_id
DISCORD_CLIENT_SECRET=your_discord_client_secret
```

**Where to get:**
1. Go to https://discord.com/developers/applications
2. Select your bot application
3. Go to OAuth2 → General
4. Copy Client ID and Client Secret
5. Add redirect URL: `https://your-dashboard.vercel.app/api/auth/callback/discord`

#### 3. Backend API URL
```
API_URL=https://your-api-service.onrender.com
BOT_API_URL=https://your-api-service.onrender.com
```

**Replace with:**
- Your Render API service URL (e.g., `https://miku-api.onrender.com`)

#### 4. Discord Bot Token
```
DISCORD_BOT_TOKEN=your_bot_token_here
```

**Where to get:**
1. Go to https://discord.com/developers/applications
2. Select your bot
3. Go to Bot → Token
4. Copy the token

#### 5. Public Client ID (Optional)
```
NEXT_PUBLIC_DISCORD_CLIENT_ID=your_discord_client_id
```
For the invite link on dashboard

---

## Part 4: Testing the Deployment

### 1. Test API Server on Render

```bash
# Check health endpoint
curl https://your-api-service.onrender.com/api/health

# Should return: {"status":"ok"}
```

### 2. Test batch-check endpoint

```bash
curl -X POST https://your-api-service.onrender.com/api/guilds/batch-check \
  -H "Content-Type: application/json" \
  -d '[]'

# Should return: {}
```

### 3. Test Dashboard

1. Visit your Vercel dashboard URL
2. Sign in with Discord
3. Check browser console (F12) for any errors
4. Dashboard should load in 3-5 seconds

---

## Part 5: Common Issues & Solutions

### Issue 1: "DATABASE_URL environment variable is not set"

**Solution:**
1. Go to Render Dashboard → Your Service → Environment
2. Add `DATABASE_URL` variable
3. If you have a Render PostgreSQL database, copy the "Internal Database URL"
4. Click "Save Changes"
5. Redeploy the service

### Issue 2: "Failed to fetch guilds" on Dashboard

**Causes:**
- API URL is wrong in Vercel environment variables
- CORS is not configured properly
- API server is not running

**Solution:**
1. Check API_URL in Vercel matches your Render API URL
2. Update ALLOWED_ORIGINS in Render to include your Vercel URL
3. Test API health endpoint manually

### Issue 3: CORS Errors

**Error in browser console:**
```
Access to fetch at 'https://api.onrender.com/...' from origin 'https://dashboard.vercel.app' 
has been blocked by CORS policy
```

**Solution:**
1. Go to Render → Your API Service → Environment
2. Update ALLOWED_ORIGINS to include your Vercel domain:
   ```
   ALLOWED_ORIGINS=https://your-dashboard.vercel.app,https://your-dashboard-git-*.vercel.app
   ```
3. Save and redeploy

### Issue 4: "Cannot read properties of undefined"

**If you still get this error:**

1. Check browser console for the API response
2. Open Network tab in DevTools
3. Find the leaderboard API call
4. Check the response structure
5. Ensure it matches what the component expects

### Issue 5: NextAuth Redirect Error

**Error:** "Redirect URL mismatch"

**Solution:**
1. Go to Discord Developer Portal
2. OAuth2 → General → Redirects
3. Add: `https://your-dashboard.vercel.app/api/auth/callback/discord`
4. Save changes

### Issue 6: Render Service Sleeping

**Issue:** First request takes 30+ seconds

**Solution:** 
- Render free tier services spin down after inactivity
- First request wakes them up (slow)
- Options:
  1. Upgrade to paid tier (no sleeping)
  2. Use a cron job to ping health endpoint every 10 minutes
  3. Accept the initial delay

---

## Part 6: Render Service Configuration

### Update render.yaml (Optional)

If using `render.yaml` for infrastructure as code:

```yaml
services:
  - type: web
    name: miku-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python src/api_server.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: API_PORT
        value: 8000
      # Add other env vars in Render Dashboard (not in YAML for security)

databases:
  - name: miku-db
    plan: free
    databaseName: miku
    user: miku
```

**Note:** Don't put sensitive values in `render.yaml` - add them in Dashboard

---

## Part 7: Verification Checklist

### Backend (Render)

- [ ] API service is deployed and running
- [ ] DATABASE_URL is set correctly
- [ ] ALLOWED_ORIGINS includes Vercel URL
- [ ] Health endpoint returns 200 OK
- [ ] Batch-check endpoint works

### Frontend (Vercel)

- [ ] Dashboard is deployed
- [ ] NEXTAUTH_URL matches Vercel URL
- [ ] NEXTAUTH_SECRET is set
- [ ] DISCORD_CLIENT_ID is set
- [ ] DISCORD_CLIENT_SECRET is set
- [ ] API_URL points to Render service
- [ ] DISCORD_BOT_TOKEN is set
- [ ] Discord OAuth redirect URL is configured

### Testing

- [ ] Can sign in with Discord
- [ ] Guilds load within 5 seconds
- [ ] No CORS errors in console
- [ ] Leaderboard displays without errors
- [ ] Stats page loads correctly

---

## Part 8: Monitoring & Debugging

### View Render Logs

```bash
# In Render Dashboard
1. Go to your service
2. Click "Logs" tab
3. Look for errors or startup issues
```

### View Vercel Logs

```bash
# Using Vercel CLI
vercel logs your-project-name

# Or in Vercel Dashboard → Deployments → View Function Logs
```

### Enable Debug Mode (Temporary)

Add to Render environment variables:
```
DEBUG=true
LOG_LEVEL=debug
```

Add to Vercel environment variables:
```
NEXT_PUBLIC_DEBUG=true
```

---

## Part 9: Performance Optimization

### Render Configuration

1. **Database Connection Pooling**
   - Already configured in `api_server.py` with `asyncpg.create_pool()`
   - Min: 1, Max: 10 connections

2. **Add Database Index** (if not exists)
   ```sql
   CREATE INDEX IF NOT EXISTS idx_user_levels_guild_id 
   ON user_levels(guild_id);
   ```

3. **Health Check Configuration**
   - Render automatically pings `/` endpoint
   - Returns 200 OK if service is healthy

### Vercel Configuration

- Automatic CDN for static assets
- Edge caching for API routes
- Already configured with SWR caching

---

## Summary: Quick Setup Steps

### 1. API Server (Render)
```bash
1. Create new Web Service
2. Connect GitHub repository
3. Set build command: pip install -r requirements.txt
4. Set start command: python src/api_server.py
5. Add environment variables (DATABASE_URL, ALLOWED_ORIGINS)
6. Deploy
```

### 2. Database (Render)
```bash
1. Create new PostgreSQL database
2. Copy Internal Database URL
3. Add to API service as DATABASE_URL
```

### 3. Dashboard (Vercel)
```bash
1. Import GitHub repository
2. Set Root Directory: dash
3. Add environment variables (NEXTAUTH_*, DISCORD_*, API_URL)
4. Deploy
```

### 4. Discord Developer Portal
```bash
1. Add OAuth2 redirect: https://your-dashboard.vercel.app/api/auth/callback/discord
2. Copy Client ID and Secret to Vercel env vars
```

---

## Need More Help?

1. Check Render logs for backend errors
2. Check Vercel logs for frontend errors
3. Check browser console for network errors
4. Test API endpoints manually with curl
5. Verify all environment variables are set

The dashboard should now work perfectly on Render and Vercel! 🎉
