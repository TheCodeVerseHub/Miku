# Miku Dashboard - Complete File Structure

This document provides a complete overview of all files in the dashboard.

## 📁 Root Level

```
dash/
├── .env.example              # Environment variables template
├── .eslintrc.json           # ESLint configuration
├── .gitignore               # Git ignore rules
├── .prettierrc              # Prettier code formatter config
├── .prettierignore          # Prettier ignore rules
├── next.config.js           # Next.js configuration
├── package.json             # NPM dependencies and scripts
├── postcss.config.js        # PostCSS configuration
├── tailwind.config.js       # Tailwind CSS configuration
├── tsconfig.json            # TypeScript configuration
├── README.md                # Main documentation
├── SETUP.md                 # Detailed setup guide
└── API_INTEGRATION.md       # API integration guide
```

## 📁 Public Assets

```
public/
├── index.html               # Fallback HTML page
└── favicon.svg              # Site favicon
```

## 📁 Source Code

### Main App Files

```
src/
├── pages/
│   ├── _app.tsx            # Next.js app wrapper (session provider)
│   ├── _document.tsx       # HTML document structure
│   ├── index.tsx           # Landing/home page
│   ├── dashboard.tsx       # Main dashboard (server list)
│   └── server/
│       └── [serverId].tsx  # Dynamic server stats page
```

### API Routes

```
src/pages/api/
├── auth/
│   └── [...nextauth].ts    # NextAuth.js Discord OAuth
├── guilds.ts               # Get user's Discord servers
└── server/
    └── [serverId]/
        ├── stats.ts        # Server statistics endpoint
        └── leaderboard.ts  # Server leaderboard endpoint
```

### Components

```
src/components/
├── Navbar.tsx              # Top navigation bar
├── ServerCard.tsx          # Server display card
├── StatsCard.tsx           # Statistics display card
├── StatsOverview.tsx       # Server stats overview grid
├── LeaderboardTable.tsx    # Leaderboard with pagination
└── LoadingSpinner.tsx      # Loading state component
```

### Utilities & Libraries

```
src/lib/
├── api.ts                  # Axios API client & endpoints
└── utils.ts                # Utility functions (XP calculations, etc.)
```

### Styles

```
src/styles/
└── globals.css             # Global CSS and Tailwind imports
```

### Type Definitions

```
src/types/
├── index.ts                # Main TypeScript interfaces
└── next-auth.d.ts          # NextAuth.js type extensions
```

## 📁 IDE Configuration

```
.vscode/
├── extensions.json         # Recommended VS Code extensions
└── settings.json          # VS Code workspace settings
```

## 🗂️ Auto-Generated (Not in Git)

```
.next/                      # Next.js build output
node_modules/              # NPM packages
.env.local                 # Local environment variables (not committed)
```

## 📄 File Purposes

### Configuration Files

| File | Purpose |
|------|---------|
| `next.config.js` | Next.js framework configuration |
| `tsconfig.json` | TypeScript compiler options |
| `tailwind.config.js` | Tailwind CSS theme and plugins |
| `postcss.config.js` | PostCSS plugins (Tailwind) |
| `.eslintrc.json` | Code linting rules |
| `.prettierrc` | Code formatting rules |

### App Pages

| File | Route | Description |
|------|-------|-------------|
| `pages/index.tsx` | `/` | Landing page with features |
| `pages/dashboard.tsx` | `/dashboard` | Server selection dashboard |
| `pages/server/[serverId].tsx` | `/server/:id` | Server stats & leaderboard |

### API Endpoints

| File | Endpoint | Purpose |
|------|----------|---------|
| `api/auth/[...nextauth].ts` | `/api/auth/*` | Discord OAuth2 |
| `api/guilds.ts` | `/api/guilds` | User's Discord servers |
| `api/server/[serverId]/stats.ts` | `/api/server/:id/stats` | Server statistics |
| `api/server/[serverId]/leaderboard.ts` | `/api/server/:id/leaderboard` | Server leaderboard |

## 📦 Dependencies

### Production Dependencies

```json
{
  "next": "^14.1.0",              // React framework
  "react": "^18.2.0",             // UI library
  "react-dom": "^18.2.0",         // React DOM renderer
  "axios": "^1.6.7",              // HTTP client
  "next-auth": "^4.24.6",         // Authentication
  "swr": "^2.2.5",                // Data fetching
  "chart.js": "^4.4.1",           // Charts (future)
  "react-chartjs-2": "^5.2.0",    // React charts
  "react-icons": "^5.0.1"         // Icon library
}
```

### Development Dependencies

```json
{
  "typescript": "^5.3.3",
  "tailwindcss": "^3.4.1",
  "autoprefixer": "^10.4.17",
  "postcss": "^8.4.35",
  "eslint": "^8.57.0",
  "eslint-config-next": "^14.1.0"
}
```

## 🎨 Design System

### Colors (Discord Theme)

```css
--discord-dark:  #2F3136  (backgrounds)
--discord-gray:  #36393F  (cards)
--discord-light: #40444B  (borders, hover)
--discord-blue:  #5865F2  (primary actions)
--discord-green: #57F287  (success, online)
--discord-red:   #ED4245  (danger, delete)
```

### Typography

- Font: System fonts (-apple-system, BlinkMacSystemFont, Segoe UI)
- Headings: Bold, larger sizes
- Body: Regular weight, readable sizes

### Components Style Guide

- **Cards**: Rounded corners, discord-gray background
- **Buttons**: Rounded, colored backgrounds, hover effects
- **Tables**: Striped rows, hover highlights
- **Inputs**: Outlined, focus states

## 🚀 Scripts

```bash
npm run dev      # Start development server (port 3000)
npm run build    # Build for production
npm start        # Start production server
npm run lint     # Run ESLint
```

## 📊 Data Flow

```
User Browser
    ↓
Next.js Pages (SSR/CSR)
    ↓
API Routes (/api/*)
    ↓
Discord API / Bot API
    ↓
Bot Database (SQLite)
```

## 🔒 Security Layers

1. **NextAuth.js** - Secure Discord OAuth2
2. **Session Management** - Server-side sessions
3. **API Protection** - Session verification on API routes
4. **CORS** - Cross-origin protection
5. **Environment Variables** - Sensitive data protection

## 📱 Responsive Breakpoints

- **Mobile**: < 768px
- **Tablet**: 768px - 1024px
- **Desktop**: > 1024px

All components are responsive using Tailwind's breakpoint system.

## 🔄 State Management

- **Server State**: SWR (remote data fetching & caching)
- **Auth State**: NextAuth.js session
- **Local State**: React useState/useEffect

## 🎯 Performance Optimizations

1. **Image Optimization**: Next.js Image component
2. **Code Splitting**: Automatic route-based splitting
3. **Static Generation**: Where possible
4. **Data Caching**: SWR with revalidation
5. **Font Optimization**: System fonts

## 📚 Further Reading

- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [NextAuth.js](https://next-auth.js.org)
- [SWR](https://swr.vercel.app)

---

**Total Files**: ~35 files
**Total Lines**: ~3,000+ lines of code
**Technologies**: 10+ major libraries/frameworks
