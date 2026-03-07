# Keep-Alive Setup Guide

This prevents your Render service from spinning down (sleeping) after 15 minutes of inactivity.

## What It Does

The GitHub Action pings your API every 10 minutes to keep it awake, preventing cold starts.

## Benefits

- ✅ Dashboard loads in 3-5 seconds (not 30-60 seconds)
- ✅ No timeouts on first load
- ✅ Better user experience
- ✅ Free (uses GitHub Actions minutes)

## Setup Instructions

### Step 1: Add API URL Secret to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `API_URL`
5. Value: `https://your-api-service.onrender.com` (your Render API URL)
6. Click **Add secret**

### Step 2: Enable GitHub Actions

The workflow file is already in `.github/workflows/keep-alive.yml`.

1. Go to your GitHub repository
2. Click **Actions** tab
3. Find "Keep Render Service Alive"
4. Click **Enable workflow** if disabled

### Step 3: Test It

1. Go to **Actions** tab
2. Click "Keep Render Service Alive"
3. Click **Run workflow** → **Run workflow**
4. Wait ~30 seconds
5. Check the results - should show ✅ green checkmark

### Step 4: Verify It's Working

After 10 minutes:
1. Go to Actions tab
2. You should see automatic runs every 10 minutes
3. Each run should show green checkmark

## How It Works

```
Every 10 minutes:
    ↓
GitHub Action triggers
    ↓
Pings: https://your-api.onrender.com/api/health
    ↓
Render service stays awake
    ↓
No cold starts! 🎉
```

## Cost

**GitHub Actions Free Tier:**
- 2,000 minutes/month (free)
- This workflow uses ~1 minute per day
- Total: ~30 minutes/month
- **100% free for most users**

## Alternative: UptimeRobot (No GitHub Actions)

If you prefer not to use GitHub Actions:

1. Sign up at https://uptimerobot.com (free)
2. Add New Monitor:
   - Monitor Type: HTTP(s)
   - URL: `https://your-api.onrender.com/api/health`
   - Monitoring Interval: 10 minutes
   - Alert Contacts: Your email
3. Click Create Monitor

## Troubleshooting

### Workflow Fails with "secrets.API_URL is empty"

**Solution:** 
1. Make sure you added `API_URL` secret in GitHub
2. Name must be exactly `API_URL`
3. Value must be your full Render URL (e.g., `https://miku-api.onrender.com`)

### Workflow Shows "Service returned HTTP 500"

**Causes:**
- Database not connected
- API server crashed
- Check Render logs for errors

**Solution:**
1. Go to Render Dashboard → Your Service → Logs
2. Look for error messages
3. Make sure DATABASE_URL is set
4. Restart service if needed

### Workflow Still Running After Deleting

**Solution:**
```bash
# Disable the workflow:
1. Go to Actions tab
2. Click "Keep Render Service Alive"
3. Click "..." (three dots)
4. Click "Disable workflow"

# Or delete the file:
rm .github/workflows/keep-alive.yml
git add .
git commit -m "Remove keep-alive"
git push
```

## Monitoring Dashboard Response Time

With keep-alive enabled:

| Scenario | Before Keep-Alive | After Keep-Alive |
|----------|------------------|------------------|
| First load (cold) | 30-60 seconds | 3-5 seconds |
| Second load (warm) | 3-5 seconds | 3-5 seconds |
| After 15 min idle | 30-60 seconds | 3-5 seconds |

## Disable If Not Needed

If you upgrade to Render paid plan ($7/month), you can disable this workflow as paid plans don't sleep.

To disable:
1. Go to Actions → Keep Render Service Alive
2. Click "..." → Disable workflow

## Summary

- ✅ Keeps Render service awake
- ✅ Prevents cold starts
- ✅ Free with GitHub Actions
- ✅ Runs automatically every 10 minutes
- ✅ Dashboard always loads fast

Your dashboard will now load in 3-5 seconds instead of 30-60 seconds! 🚀
