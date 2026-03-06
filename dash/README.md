# Miku Dashboard

A modern, responsive web dashboard for the Miku Discord Leveling Bot built with **Next.js 14**, **React 18**, and **TypeScript**.

![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square&logo=next.js)
![React](https://img.shields.io/badge/React-18-blue?style=flat-square&logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-5.3-blue?style=flat-square&logo=typescript)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-38bdf8?style=flat-square&logo=tailwindcss)

## Features

✨ **Modern UI/UX**
- Beautiful Discord-themed design with Tailwind CSS
- Responsive layout for mobile, tablet, and desktop
- Smooth animations and transitions
- Custom scrollbars and loading states

🔐 **Discord OAuth2 Authentication**
- Secure login with Discord
- Server-side session management with NextAuth.js
- Access token handling for Discord API calls

📊 **Comprehensive Statistics**
- Real-time server stats and analytics
- Interactive leaderboards with pagination
- User rank cards and progress tracking
- XP distribution charts (coming soon)

🎮 **Server Management**
- Multi-server support
- View and manage all servers where you're admin
- One-click bot invitation for new servers
- Per-server customization options

⚡ **Performance Optimized**
- Server-side rendering (SSR)
- Static generation where possible
- SWR for efficient data fetching
- Image optimization with Next.js Image

## Tech Stack

### Frontend
- **Framework**: Next.js 14 (App Router)
- **UI Library**: React 18
- **Language**: TypeScript 5.3
- **Styling**: Tailwind CSS 3.4
- **State Management**: SWR for remote data
- **Icons**: React Icons

### Authentication
- **NextAuth.js 4**: Discord OAuth2 provider

### API Integration
- **Axios**: HTTP client for API calls
- **SWR**: Data fetching and caching

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn
- Discord Application with OAuth2 configured
- Miku bot running with API endpoint

### Installation

1. **Navigate to the dashboard folder**
   ```bash
   cd dash
   ```

2. **Install dependencies**
   ```bash
   npm install
   # or
   yarn install
   ```

3. **Set up environment variables**
   
   Copy `.env.example` to `.env.local`:
   ```bash
   cp .env.example .env.local
   ```

   Fill in your Discord OAuth2 credentials:
   ```env
   # Discord OAuth2
   NEXTAUTH_URL=http://localhost:3000
   NEXTAUTH_SECRET=your_nextauth_secret_here
   
   DISCORD_CLIENT_ID=your_discord_client_id
   DISCORD_CLIENT_SECRET=your_discord_client_secret
   
   # Backend API
   API_URL=http://localhost:8000
   
   # Discord Bot Token (if needed)
   DISCORD_BOT_TOKEN=your_bot_token_here
   ```

### Discord Application Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select existing one
3. Navigate to **OAuth2** → **General**
4. Add redirect URL: `http://localhost:3000/api/auth/callback/discord`
5. Copy **Client ID** and **Client Secret**
6. Save the credentials in your `.env.local` file

### Running the Development Server

```bash
npm run dev
# or
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Building for Production

```bash
npm run build
npm start
# or
yarn build
yarn start
```

## Project Structure

```
dash/
├── public/                 # Static assets
├── src/
│   ├── components/        # React components
│   │   ├── Navbar.tsx
│   │   ├── ServerCard.tsx
│   │   ├── StatsCard.tsx
│   │   ├── LeaderboardTable.tsx
│   │   ├── StatsOverview.tsx
│   │   └── LoadingSpinner.tsx
│   ├── pages/            # Next.js pages
│   │   ├── api/         # API routes
│   │   │   ├── auth/   # NextAuth endpoints
│   │   │   ├── guilds.ts
│   │   │   └── server/
│   │   ├── server/      # Dynamic server pages
│   │   ├── _app.tsx
│   │   ├── _document.tsx
│   │   ├── index.tsx    # Landing page
│   │   └── dashboard.tsx
│   ├── lib/             # Utilities and API client
│   │   ├── api.ts
│   │   └── utils.ts
│   ├── styles/          # Global styles
│   │   └── globals.css
│   └── types/           # TypeScript definitions
│       ├── index.ts
│       └── next-auth.d.ts
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
└── next.config.js
```

## Features Roadmap

### ✅ Completed
- [x] Discord OAuth2 authentication
- [x] Server list and management
- [x] Basic statistics dashboard
- [x] Leaderboard with pagination
- [x] Responsive design

### 🚧 In Progress
- [ ] Charts and graphs (Chart.js integration)
- [ ] Real-time data updates
- [ ] Server settings management

### 📋 Planned
- [ ] User profile pages
- [ ] Custom rank card designer
- [ ] Role rewards configuration
- [ ] XP multiplier settings
- [ ] Level-up announcement customization
- [ ] Export data functionality
- [ ] Dark/Light theme toggle
- [ ] Multi-language support

## API Integration

The dashboard communicates with the Miku bot's API endpoints. You'll need to implement these endpoints in your bot:

### Required Endpoints

```
GET  /api/server/:serverId/stats
GET  /api/server/:serverId/leaderboard?page=1
GET  /api/user/:userId?guild=:guildId
POST /api/admin/setlevel
POST /api/admin/addxp
POST /api/admin/resetlevel
```

See `src/lib/api.ts` for the complete API client implementation.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guidelines.

## Styling Guide

This project uses **Tailwind CSS** with a custom Discord theme:

```css
--discord-dark: #2F3136
--discord-gray: #36393F
--discord-light: #40444B
--discord-blue: #5865F2
--discord-green: #57F287
--discord-red: #ED4245
```

Use these classes for consistency:
- `bg-discord-dark`, `bg-discord-gray`, `bg-discord-light`
- `text-discord-blue`, `text-discord-green`, `text-discord-red`

## Performance Tips

1. **Image Optimization**: Always use Next.js `<Image>` component
2. **Data Fetching**: Use SWR for automatic caching and revalidation
3. **Code Splitting**: Components are automatically code-split by Next.js
4. **Bundle Analysis**: Run `npm run build` and check bundle sizes

## Troubleshooting

### OAuth Error: "Redirect URI Mismatch"
- Ensure redirect URI in Discord Developer Portal matches exactly
- Check `NEXTAUTH_URL` in `.env.local`

### API Connection Failed
- Verify `API_URL` is correct in `.env.local`
- Ensure the bot's API server is running
- Check CORS settings on the bot API

### Build Errors
- Clear `.next` folder and rebuild: `rm -rf .next && npm run build`
- Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Support

- 📖 [Documentation](https://github.com/TheCodeVerseHub/Miku)
- 🐛 [Report a Bug](https://github.com/TheCodeVerseHub/Miku/issues)
- 💡 [Request a Feature](https://github.com/TheCodeVerseHub/Miku/issues)

---

Built with ❤️ by TheCodeVerseHub
