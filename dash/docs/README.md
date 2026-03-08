# Dashboard Documentation

This folder contains all documentation specific to the Miku Dashboard (Next.js web interface).

## Overview

The Miku Dashboard is a Next.js web application that provides a user-friendly interface for managing the Miku Discord leveling bot.

## Documentation Files

### Setup & Deployment
- [SETUP.md](./SETUP.md) - Complete dashboard setup instructions
- [QUICK_DEPLOY.md](./QUICK_DEPLOY.md) - Quick deployment guide for Vercel

### Technical Documentation
- [API_INTEGRATION.md](./API_INTEGRATION.md) - API integration guide
- [DATA_INTEGRATION.md](./DATA_INTEGRATION.md) - Data flow and integration
- [FILE_STRUCTURE.md](./FILE_STRUCTURE.md) - Dashboard file structure overview

## Main Dashboard README

The main dashboard documentation is located at:
- [../README.md](../README.md) - Dashboard overview and quick start

## Quick Links

### For Development
1. Read [SETUP.md](./SETUP.md) for local development setup
2. Review [FILE_STRUCTURE.md](./FILE_STRUCTURE.md) to understand the codebase
3. Check [API_INTEGRATION.md](./API_INTEGRATION.md) for API usage

### For Deployment
1. Follow [QUICK_DEPLOY.md](./QUICK_DEPLOY.md) for Vercel deployment
2. Configure environment variables as described in [SETUP.md](./SETUP.md)

### For Understanding Data Flow
1. Read [DATA_INTEGRATION.md](./DATA_INTEGRATION.md)
2. Review [API_INTEGRATION.md](./API_INTEGRATION.md)

## Technology Stack

- **Framework**: Next.js 14
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Authentication**: NextAuth.js (Discord OAuth2)
- **Data Fetching**: SWR
- **API Client**: Axios
- **Charts**: Chart.js + react-chartjs-2

## Key Features

### Authentication
- Discord OAuth2 integration
- Session management with NextAuth.js
- Secure token handling

### Server Management
- View server statistics
- Configure leveling settings
- Manage role rewards
- Set level-up announcement channels

### Data Visualization
- Real-time leaderboards
- Server statistics overview
- User progress tracking
- Role reward display

## Development

### Prerequisites
- Node.js 18+
- npm or yarn
- Discord application credentials
- Bot API endpoint

### Environment Variables
See [SETUP.md](./SETUP.md) for required environment variables.

### Local Development
```bash
cd dash
npm install
npm run dev
```

Visit `http://localhost:3000`

## Deployment

### Vercel (Recommended)
See [QUICK_DEPLOY.md](./QUICK_DEPLOY.md) for step-by-step instructions.

### Other Platforms
The dashboard can be deployed to any platform supporting Next.js:
- Netlify
- Railway
- Self-hosted with Docker

## API Integration

The dashboard communicates with:
1. **Bot API**: For leveling data and settings
2. **Discord API**: For authentication and guild information

See [API_INTEGRATION.md](./API_INTEGRATION.md) for details.

## Architecture

```
User Browser
    ↓
Next.js Dashboard (Vercel)
    ↓
Discord OAuth2
    ↓
Bot API (Render)
    ↓
PostgreSQL Database (Neon)
```

## Support

For dashboard-specific issues:
1. Check this documentation
2. Review [main documentation](../../docs/README.md)
3. Create a GitHub issue

## Contributing

See the main [CONTRIBUTING.md](../../CONTRIBUTING.md) guide.

---

*Last updated: March 8, 2026*
