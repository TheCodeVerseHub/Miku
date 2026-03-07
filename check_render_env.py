#!/usr/bin/env python3
"""
Environment Variables Checker for Render Deployment
Run this script to verify all required environment variables are set correctly
"""

import os
import sys
from urllib.parse import urlparse

def check_env_var(name, required=True, check_value=None):
    """Check if an environment variable is set and optionally validate it"""
    value = os.getenv(name)
    
    if value is None:
        if required:
            print(f"❌ {name}: NOT SET (Required)")
            return False
        else:
            print(f"⚠️  {name}: Not set (Optional)")
            return True
    
    # Don't print sensitive values
    if 'SECRET' in name or 'TOKEN' in name or 'PASSWORD' in name:
        display_value = f"***{value[-4:]}" if len(value) > 4 else "***"
    else:
        display_value = value[:50] + "..." if len(value) > 50 else value
    
    if check_value and not check_value(value):
        print(f"❌ {name}: {display_value} (Invalid)")
        return False
    
    print(f"✅ {name}: {display_value}")
    return True

def check_database_url(url):
    """Validate PostgreSQL database URL format"""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ['postgresql', 'postgres'] and parsed.netloc
    except:
        return False

def check_cors_origins(origins):
    """Validate CORS origins format"""
    if origins == "*":
        return True
    origin_list = [o.strip() for o in origins.split(',')]
    return all(o.startswith('http://') or o.startswith('https://') for o in origin_list)

def main():
    print("=" * 60)
    print("🔍 Checking Environment Variables for Render Deployment")
    print("=" * 60)
    print()
    
    all_valid = True
    
    # Critical environment variables
    print("📊 Critical Variables:")
    all_valid &= check_env_var("DATABASE_URL", required=True, check_value=check_database_url)
    all_valid &= check_env_var("ALLOWED_ORIGINS", required=True, check_value=check_cors_origins)
    
    print()
    print("🔧 Optional Variables:")
    check_env_var("API_PORT", required=False)
    check_env_var("PORT", required=False)
    
    print()
    print("=" * 60)
    
    if all_valid:
        print("✅ All required environment variables are set correctly!")
        print()
        print("Next steps:")
        print("1. Deploy your service to Render")
        print("2. Test the health endpoint:")
        print("   curl https://your-service.onrender.com/api/health")
        print("3. Test the batch-check endpoint:")
        print("   curl -X POST https://your-service.onrender.com/api/guilds/batch-check \\")
        print("     -H 'Content-Type: application/json' -d '[]'")
        return 0
    else:
        print("❌ Some required environment variables are missing or invalid!")
        print()
        print("Required environment variables:")
        print()
        print("DATABASE_URL:")
        print("  - Get from Render PostgreSQL database (Internal Database URL)")
        print("  - Format: postgresql://user:password@host:port/database")
        print()
        print("ALLOWED_ORIGINS:")
        print("  - Your Vercel dashboard URL(s)")
        print("  - Format: https://your-dashboard.vercel.app")
        print("  - Multiple: https://app1.com,https://app2.com")
        print()
        print("Add these in Render Dashboard:")
        print("1. Go to your service")
        print("2. Click 'Environment' tab")
        print("3. Add each variable")
        print("4. Click 'Save Changes'")
        print("5. Service will redeploy automatically")
        return 1

if __name__ == "__main__":
    sys.exit(main())
