# Fix NextAuth CLIENT_FETCH_ERROR on Vercel

## Problem
```
[next-auth][error][CLIENT_FETCH_ERROR]
https://next-auth.js.org/errors#client_fetch_error undefined
```

This error occurs when NextAuth environment variables are missing or incorrectly configured on Vercel.

## Solution: Set Environment Variables on Vercel

### 1. Generate NEXTAUTH_SECRET

Run this command to generate a secure secret:

```bash
openssl rand -base64 32
```

Copy the output (something like: `jK8mN2pQ5rS7tU9vW0xY1zA3bC4dE5fF6gH7iJ8kL9mN0oP1qR2sT3u=`)

### 2. Add Environment Variables to Vercel

Go to your Vercel project settings:

**Vercel Dashboard → Your Project → Settings → Environment Variables**

Add these variables:

#### Required Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXTAUTH_URL` | `https://miku-two.vercel.app` | Your full Vercel deployment URL |
| `NEXTAUTH_SECRET` | `<generated_secret>` | The secret from step 1 |
| `DISCORD_CLIENT_ID` | `<your_discord_app_client_id>` | From Discord Developer Portal |
| `DISCORD_CLIENT_SECRET` | `<your_discord_app_client_secret>` | From Discord Developer Portal |
| `BOT_API_URL` | `https://miku-fjwa.onrender.com` | Your Render backend URL |

#### Important Settings

For each environment variable:
- ✅ Check **Production**
- ✅ Check **Preview**
- ✅ Check **Development** (optional)

### 3. Update Discord OAuth2 Redirect URL

Go to **Discord Developer Portal → Your App → OAuth2 → Redirects**

Add/Update redirect URL:
```
https://miku-two.vercel.app/api/auth/callback/discord
```

### 4. Redeploy

After adding environment variables, trigger a new deployment:

**Option A - Via Vercel Dashboard:**
- Go to **Deployments** tab
- Click **⋯** on the latest deployment
- Click **Redeploy**

**Option B - Via Git Push:**
```bash
git commit --allow-empty -m "Trigger redeploy"
git push
```

### 5. Verify

After deployment completes:

1. Visit `https://miku-two.vercel.app`
2. Click "Sign in with Discord"
3. You should be redirected to Discord OAuth
4. After authorization, you should be redirected back and signed in

Check Vercel logs for any remaining errors:
- Go to **Deployments** → Click latest deployment → **Runtime Logs**

## Common Issues

### Issue: Still getting CLIENT_FETCH_ERROR

**Solution:** Clear browser cookies and try again:
```
1. Open browser DevTools (F12)
2. Application/Storage tab
3. Clear cookies for miku-two.vercel.app
4. Refresh and try signing in again
```

### Issue: OAuth redirect mismatch

**Solution:** Ensure Discord redirect URL EXACTLY matches:
```
https://miku-two.vercel.app/api/auth/callback/discord
```
- No trailing slash
- Must use https
- Must match your NEXTAUTH_URL

### Issue: Session not persisting

**Solution:** Ensure cookies are not blocked:
- Check browser privacy settings
- Try in incognito/private mode
- Check browser console for cookie warnings

## Environment Variable Checklist

Copy this checklist and verify each variable:

```
Vercel Environment Variables (https://vercel.com/your-account/miku-two/settings/environment-variables):

[ ] NEXTAUTH_URL = https://miku-two.vercel.app
[ ] NEXTAUTH_SECRET = <32+ character random string>
[ ] DISCORD_CLIENT_ID = <from Discord Developer Portal>
[ ] DISCORD_CLIENT_SECRET = <from Discord Developer Portal>
[ ] BOT_API_URL = https://miku-fjwa.onrender.com

Discord OAuth2 Redirects (https://discord.com/developers/applications):

[ ] https://miku-two.vercel.app/api/auth/callback/discord

Deployment:

[ ] Redeployed after adding environment variables
[ ] No errors in Vercel Runtime Logs
[ ] Successfully signed in with Discord
```

## Technical Details

### What Changed

Added explicit NextAuth configuration in `[...nextauth].ts`:

```typescript
export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,  // Now explicitly required
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60,  // 30 days
  },
  cookies: {
    sessionToken: {
      name: `${process.env.NODE_ENV === 'production' ? '__Secure-' : ''}next-auth.session-token`,
      options: {
        httpOnly: true,
        sameSite: 'lax',
        path: '/',
        secure: process.env.NODE_ENV === 'production',
      },
    },
  },
  // ... rest of config
}
```

### Why This Fixes It

1. **Explicit secret**: NextAuth now explicitly uses `NEXTAUTH_SECRET` environment variable
2. **Production cookies**: Uses secure cookies in production (`__Secure-` prefix, `secure: true`)
3. **Session strategy**: Explicitly sets JWT strategy with 30-day expiration
4. **Cookie settings**: Properly configured for Vercel's serverless environment

## Support

If you continue to have issues after following this guide:

1. Check Vercel Runtime Logs for specific errors
2. Check browser console (F12) for client-side errors
3. Verify all environment variables are set correctly
4. Try clearing all cookies and cache
5. Test in incognito/private browsing mode

---

**Last Updated:** March 8, 2026
