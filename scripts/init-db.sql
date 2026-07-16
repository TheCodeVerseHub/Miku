-- Miku - PostgreSQL Initialization Script
-- This runs automatically on first container start.

-- Enable pgcrypto for gen_random_uuid() and other crypto functions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create schema (all tables are created by the bot at runtime)
-- This file exists to set up extensions and any future pre-requisites.

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE miku TO miku;
