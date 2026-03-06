@echo off
REM Miku Dashboard Quick Setup Script for Windows
REM This script helps you set up the dashboard quickly

echo.
echo ================================
echo   Miku Dashboard Setup
echo ================================
echo.

REM Check if Node.js is installed
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed!
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Node.js detected: 
node -v
echo.

REM Navigate to dashboard directory
cd /d "%~dp0"

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
    echo [OK] Dependencies installed
) else (
    echo [OK] Dependencies already installed
)
echo.

REM Check if .env.local exists
if not exist ".env.local" (
    echo Creating environment file...
    copy .env.example .env.local >nul
    echo [OK] Created .env.local from template
    echo.
    echo [WARNING] IMPORTANT: You need to configure .env.local with your Discord credentials!
    echo.
    echo Please follow these steps:
    echo 1. Go to https://discord.com/developers/applications
    echo 2. Create a new application or select existing one
    echo 3. Navigate to OAuth2 - General
    echo 4. Add redirect: http://localhost:3000/api/auth/callback/discord
    echo 5. Copy your Client ID and Client Secret
    echo 6. Edit .env.local and add your credentials
    echo.
    pause
) else (
    echo [OK] Environment file exists (.env.local)
)
echo.

REM Check if .env.local is configured
findstr /C:"your_discord_client_id" .env.local >nul
if %ERRORLEVEL% EQU 0 (
    echo [WARNING] .env.local might not be configured properly
    echo Make sure to set DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET
) else (
    echo [OK] Discord credentials configured
)
echo.

echo Setup complete!
echo.
set /p START="Do you want to start the development server now? (Y/N): "

if /i "%START%"=="Y" (
    echo.
    echo Starting development server...
    echo Dashboard will be available at http://localhost:3000
    echo.
    echo Press Ctrl+C to stop the server
    echo.
    call npm run dev
) else (
    echo.
    echo To start the dashboard later, run:
    echo   cd dash
    echo   npm run dev
    echo.
    echo Then open http://localhost:3000 in your browser
    pause
)
