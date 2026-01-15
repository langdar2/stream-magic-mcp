import asyncio
from streammagic_mcp.discovery import discover_media_servers

async def test():
    print("Scanning...")
    servers = await discover_media_servers(timeout=5)
    print(f"Found {len(servers)} servers.")
    for s in servers:
        print(f" - {s['name']} at {s['location']}")

if __name__ == "__main__":
    asyncio.run(test())
