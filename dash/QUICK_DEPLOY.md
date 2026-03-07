# Quick Deployment Guide

## 🚀 For WispByte (Bot + API)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

3. **Run the bot with API server:**
   ```bash
   python start_all.py
   ```

   Or if WispByte requires `main.py`:
   Update `main.py` to import from `start_all.py`

4. **Get your API URL** and test it:
   ```bash
   curl https://your-bot-url.com/
   # Should return: {"status": "ok", "message": "Miku Bot API is running"}
   ```

---

## 🌐 For Vercel (Dashboard)

1. **Navigate to dashboard folder:**
   ```bash
   cd dash
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your values
   ```

4. **Test locally:**
   ```bash
   npm run dev
   # Open http://localhost:3000
   ```

5. **Deploy to Vercel:**
   - Push code to GitHub
   - Import project in Vercel
   - Add environment variables
   - Deploy!

---

## 📋 Environment Variables Checklist

### Bot (.env)
- [ ] `DISCORD_BOT_TOKEN`
- [ ] `API_PORT` (default: 8000)
- [ ] `ALLOWED_ORIGINS` (your dashboard URL)

### Dashboard (.env.local or Vercel)
- [ ] `NEXTAUTH_URL` (your Vercel URL)
- [ ] `NEXTAUTH_SECRET` (generate with `openssl rand -base64 32`)
- [ ] `DISCORD_CLIENT_ID`
- [ ] `DISCORD_CLIENT_SECRET`
- [ ] `DISCORD_BOT_TOKEN`
- [ ] `BOT_API_URL` (your bot's API URL)

---

## 📝 Discord Developer Portal Setup

1. Go to https://discord.com/developers/applications
2. Select your application
3. **OAuth2** → Add redirect URL:
   ```
   https://your-dashboard.vercel.app/api/auth/callback/discord
   ```
4. Save changes

---

## ✅ Verification Steps

1. Bot is running and connected to Discord
2. API is accessible: `curl https://your-bot-url.com/`
3. Dashboard loads and you can log in
4. Server stats display correctly

---

## 🆘 Need Help?

See full deployment guide: [DEPLOYMENT.md](DEPLOYMENT.md)

---

**All services are FREE! 🎉**
- Bot: WispByte (or any free host)
- Dashboard: Vercel
- Database: SQLite (included)
