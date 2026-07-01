# Miku Dashboard — Setup Guide

This guide walks you through every step needed to get the web dashboard running.

---

## 1. Prerequisites

- The Miku bot must already be running (or at least have its database set up).
- You need a **Discord Application** with OAuth2 enabled.
- The bot's PostgreSQL database must be accessible from your machine.

---

## 2. Discord OAuth2 — Create Credentials

The dashboard logs you in via Discord. You need to create an OAuth2 app.

1. Go to https://discord.com/developers/applications
2. Click on your bot's application (or create a new one).
3. In the left sidebar, click **OAuth2 → General**.

   Here you will find:

   - **CLIENT ID** — a long number (e.g. `123456789012345678`)
   - **CLIENT SECRET** — click **Reset Secret** to reveal it, then **copy it now** (you won't see it again)

4. In the same page, under **Redirects**, click **Add Redirect** and paste:

   ```
   http://localhost:8000/auth/callback
   ```

   Then click **Save**.

---

## 3. Configure `.env`

Open the `.env` file in the **project root** (`Miku-Main/.env`) and add these lines:

```env
# === Dashboard Configuration ===

DASHBOARD_CLIENT_ID=123456789012345678
DASHBOARD_CLIENT_SECRET=AbCdEfGhIjKlMnOpQrStUvWxYz
DASHBOARD_REDIRECT_URI=http://localhost:8000/auth/callback
DASHBOARD_SESSION_SECRET=make-up-a-random-string-here-at-least-32-chars
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8000
```

Replace the values:

| Variable | Where to find it |
|----------|------------------|
| `DASHBOARD_CLIENT_ID` | Discord Developer Portal → OAuth2 → General → Client ID |
| `DASHBOARD_CLIENT_SECRET` | Discord Developer Portal → OAuth2 → General → Client Secret (click Reset Secret) |
| `DASHBOARD_SESSION_SECRET` | Make up a random string (used to sign session cookies) |

> `DATABASE_URL` should already be in your `.env` from when you set up the bot. The dashboard reuses it.

---

## 4. Install Dependencies

From the project root (`Miku-Main/`), run:

```bash
.venv/bin/pip install -r dashboard/requirements.txt
```

This installs FastAPI, uvicorn, httpx, jinja2, itsdangerous, and their dependencies.

---

## 5. Run the Dashboard

From the project root (`Miku-Main/`):

```bash
.venv/bin/uvicorn dashboard.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see output like:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     (Press CTRL+C to quit)
```

---

## 6. Open the Dashboard

Open your browser and go to:

```
http://localhost:8000
```

Click **Login with Discord** — you'll be redirected to Discord to authorize. After that, you'll see a list of servers where you have **Administrator** or **Manage Server** permission.

Click a server to start configuring Miku's leveling system.

---

## 7. Quick Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot connect to database` | Make sure `DATABASE_URL` is correct in `.env` and the PostgreSQL server is running. |
| `401 Not Authenticated` on login | Check that the **Redirect URI** in Discord Developer Portal matches `DASHBOARD_REDIRECT_URI` in `.env` **exactly**. |
| `403 Missing permissions` | You need **Administrator** or **Manage Server** permission in the Discord server. |
| No servers showing | The bot must be in at least one server where you have admin permissions. |
| Slash commands not working | Not related to the dashboard — the dashboard is a separate web app. |
| Module not found errors | Make sure you ran the pip install command from step 4. |

---

## 8. How It Works (Architecture)

```
Browser  ──HTTP──>  FastAPI (dashboard/backend/main.py)
                        │
                        ├── Discord OAuth2 (login/auth)
                        ├── PostgreSQL (same database as the bot)
                        └── Jinja2 Templates (server-rendered HTML)
```

- The dashboard is a **completely separate process** from the Discord bot.
- They share the **same PostgreSQL database**.
- The dashboard **does not modify any bot source code**.
- All changes made in the dashboard are visible to the bot immediately (and vice versa).
