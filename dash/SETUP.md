# Miku Dashboard - Setup Guide

This guide will walk you through setting up the Miku bot dashboard from scratch.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Discord Application Setup](#discord-application-setup)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the Dashboard](#running-the-dashboard)
6. [Deployment](#deployment)

## Prerequisites

Before you begin, ensure you have:

- **Node.js** 18.x or higher ([Download](https://nodejs.org/))
- **npm** or **yarn** package manager
- A **Discord Application** (create one at [Discord Developer Portal](https://discord.com/developers/applications))
- The **Miku bot** set up and running

## Discord Application Setup

### Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Give it a name (e.g., "Miku Dashboard")
4. Click **"Create"**

### Step 2: Configure OAuth2

1. In your application, navigate to **OAuth2** → **General**
2. Under **"Redirects"**, add:
   - Development: `http://localhost:3000/api/auth/callback/discord`
   - Production: `https://yourdomain.com/api/auth/callback/discord`
3. Click **"Save Changes"**

### Step 3: Get Credentials

1. Still in **OAuth2** → **General**
2. Copy your **Client ID**
3. Click **"Reset Secret"** to generate a new **Client Secret**
4. Copy the **Client Secret** (save it securely!)

## Installation

### Step 1: Navigate to Dashboard Folder

```bash
cd /path/to/Miku/dash
```

### Step 2: Install Dependencies

Using npm:
```bash
npm install
```

Using yarn:
```bash
yarn install
```

This will install:
- Next.js 14
- React 18
- TypeScript
- Tailwind CSS
- NextAuth.js
- SWR
- Axios
- React Icons

## Configuration

### Step 1: Create Environment File

Copy the example environment file:

```bash
cp .env.example .env.local
```

### Step 2: Configure Environment Variables

Open `.env.local` and fill in your values:

```env
# NextAuth Configuration
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=generate_a_random_secret_here

# Discord OAuth2 Credentials
DISCORD_CLIENT_ID=your_client_id_from_step_3
DISCORD_CLIENT_SECRET=your_client_secret_from_step_3

# Backend API URL (your Python bot's API endpoint)
API_URL=http://localhost:8000

# Discord Bot Token (optional, if API needs it)
DISCORD_BOT_TOKEN=your_bot_token
```

### Step 3: Generate NextAuth Secret

Generate a secure random string for `NEXTAUTH_SECRET`:

```bash
openssl rand -base64 32
```

Or use this Node.js command:
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

## Running the Dashboard

### Development Mode

Start the development server with hot-reload:

```bash
npm run dev
# or
yarn dev
```

The dashboard will be available at [http://localhost:3000](http://localhost:3000)

### Production Build

Build the optimized production bundle:

```bash
npm run build
```

Start the production server:

```bash
npm start
```

## Deployment

### Option 1: Vercel (Recommended)

Vercel is the easiest way to deploy Next.js applications:

1. **Install Vercel CLI**
   ```bash
   npm install -g vercel
   ```

2. **Deploy**
   ```bash
   vercel
   ```

3. **Add Environment Variables**
   - Go to your project settings on Vercel
   - Add all variables from `.env.local`
   - Update `NEXTAUTH_URL` to your production URL

4. **Redeploy**
   ```bash
   vercel --prod
   ```

### Option 2: Docker

Create `Dockerfile` in the `dash` folder:

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
```

Build and run:
```bash
docker build -t miku-dashboard .
docker run -p 3000:3000 --env-file .env.local miku-dashboard
```

### Option 3: VPS/Cloud Server

1. **Install Node.js on your server**
   ```bash
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

2. **Clone and setup**
   ```bash
   git clone https://github.com/TheCodeVerseHub/Miku.git
   cd Miku/dash
   npm install
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env.local
   nano .env.local  # Edit with your values
   ```

4. **Build**
   ```bash
   npm run build
   ```

5. **Use PM2 for process management**
   ```bash
   npm install -g pm2
   pm2 start npm --name "miku-dashboard" -- start
   pm2 save
   pm2 startup
   ```

6. **Setup Nginx reverse proxy** (optional)
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://localhost:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

## Troubleshooting

### Port Already in Use

If port 3000 is taken, specify a different port:

```bash
PORT=3001 npm run dev
```

### OAuth Redirect URI Mismatch

Ensure the redirect URI in Discord Developer Portal **exactly matches** your `NEXTAUTH_URL`:
- Development: `http://localhost:3000/api/auth/callback/discord`
- Production: `https://yourdomain.com/api/auth/callback/discord`

### Cannot Connect to Bot API

1. Check if your bot's API server is running
2. Verify `API_URL` in `.env.local` is correct
3. Ensure there are no firewall issues
4. Check CORS settings on the bot API

### Build Fails

Clear cache and rebuild:
```bash
rm -rf .next node_modules
npm install
npm run build
```

## Next Steps

1. **Customize the design** - Edit components in `src/components/`
2. **Add new features** - Create new pages in `src/pages/`
3. **Connect to your bot API** - Update endpoints in `src/lib/api.ts`
4. **Add analytics** - Integrate Google Analytics or similar

## Support

Need help? 

- 📖 [Full Documentation](README.md)
- 🐛 [Report Issues](https://github.com/TheCodeVerseHub/Miku/issues)
- 💬 [Discussions](https://github.com/TheCodeVerseHub/Miku/discussions)

---

Happy coding! 🚀
