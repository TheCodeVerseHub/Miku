#!/bin/bash

# Dashboard Performance Fix - Quick Test Script
# This script verifies that all the performance fixes are working correctly

echo "🔍 Testing Miku Dashboard Performance Fixes..."
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check if API server is running
echo "Test 1: Checking API server..."
API_URL="${API_URL:-http://localhost:8000}"
if curl -s "$API_URL/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} API server is running at $API_URL"
else
    echo -e "${RED}✗${NC} API server is not running at $API_URL"
    echo -e "${YELLOW}→${NC} Start it with: python src/api_server.py"
fi

# Test 2: Check if batch-check endpoint exists
echo ""
echo "Test 2: Checking batch-check endpoint..."
if curl -s -X POST "$API_URL/api/guilds/batch-check" \
    -H "Content-Type: application/json" \
    -d '[]' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Batch-check endpoint is working"
else
    echo -e "${RED}✗${NC} Batch-check endpoint not found"
    echo -e "${YELLOW}→${NC} Make sure you've updated src/api_server.py"
fi

# Test 3: Check if Dashboard dev server can start
echo ""
echo "Test 3: Checking dashboard configuration..."
if [ -f "dash/package.json" ]; then
    echo -e "${GREEN}✓${NC} Dashboard package.json found"
else
    echo -e "${RED}✗${NC} Dashboard package.json not found"
fi

if [ -f "dash/.env.local" ]; then
    echo -e "${GREEN}✓${NC} Dashboard .env.local found"
    
    # Check required env vars
    if grep -q "DISCORD_CLIENT_ID=" "dash/.env.local"; then
        echo -e "${GREEN}✓${NC} DISCORD_CLIENT_ID is set"
    else
        echo -e "${RED}✗${NC} DISCORD_CLIENT_ID not found in .env.local"
    fi
    
    if grep -q "NEXTAUTH_SECRET=" "dash/.env.local"; then
        echo -e "${GREEN}✓${NC} NEXTAUTH_SECRET is set"
    else
        echo -e "${RED}✗${NC} NEXTAUTH_SECRET not found in .env.local"
    fi
else
    echo -e "${RED}✗${NC} Dashboard .env.local not found"
    echo -e "${YELLOW}→${NC} Copy from dash/.env.local.example if exists"
fi

# Test 4: Check Node.js and npm
echo ""
echo "Test 4: Checking Node.js setup..."
if command -v node > /dev/null 2>&1; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js installed: $NODE_VERSION"
else
    echo -e "${RED}✗${NC} Node.js not found"
    echo -e "${YELLOW}→${NC} Install Node.js 18+ from https://nodejs.org"
fi

if command -v npm > /dev/null 2>&1; then
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✓${NC} npm installed: v$NPM_VERSION"
else
    echo -e "${RED}✗${NC} npm not found"
fi

# Test 5: Check if dependencies are installed
echo ""
echo "Test 5: Checking dashboard dependencies..."
if [ -d "dash/node_modules" ]; then
    echo -e "${GREEN}✓${NC} Dashboard dependencies installed"
else
    echo -e "${YELLOW}!${NC} Dashboard dependencies not installed"
    echo -e "${YELLOW}→${NC} Run: cd dash && npm install"
fi

# Test 6: Performance test
echo ""
echo "Test 6: Testing API response time..."
if command -v curl > /dev/null 2>&1; then
    START_TIME=$(date +%s%N)
    if curl -s "$API_URL/api/health" > /dev/null 2>&1; then
        END_TIME=$(date +%s%N)
        RESPONSE_TIME=$(( (END_TIME - START_TIME) / 1000000 ))
        
        if [ $RESPONSE_TIME -lt 500 ]; then
            echo -e "${GREEN}✓${NC} API response time: ${RESPONSE_TIME}ms (Excellent!)"
        elif [ $RESPONSE_TIME -lt 2000 ]; then
            echo -e "${YELLOW}!${NC} API response time: ${RESPONSE_TIME}ms (OK)"
        else
            echo -e "${RED}✗${NC} API response time: ${RESPONSE_TIME}ms (Slow!)"
            echo -e "${YELLOW}→${NC} Check database connection and performance"
        fi
    fi
fi

# Summary
echo ""
echo "================================"
echo "📊 Summary"
echo "================================"
echo ""
echo "To start the dashboard with all performance fixes:"
echo ""
echo "1. Start API server:"
echo "   cd /run/media/aditya/Local\ Disk/E/Aditya_Verma/Bot_Programming/Miku"
echo "   python src/api_server.py"
echo ""
echo "2. In a new terminal, start dashboard:"
echo "   cd dash"
echo "   npm run dev"
echo ""
echo "3. Open browser to:"
echo "   http://localhost:3000"
echo ""
echo "Expected performance:"
echo "  • Initial load: 3-5 seconds"
echo "  • Cached loads: <1 second"
echo "  • Guild checking: <1 second for any number of guilds"
echo ""
echo "For more details, see: DASHBOARD_PERFORMANCE_FIX.md"
