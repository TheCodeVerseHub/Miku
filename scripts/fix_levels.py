"""
Fix inconsistent levels in database based on actual XP values.
This recalculates all user levels using the correct formula: 5 * (level²) + (50 * level) + 100

Run this after changing XP formulas to ensure database consistency.
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

def calculate_xp_for_level(level: int) -> int:
    """Calculate total XP needed for a specific level (cumulative)"""
    total_xp = 0
    for lvl in range(1, level + 1):
        total_xp += 5 * (lvl ** 2) + (50 * lvl) + 100
    return total_xp

def calculate_level_from_xp(xp: int) -> int:
    """Calculate level from total XP"""
    if xp < 0:
        return 0
    
    level = 0
    while True:
        xp_for_next = calculate_xp_for_level(level + 1)
        if xp < xp_for_next:
            break
        level += 1
        # Safety check to prevent infinite loops
        if level > 1000:
            break
    
    return level

async def fix_all_levels():
    """Connect to database and fix all user levels"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables")
        return
    
    print("=" * 60)
    print("Miku Bot - Level Fix Script")
    print("=" * 60)
    print(f"📊 Connecting to database...")
    
    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database\n")
        
        # Get all users
        print("📥 Fetching all user records...")
        users = await conn.fetch(
            "SELECT user_id, guild_id, xp, level FROM user_levels ORDER BY xp DESC"
        )
        
        total_users = len(users)
        print(f"Found {total_users} user records\n")
        
        if total_users == 0:
            print("No users found. Nothing to fix.")
            await conn.close()
            return
        
        # Analyze issues
        print("🔍 Analyzing level inconsistencies...")
        incorrect = 0
        corrections = []
        
        for user in users:
            user_id = user['user_id']
            guild_id = user['guild_id']
            current_xp = user['xp']
            current_level = user['level']
            correct_level = calculate_level_from_xp(current_xp)
            
            if current_level != correct_level:
                incorrect += 1
                corrections.append({
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'xp': current_xp,
                    'old_level': current_level,
                    'new_level': correct_level
                })
        
        print(f"Found {incorrect} users with incorrect levels")
        print(f"✅ {total_users - incorrect} users already have correct levels\n")
        
        if incorrect == 0:
            print("🎉 All levels are correct! No changes needed.")
            await conn.close()
            return
        
        # Show sample of corrections
        print("📋 Sample corrections (first 10):")
        print("-" * 60)
        for i, correction in enumerate(corrections[:10]):
            print(f"  User {correction['user_id'][:8]}... | {correction['xp']:,} XP | "
                  f"Level {correction['old_level']} → {correction['new_level']}")
        
        if len(corrections) > 10:
            print(f"  ... and {len(corrections) - 10} more")
        print()
        
        # Confirm before proceeding
        response = input(f"⚠️  Apply {incorrect} corrections? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ Aborted. No changes made.")
            await conn.close()
            return
        
        # Apply corrections
        print(f"\n🔧 Applying corrections...")
        updated = 0
        
        for correction in corrections:
            try:
                await conn.execute(
                    """UPDATE user_levels 
                       SET level = $1 
                       WHERE user_id = $2 AND guild_id = $3""",
                    correction['new_level'],
                    correction['user_id'],
                    correction['guild_id']
                )
                updated += 1
                if updated % 100 == 0:
                    print(f"  Progress: {updated}/{incorrect} updated...")
            except Exception as e:
                print(f"  ❌ Error updating user {correction['user_id']}: {e}")
        
        print(f"\n✅ Successfully updated {updated}/{incorrect} user levels")
        
        # Verify corrections
        print("\n🔍 Verifying corrections...")
        remaining_issues = 0
        
        for correction in corrections:
            check = await conn.fetchrow(
                "SELECT level FROM user_levels WHERE user_id = $1 AND guild_id = $2",
                correction['user_id'],
                correction['guild_id']
            )
            if check and check['level'] != correction['new_level']:
                remaining_issues += 1
        
        if remaining_issues == 0:
            print("✅ All corrections verified successfully!")
        else:
            print(f"⚠️  {remaining_issues} records may need manual review")
        
        await conn.close()
        print("\n" + "=" * 60)
        print("✨ Level fix complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point"""
    asyncio.run(fix_all_levels())

if __name__ == "__main__":
    main()
