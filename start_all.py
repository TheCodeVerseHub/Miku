"""
Backward compatibility wrapper for start_all.py
This file has been moved to /scripts/start_all.py

This wrapper ensures existing deployments continue to work.
"""
import sys
import os

# Add the scripts directory to the path
scripts_dir = os.path.join(os.path.dirname(__file__), 'scripts')
sys.path.insert(0, scripts_dir)

# Import and run the actual start_all module
if __name__ == "__main__":
    from scripts.start_all import main
    main()
