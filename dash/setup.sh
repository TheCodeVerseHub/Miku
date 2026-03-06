#!/bin/bash

# Miku Dashboard Quick Setup Script
# This script helps you set up the dashboard quickly

set -e

echo "🚀 Miku Dashboard Setup"
echo "======================="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed!"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version must be 18 or higher (current: $(node -v))"
    exit 1
fi

echo "✅ Node.js $(node -v) detected"
echo ""

# Navigate to dashboard directory
cd "$(dirname "$0")"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi
echo ""

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo "⚙️  Creating environment file..."
    cp .env.example .env.local
    echo "✅ Created .env.local from template"
    echo ""
    echo "⚠️  IMPORTANT: You need to configure .env.local with your Discord credentials!"
    echo ""
    echo "Please follow these steps:"
    echo "1. Go to https://discord.com/developers/applications"
    echo "2. Create a new application or select existing one"
    echo "3. Navigate to OAuth2 → General"
    echo "4. Add redirect: http://localhost:3000/api/auth/callback/discord"
    echo "5. Copy your Client ID and Client Secret"
    echo "6. Edit .env.local and add your credentials"
    echo ""
    read -p "Press Enter when you have configured .env.local..."
else
    echo "✅ Environment file exists (.env.local)"
fi
echo ""

# Validate .env.local has required variables
if ! grep -q "DISCORD_CLIENT_ID=your_discord_client_id" .env.local; then
    echo "✅ Discord credentials configured"
else
    echo "⚠️  Warning: .env.local might not be configured properly"
    echo "Make sure to set DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET"
fi
echo ""

# Ask if user wants to start dev server
echo "🎯 Setup complete!"
echo ""
read -p "Do you want to start the development server now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Starting development server..."
    echo "Dashboard will be available at http://localhost:3000"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""
    npm run dev
else
    echo ""
    echo "To start the dashboard later, run:"
    echo "  cd dash"
    echo "  npm run dev"
    echo ""
    echo "Then open http://localhost:3000 in your browser"
fi
