import asyncio
import aiohttp
import sys
import os
import xml.etree.ElementTree as ET

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from streammagic_mcp.dlna import DlnaClient
from streammagic_mcp.discovery import discover_media_servers

async def debug_dlna(location=None):
    if not location:
        print("No URL provided. Scanning for Media Servers...")
        try:
            servers = await discover_media_servers(timeout=3)
            if not servers:
                print("No Media Servers found.")
                return
            
            print(f"Found {len(servers)} servers:")
            for i, s in enumerate(servers):
                print(f"{i+1}. {s['name']} ({s['host']}) - {s['location']}")
            
            # Pick first one or ask? For debug, pick first.
            location = servers[0]['location']
            print(f"\nAuto-selecting first server: {location}")
        except Exception as e:
            print(f"Discovery failed: {e}")
            return

    print(f"--- Debugging DLNA for {location} ---")
    
    # 1. Fetch XML manually
    print(f"Fetching description from {location}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(location, timeout=5) as resp:
                print(f"Status: {resp.status}")
                if resp.status != 200:
                    print("Failed to fetch.")
                    return
                xml_content = await resp.text()
                print(f"XML length: {len(xml_content)} bytes")
    except Exception as e:
        print(f"Fetch request failed: {e}")
        return

    # 2. Use DlnaClient initialize
    print("\nInitializing DlnaClient...")
    client = DlnaClient(location)
    try:
        await client.initialize()
        print(f"Friendly Name: {client._friendly_name}")
        print(f"Base URL: {client._base_url}")
        print(f"ContentDirectory URL: {client._content_directory_url}")
        print(f"AVTransport URL: {client._av_transport_url}")
        
        if not client._content_directory_url:
            print("ERROR: ContentDirectory URL not found. Parsing issue or unsupported device.")
            return

    except Exception as e:
        print(f"Initialization Exception: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Try Browse
    print("\nAttempting Browse(0)...")
    try:
        items = await client.browse("0")
        print(f"Success! Found {len(items)} items.")
        for item in items[:10]: # Print up to 10
            print(f"- [{item.id}] {item.title} ({'Container' if item.is_container else 'Item'})")
    except Exception as e:
        print(f"Browse Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    
    # Ensure source path is correct for imports if run from project root
    if "src" not in sys.path:
         sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
         
    asyncio.run(debug_dlna(url))
