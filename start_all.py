"""
Start both Discord bot and API server concurrently
"""
import multiprocessing
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_bot():
    """Run the Discord bot"""
    print("Starting Discord bot...")
    import sys
    import os
    # Add src to path so cogs can be imported
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    from bot import main
    asyncio.run(main())

def run_api():
    """Run the FastAPI server"""
    print("Starting API server...")
    import uvicorn
    from src.api_server import app
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

def main():
    """Start both processes"""
    print("=" * 50)
    print("Miku Bot - Starting Services")
    print("=" * 50)
    
    # Start API server in a separate process
    api_process = multiprocessing.Process(target=run_api, name="API-Server")
    api_process.daemon = True
    api_process.start()
    
    print("✓ API Server started")
    
    try:
        # Run bot in main process
        run_bot()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Cleanup
        api_process.terminate()
        api_process.join(timeout=5)
        if api_process.is_alive():
            api_process.kill()
        print("✓ All services stopped")

if __name__ == "__main__":
    main()
