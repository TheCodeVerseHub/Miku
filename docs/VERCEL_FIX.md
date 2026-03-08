# Vercel Deployment - Quick Fix

## ❌ Error: "No Next.js version detected"

This happens because Vercel is looking in the wrong directory.

## ✅ Solution

### Option 1: Configure Root Directory in Vercel (Recommended)

1. Go to your Vercel project dashboard
2. Click **Settings** (top menu)
3. Click **General** (left sidebar)
4. Find **"Root Directory"** section
5. Click **"Edit"**
6. Set to: `dash`
7. Click **"Save"**
8. Go to **Deployments** tab
9. Click **"Redeploy"** on the latest deployment

### Option 2: Use Vercel CLI

```bash
cd dash
vercel --prod
```

This deploys from the dash directory directly.

### Option 3: Restructure Repository (Not Recommended)

Move everything from `dash/` to root, but this breaks the bot structure.

## Verification

After setting Root Directory to `dash`:

1. Vercel will find `dash/package.json`
2. Build will succeed
3. Your dashboard will be live!

## Still Having Issues?

Make sure:
- [ ] Root Directory is set to `dash`
- [ ] Environment variables are set in Vercel
- [ ] `dash/package.json` exists with Next.js dependency

## Environment Variables Needed

In Vercel → Settings → Environment Variables:

```
NEXTAUTH_URL=https://your-project.vercel.app
NEXTAUTH_SECRET=generate_with_openssl
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_BOT_TOKEN=your_bot_token
BOT_API_URL=https://your-bot-api-url.com
```

After adding, redeploy!
