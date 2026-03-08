"""
Backward compatibility wrapper for api_start.py
This file has been moved to /scripts/api_start.py

This wrapper ensures existing deployments continue to work.
"""
import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the API server
from api_server import app
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting API server on port {port}...")
    print("NOTE: This file has moved to /scripts/api_start.py")
    uvicorn.run(app, host="0.0.0.0", port=port)
