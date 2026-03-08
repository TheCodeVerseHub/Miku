# PostgreSQL Setup Guide

## Getting a Free PostgreSQL Database

### Option 1: Neon (Recommended - Easiest)

1. Go to [neon.tech](https://neon.tech)
2. Sign up with GitHub
3. Create a new project
4. Copy the connection string (looks like: `postgresql://user:password@host/database`)

### Option 2: Supabase

1. Go to [supabase.com](https://supabase.com)
2. Sign up and create a new project
3. Go to Settings → Database
4. Copy the Connection String (URI mode)

### Option 3: Render PostgreSQL

1. Go to your Render dashboard
2. New → PostgreSQL
3. Select Free tier
4. Copy the External Database URL

## Configuration

1. Get your PostgreSQL connection string
2. Add to `.env`:
   ```
   DATABASE_URL=postgresql://user:password@host:port/database
   ```

3. Add to WispByte environment variables:
   ```
   DATABASE_URL=your_postgres_url
   ```

4. Add to Render API service environment variables:
   ```
   DATABASE_URL=your_postgres_url
   ```

## Migration

Run the migration script to move data from SQLite to PostgreSQL:

```bash
python migrate_to_postgres.py
```

This will:
- Create tables in PostgreSQL
- Copy all data from SQLite
- Preserve all user levels and settings
