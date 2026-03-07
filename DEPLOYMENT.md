# Miku Dashboard - Deployment Guide

This guide will help you deploy the Miku Dashboard to Vercel (free) while your bot runs on WispByte.

## Architecture Overview

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Discord   │ ◄─────► │  Bot + API   │ ◄─────► │  Dashboard  │
│   Server    │         │  (WispByte)  │         │  (Vercel)   │
└─────────────┘         └──────────────┘         └─────────────┘
                              │
                              ▼
                        ┌──────────┐
                        │ Database │
                        │ (SQLite) │
                        └──────────┘
```

- **Bot**: Runs on WispByte, handles Discord events
- **API Server**: FastAPI server (within bot), exposes database via REST API
- **Dashboard**: Next.js app on Vercel, calls bot API for data

## Prerequisites

1. Discord Application with OAuth2 configured
2. WispByte account (or any hosting for the bot)
3. Vercel account (free)
4. Git repository (GitHub, GitLab, or Bitbucket)

---

## Part 1: Deploy Bot with API Server to WispByte

### Step 1: Configure Environment Variables

Update your `.env` file on WispByte with:

```env
DISCORD_BOT_TOKEN=your_bot_token_here
API_PORT=8000
ALLOWED_ORIGINS=https://your-dashboard.vercel.app
```

### Step 2: Update Bot Startup Script

You need to run both the Discord bot AND the API server. Create a startup script or use a process manager.

**Option A: Using a simple bash script (start.sh):**

```bash
#!/bin/bash
# Start API server in background
python src/api_server.py &
API_PID=$!

# Start Discord bot
python main.py

# Cleanup on exit
kill $API_PID
```

**Option B: Using Python multiprocessing (recommended):**

Create `start_all.py`:

```python
import multiprocessing
import sys
import os

def run_bot():
    from src.bot import main
    import asyncio
    asyncio.run(main())

def run_api():
    import uvicorn
    from src.api_server import app
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Start API server process
    api_process = multiprocessing.Process(target=run_api)
    api_process.start()
    
    # Start bot in main process
    run_bot()
    
    # Cleanup
    api_process.terminate()
    api_process.join()
```

Then update your WispByte startup command to:
```bash
python start_all.py
```

### Step 3: Get Your API URL

Once deployed, note down your bot's API URL. This will be something like:
- `https://your-bot-domain.wispbyte.com`
- Or the public URL WispByte provides

Test it by visiting: `https://your-bot-url.com/` - should return `{"status": "ok", "message": "Miku Bot API is running"}`

---

## Part 2: Configure Discord OAuth2

### Step 1: Go to Discord Developer Portal

1. Visit https://discord.com/developers/applications
2. Select your application
3. Go to **OAuth2** → **General**

### Step 2: Add Redirect URLs

Add these redirect URLs:
```
http://localhost:3000/api/auth/callback/discord
https://your-dashboard.vercel.app/api/auth/callback/discord
```

(Replace `your-dashboard` with your actual Vercel project name)

### Step 3: Note Your Credentials

Copy these values:
- **Client ID**
- **Client Secret**
- **Bot Token** (from Bot section)

---

## Part 3: Deploy Dashboard to Vercel

### Step 1: Push Code to Git

```bash
cd dash
git init
git add .
git commit -m "Prepare dashboard for deployment"
git remote add origin https://github.com/yourusername/miku-dashboard.git
git push -u origin main
```

### Step 2: Connect to Vercel

1. Go to https://vercel.com
2. Click **"Add New Project"**
3. Import your Git repository
4. **⚠️ IMPORTANT: Configure Root Directory**
   - In the project configuration screen
   - Find **"Root Directory"** setting
   - Click **"Edit"**
   - Set it to: `dash`
   - Click **"Continue"**
5. Vercel will auto-detect Next.js

### Step 3: Configure Environment Variables

In Vercel project settings → **Environment Variables**, add:

| Variable | Value | Where to Get It |
|----------|-------|-----------------|
| `NEXTAUTH_URL` | `https://your-dashboard.vercel.app` | Vercel will show this after first deploy |
| `NEXTAUTH_SECRET` | Generate with: `openssl rand -base64 32` | Run in terminal |
| `DISCORD_CLIENT_ID` | Your Discord Client ID | Discord Developer Portal |
| `DISCORD_CLIENT_SECRET` | Your Discord Client Secret | Discord Developer Portal |
| `DISCORD_BOT_TOKEN` | Your Discord Bot Token | Discord Developer Portal |
| `BOT_API_URL` | `https://your-bot-url.com` | From Part 1, Step 3 |

### Step 4: Deploy

Click **"Deploy"**. Vercel will build and deploy your dashboard.

### Step 5: Update Discord Redirect URL

After first deployment:
1. Note your Vercel URL (e.g., `miku-dashboard.vercel.app`)
2. Go back to Discord Developer Portal
3. Update the redirect URL to match exactly: `https://miku-dashboard.vercel.app/api/auth/callback/discord`
4. Update `NEXTAUTH_URL` in Vercel environment variables
5. Redeploy in Vercel

---

## Part 4: Update Bot CORS Settings

Update your bot's `.env`:

```env
ALLOWED_ORIGINS=https://your-dashboard.vercel.app
```

This ensures only your dashboard can access the API.

---

## Verification

### Test Bot API

```bash
curl https://your-bot-url.com/
# Should return: {"status": "ok", "message": "Miku Bot API is running"}
```

### Test Dashboard

1. Visit your Vercel URL
2. Click "Login with Discord"
3. Authorize the application
4. You should see your servers
5. Click on a server to view stats

---

## Troubleshooting

### "Failed to fetch from bot API"

- Check `BOT_API_URL` in Vercel environment variables
- Ensure API server is running on WispByte
- Check CORS settings (ALLOWED_ORIGINS)
- Test API endpoint directly: `https://your-bot-url.com/api/server/{guild_id}/stats`

### "Unauthorized" on Dashboard

- Check DISCORD_BOT_TOKEN is set correctly in Vercel
- Verify token has proper permissions

### "OAuth Error"

- Verify NEXTAUTH_URL matches your Vercel domain exactly
- Check Discord redirect URLs are correct
- Ensure NEXTAUTH_SECRET is set

### CORS Errors

- Update ALLOWED_ORIGINS on bot to include your Vercel domain
- Redeploy bot

---

## Cost Breakdown (All FREE! 🎉)

| Service | Cost | Limits |
|---------|------|--------|
| **Vercel** | FREE | 100GB bandwidth/month |
| **WispByte** | FREE | Check their free tier limits |
| **Discord API** | FREE | Unlimited |

---

## Custom Domain (Optional)

### For Dashboard (Vercel):

1. Go to Vercel Project → Settings → Domains
2. Add your custom domain
3. Update DNS records as instructed
4. Update NEXTAUTH_URL and Discord redirect URLs

### For Bot API (WispByte):

1. Check WispByte documentation for custom domain setup
2. Update BOT_API_URL in Vercel after setup

---

## Monitoring

### Dashboard Logs:
- Vercel Dashboard → Project → Deployments → View Logs

### Bot Logs:
- Check WispByte console/logs

### API Health Check:
Monitor: `https://your-bot-url.com/` should always return `{"status": "ok"}`

---

## Updating

### Update Dashboard:
```bash
git add .
git commit -m "Update dashboard"
git push
```
Vercel auto-deploys on push!

### Update Bot:
Push changes to WispByte via their deployment method.

---

## Security Best Practices

1. ✅ Never commit `.env` files
2. ✅ Use environment variables for all secrets
3. ✅ Restrict CORS to your dashboard domain only
4. ✅ Rotate NEXTAUTH_SECRET periodically
5. ✅ Keep dependencies updated

---

## Support

If you encounter issues:
1. Check Vercel deployment logs
2. Check WispByte bot logs
3. Verify all environment variables are set correctly
4. Test API endpoints directly
5. Check Discord Developer Portal for OAuth errors

---

## Architecture Benefits

✨ **Free hosting** for both bot and dashboard  
✨ **Scalable** - Vercel scales automatically  
✨ **Fast** - CDN distribution for dashboard  
✨ **Secure** - No direct database exposure  
✨ **Maintainable** - Clear separation of concerns

---

Congratulations! Your Miku Dashboard is now deployed! 🎉
