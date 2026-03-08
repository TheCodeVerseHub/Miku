# Scripts

Utility scripts for Miku Bot maintenance and operations.

## Available Scripts

### `fix_levels.py`
**Purpose**: Recalculate and fix inconsistent user levels in the database.

Fixes user levels that don't match their XP values. This is useful after:
- Changing the XP formula
- Database migrations
- Manual XP adjustments
- Importing data from other bots

**Usage**:
```bash
cd /path/to/Miku
python scripts/fix_levels.py
```

The script will:
1. Connect to your database using `DATABASE_URL` from `.env`
2. Analyze all user records for level inconsistencies
3. Show a preview of corrections
4. Ask for confirmation before applying changes
5. Update incorrect levels
6. Verify all corrections

**XP Formula Used**:
```python
# Per level: 5 * (level²) + (50 * level) + 100
# Cumulative XP for level N = sum of all previous levels
```

**Safety Features**:
- Requires explicit `yes` confirmation
- Shows preview of changes
- Verifies corrections after applying
- No data loss (only level field is updated)

---

### `migrate_to_postgres.py`
**Purpose**: Migrate data from SQLite to PostgreSQL.

Converts your local SQLite database to PostgreSQL for production deployment.

**Usage**:
```bash
python scripts/migrate_to_postgres.py
```

**Prerequisites**:
- SQLite database file: `data/miku.db`
- PostgreSQL `DATABASE_URL` in environment variables

---

### `api_start.py`
**Purpose**: Start only the API server (no Discord bot).

Useful for:
- Render.com deployment (API-only service)
- Testing API endpoints separately
- Running API on different server than bot

**Usage**:
```bash
python scripts/api_start.py
```

**Environment Variables**:
- `PORT`: API server port (default: 8000)
- `DATABASE_URL`: PostgreSQL connection string

---

### `start_all.py`
**Purpose**: Start both Discord bot and API server together.

Runs both services in parallel using multiprocessing.

**Usage**:
```bash
python scripts/start_all.py
```

**Environment Variables**:
- All Discord bot variables (see main README.md)
- `API_PORT`: API server port (default: 8000)
- `DATABASE_URL`: PostgreSQL connection string

**Behavior**:
- API runs in background process
- Bot runs in foreground
- Ctrl+C stops both services
- Automatic cleanup on exit

---

## Development Scripts

### Creating New Scripts

When adding new maintenance scripts:

1. **Name**: Use descriptive names with underscores: `action_target.py`
2. **Location**: Place in `/scripts` folder
3. **Documentation**: Add to this README with:
   - Purpose
   - Usage instructions
   - Prerequisites
   - Environment variables

4. **Safety**: For destructive operations:
   - Show preview of changes
   - Require confirmation
   - Provide dry-run mode
   - Log all actions

5. **Error Handling**:
   - Catch and display clear errors
   - Provide helpful error messages
   - Include traceback for debugging

### Script Template

```python
"""
Brief description of what this script does.

Longer explanation if needed.
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    """Main script logic"""
    print("=" * 60)
    print("Miku Bot - Script Name")
    print("=" * 60)
    
    # Your code here
    
    print("✅ Complete!")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Troubleshooting

### "DATABASE_URL not found"
Make sure you have a `.env` file in the project root with:
```env
DATABASE_URL=postgresql://user:password@host:port/database
```

### "Module not found" errors
Install dependencies:
```bash
pip install -r requirements.txt
```

### "Permission denied"
Make scripts executable:
```bash
chmod +x scripts/*.py
```

### Database connection issues
- Check your `DATABASE_URL` is correct
- Verify database is accessible (ping host)
- Check firewall rules
- Ensure IP is whitelisted (for hosted databases)

---

## Best Practices

1. **Always backup** before running destructive scripts
2. **Test on development database** first
3. **Read script output** carefully before confirming
4. **Check logs** after running scripts
5. **Run during low-traffic** periods when possible

---

*For more information, see [main documentation](../docs/README.md)*
