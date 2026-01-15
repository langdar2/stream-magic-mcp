import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import html
import json
from dataclasses import asdict
from streammagic_mcp.dlna import DlnaClient

async def test_filtering(location, query):
    client = DlnaClient(location)
    await client.initialize()
    
    # Simulate the new server tool logic
    clean_query = query.replace('"', '') 
    criteria = f'dc:title contains "{clean_query}"'
    
    print(f"\n=== Testing Workaround (500 limit + Filter) for '{query}' ===")
    try:
        # Request 500 items
        raw_items = await client.search(search_criteria=criteria, count=500)
        print(f"Server returned {len(raw_items)} raw items.")
        
        # Manual Filtering
        q = query.lower()
        filtered = []
        for item in raw_items:
            match = q in item.title.lower() or \
                    (item.artist and q in item.artist.lower()) or \
                    (item.album and q in item.album.lower())
            if match:
                filtered.append(item)
        
        print(f"Filter found {len(filtered)} items.")
        for item in filtered[:10]:
            print(f" - [{item.upnp_class}] {item.title} (Artist: {item.artist})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    loc = "http://192.168.0.2:8096/dlna/2db3d90f-d0c1-4602-a388-9d2a28ac5afb/description.xml"
    asyncio.run(test_filtering(loc, "onkelz"))
