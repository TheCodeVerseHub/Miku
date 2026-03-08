"""
Backward compatibility wrapper for api_start.py
This file has been moved to /scripts/api_start.py

This wrapper ensures existing deployments continue to work.
"""
import sys
import os

# Add the scripts directory to the path
scripts_dir = os.path.join(os.path.dirname(__file__), 'scripts')
sys.path.insert(0, scripts_dir)

# Import and run the actual api_start module
if __name__ == "__main__":
    from scripts.api_start import main
    main()
