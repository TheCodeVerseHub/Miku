"""
Migration script to transfer data from SQLite to PostgreSQL
Run this script once to migrate your existing leveling data
"""
import asyncio
import aiosqlite
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
SQLITE_DB = Path(__file__).parent / "data" / "leveling.db"
POSTGRES_URL = os.getenv("DATABASE_URL")

async def migrate():
    """Migrate data from SQLite to PostgreSQL"""
    
    if not SQLITE_DB.exists():
        print("❌ SQLite database not found. Nothing to migrate.")
        return
    
    if not POSTGRES_URL:
        print("❌ DATABASE_URL environment variable not set!")
        print("Please set DATABASE_URL in your .env file")
        return
    
    print("🔄 Starting migration from SQLite to PostgreSQL...")
    print(f"   SQLite: {SQLITE_DB}")
    print(f"   PostgreSQL: {POSTGRES_URL[:30]}...")
    print()
    
    # Connect to both databases
    sqlite_conn = await aiosqlite.connect(SQLITE_DB)
    sqlite_conn.row_factory = aiosqlite.Row
    
    pg_pool = await asyncpg.create_pool(POSTGRES_URL)
    
    try:
        async with pg_pool.acquire() as pg_conn:
            # Create tables in PostgreSQL
            print("📋 Creating tables in PostgreSQL...")
            await pg_conn.execute('''
                CREATE TABLE IF NOT EXISTS user_levels (
                    user_id BIGINT,
                    guild_id BIGINT,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 0,
                    messages INTEGER DEFAULT 0,
                    last_message_time DOUBLE PRECISION DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            
            await pg_conn.execute('''
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id BIGINT PRIMARY KEY,
                    levelup_channel_id BIGINT,
                    updated_at DOUBLE PRECISION DEFAULT 0
                )
            ''')
            
            await pg_conn.execute('''
                CREATE TABLE IF NOT EXISTS role_rewards (
                    guild_id BIGINT,
                    level INTEGER,
                    role_id BIGINT,
                    PRIMARY KEY (guild_id, level)
                )
            ''')
            print("✅ Tables created\n")
            
            # Migrate user_levels
            print("👥 Migrating user levels...")
            async with sqlite_conn.execute('SELECT * FROM user_levels') as cursor:
                rows = await cursor.fetchall()
                count = 0
                for row in rows:
                    # Handle optional columns safely
                    messages = row['messages'] if 'messages' in row.keys() else 0
                    last_message_time = row['last_message_time'] if 'last_message_time' in row.keys() else 0
                    
                    await pg_conn.execute('''
                        INSERT INTO user_levels (user_id, guild_id, xp, level, messages, last_message_time)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (user_id, guild_id) DO UPDATE SET
                            xp = EXCLUDED.xp,
                            level = EXCLUDED.level,
                            messages = EXCLUDED.messages,
                            last_message_time = EXCLUDED.last_message_time
                    ''', row['user_id'], row['guild_id'], row['xp'], row['level'],
                         messages, last_message_time)
                    count += 1
                print(f"✅ Migrated {count} user level records\n")
            
            # Migrate guild_settings
            print("⚙️  Migrating guild settings...")
            async with sqlite_conn.execute('SELECT * FROM guild_settings') as cursor:
                rows = await cursor.fetchall()
                count = 0
                for row in rows:
                    # Handle optional columns safely
                    levelup_channel_id = row['levelup_channel_id'] if 'levelup_channel_id' in row.keys() else None
                    updated_at = row['updated_at'] if 'updated_at' in row.keys() else 0
                    
                    await pg_conn.execute('''
                        INSERT INTO guild_settings (guild_id, levelup_channel_id, updated_at)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (guild_id) DO UPDATE SET
                            levelup_channel_id = EXCLUDED.levelup_channel_id,
                            updated_at = EXCLUDED.updated_at
                    ''', row['guild_id'], levelup_channel_id, updated_at)
                    count += 1
                print(f"✅ Migrated {count} guild settings\n")
            
            # Migrate role_rewards
            print("🎖️  Migrating role rewards...")
            async with sqlite_conn.execute('SELECT * FROM role_rewards') as cursor:
                rows = await cursor.fetchall()
                count = 0
                for row in rows:
                    await pg_conn.execute('''
                        INSERT INTO role_rewards (guild_id, level, role_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (guild_id, level) DO UPDATE SET
                            role_id = EXCLUDED.role_id
                    ''', row['guild_id'], row['level'], row['role_id'])
                    count += 1
                print(f"✅ Migrated {count} role rewards\n")
            
            print("🎉 Migration completed successfully!")
            print("\n📌 Next steps:")
            print("1. Verify the data in your PostgreSQL database")
            print("2. Update your .env file with DATABASE_URL")
            print("3. Deploy your bot with the new PostgreSQL configuration")
            print("4. (Optional) Keep the SQLite database as a backup")
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await sqlite_conn.close()
        await pg_pool.close()

if __name__ == "__main__":
    print("=" * 60)
    print("  SQLite → PostgreSQL Migration Tool")
    print("=" * 60)
    print()
    asyncio.run(migrate())
