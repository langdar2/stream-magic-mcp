import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from streammagic_mcp.discovery import discover_media_servers

async def main():
    print("Running discover_media_servers...")
    try:
        servers = await discover_media_servers(timeout=2)
        print(f"Result: {servers}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
