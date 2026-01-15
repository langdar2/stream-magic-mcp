import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional, Dict

from mcp.server.fastmcp import FastMCP
from aiostreammagic import StreamMagicClient, StreamMagicError

# Initialize FastMCP server
mcp = FastMCP("streammagic")

# Configure logging
import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global client cache: host -> StreamMagicClient
_clients: Dict[str, StreamMagicClient] = {}

# DLNA Client cache: location -> DlnaClient
from streammagic_mcp.dlna import DlnaClient
_dlna_clients: Dict[str, DlnaClient] = {}

@asynccontextmanager
async def get_client(host: str):
    """
    Context manager to get a connected StreamMagicClient.
    Reuse existing connections if possible, otherwise create new ones.
    """
    if not host:
         # Fallback to env var if not provided
        host = os.environ.get("STREAMMAGIC_HOST")
    
    if not host:
        raise ValueError("Host must be provided or set in STREAMMAGIC_HOST environment variable")

    client = _clients.get(host)
    
    # If client doesn't exist or isn't connected, create/connect
    if not client:
        client = StreamMagicClient(host)
        try:
            await client.connect()
            _clients[host] = client
        except Exception as e:
            # If connection fails, ensure we don't keep a broken client in cache
            if host in _clients:
                del _clients[host]
            raise RuntimeError(f"Failed to connect to {host}: {str(e)}")
    
    # If client exists but disconnected (check logic depends on library)
    # aiostreammagic has .is_connected()
    if not client.is_connected():
         try:
            await client.connect()
         except Exception as e:
             if host in _clients:
                 del _clients[host]
             raise RuntimeError(f"Failed to reconnect to {host}: {str(e)}")

    try:
        yield client
    except Exception as e:
        raise e
    finally:
        # We don't disconnect here to allow reuse. 
        # In a real long-running server, we might want to cleanup idle connections.
        pass

@mcp.tool()
async def get_info(host: str = "") -> str:
    """
    Get device information (model, name, API version, etc.).
    
    Args:
        host: The IP address of the device. Optional if STREAMMAGIC_HOST env var is set.
    """
    async with get_client(host) as client:
        info = await client.get_info()
        return info.to_json()

@mcp.tool()
async def get_state(host: str = "") -> str:
    """
    Get current state (power, source, volume, etc.).
    
    Args:
        host: The IP address of the device. Optional if STREAMMAGIC_HOST env var is set.
    """
    async with get_client(host) as client:
        state = await client.get_state()
        return state.to_json()

@mcp.tool()
async def get_now_playing(host: str = "") -> str:
    """
    Get current playback details (artist, track, album, art URL).
    
    Args:
        host: The IP address of the device. Optional if STREAMMAGIC_HOST env var is set.
    """
    async with get_client(host) as client:
        # aiostreammagic separates 'now playing' (controls) and 'play state' (metadata).
        # We want metadata, so we use get_play_state.
        play_state = await client.get_play_state()
        return play_state.to_json()

@mcp.tool()
async def list_sources(host: str = "") -> str:
    """
    Get a list of available input sources.
    
    Args:
        host: The IP address of the device. Optional if STREAMMAGIC_HOST env var is set.
    """
    async with get_client(host) as client:
        sources = await client.get_sources()
        import json
        # sources is a list of Source objects, so we map them to dicts or rely on masuhmaro list handling if available.
        # simpler to just construct list of dicts here manually or use list serialization helper if exists.
        # aiostreammagic models are DataClassORJSONMixin, so they have to_dict().
        return json.dumps([s.to_dict() for s in sources])

@mcp.tool()
async def set_power(power: bool, host: str = "") -> str:
    """
    Turn the device on or off (network standby).
    
    Args:
        power: True to turn ON, False to set to NETWORK standby.
        host: The IP address of the device.
    """
    async with get_client(host) as client:
        if power:
            await client.power_on()
            return "Powered On"
        else:
            await client.power_off()
            return "Powered Off (Network Standby)"

@mcp.tool()
async def set_volume(level: int, host: str = "") -> str:
    """
    Set volume level (0-100).
    
    Args:
        level: Volume level between 0 and 100.
        host: The IP address of the device.
    """
    async with get_client(host) as client:
        await client.set_volume(level)
        return f"Volume set to {level}"

@mcp.tool()
async def set_mute(mute: bool, host: str = "") -> str:
    """
    Mute or unmute the device.
    
    Args:
        mute: True to mute, False to unmute.
        host: The IP address of the device.
    """
    async with get_client(host) as client:
        await client.set_mute(mute)
        return f"Mute set to {mute}"

@mcp.tool()
async def control_playback(action: str, host: str = "") -> str:
    """
    Control playback (play, pause, stop, next, previous).
    
    Args:
        action: One of 'play', 'pause', 'stop', 'play_pause', 'next', 'previous'.
        host: The IP address of the device.
    """
    async with get_client(host) as client:
        action = action.lower()
        if action == "play":
            await client.play()
        elif action == "pause":
            await client.pause()
        elif action == "stop":
            await client.stop()
        elif action == "play_pause":
            await client.play_pause()
        elif action == "next":
            await client.next_track()
        elif action == "previous":
            await client.previous_track()
        else:
            raise ValueError(f"Unknown action: {action}")
        return f"Executed {action}"

@mcp.tool()
async def set_source(source_id: str, host: str = "") -> str:
    """
    Switch input source.
    
    Args:
        source_id: The ID of the source to switch to (e.g., 'AIRPLAY', 'CAST', 'SPDIF').
                   Use list_sources to see available IDs.
        host: The IP address of the device.
    """
    async with get_client(host) as client:
        await client.set_source_by_id(source_id)
        return f"Source set to {source_id}"

@mcp.tool()
async def play_preset(preset_number: int, host: str = "") -> str:
    """
    Recall a stored preset.
    
    Args:
        preset_number: The preset number (1-99 usually).
        host: The IP address of the device.
    """
    async with get_client(host) as client:
        await client.recall_preset(preset_number)
        return f"Recalled preset {preset_number}"

@mcp.tool()
async def discover_devices(timeout: int = 3) -> str:
    """
    Scan the network for StreamMagic devices.
    Returns a JSON string list of discovered devices.
    """
    from streammagic_mcp.discovery import discover_streammagic_devices
    import json
    
    devices = await discover_streammagic_devices(timeout)
    return json.dumps(devices)

@mcp.tool()
async def discover_media_servers(timeout: int = 3) -> str:
    """
    Scan the network for DLNA Media Servers.
    Returns a JSON string list of discovered servers.
    """
    from streammagic_mcp.discovery import discover_media_servers
    import json
    
    servers = await discover_media_servers(timeout)
    return json.dumps(servers)

@mcp.tool()
async def search_media_server(location: str, query: str) -> str:
    """
    Search for media on a DLNA Media Server.
    
    Args:
        location: The URL location of the Media Server.
        query: The search term (searches titles).
    """
    import json
    from dataclasses import asdict
    
    if location not in _dlna_clients:
        _dlna_clients[location] = DlnaClient(location)
    
    client = _dlna_clients[location]
    
    # Simplified search for maximum compatibility
    clean_query = query.replace('"', '') 
    criteria = f'dc:title contains "{clean_query}"'
    
    try:
        # WORKAROUND: Request 500 items because some servers (like Jellyfin) ignore criteria
        # and just return everything. We then filter manually.
        logger.debug(f"Searching Media Server {location} with criteria: {criteria}")
        raw_items = await client.search(search_criteria=criteria, count=500)
        
        # Manual Filtering (Case-Insensitive)
        q = query.lower()
        filtered_items = []
        for item in raw_items:
            # Check Title, Artist, or Album for the query
            match = q in item.title.lower() or \
                    (item.artist and q in item.artist.lower()) or \
                    (item.album and q in item.album.lower())
            
            if match:
                filtered_items.append(item)
        
        logger.info(f"Client-side filter: {len(filtered_items)} matches found out of {len(raw_items)} raw results.")
        return json.dumps([asdict(item) for item in filtered_items])
        
    except Exception as e:
        logger.error(f"Search failed on {location}: {e}")
        raise RuntimeError(f"Search failed. Error: {str(e)}")

@mcp.tool()
async def browse_media_server(location: str, object_id: str = "0", start_index: int = 0) -> str:
    """
    Browse a DLNA Media Server container.
    Returns a JSON object with 'items' and 'total'.
    
    Args:
        location: The URL location of the Media Server (from discovery).
        object_id: The ID of the container to browse (default "0" for root).
        start_index: The starting index for pagination.
    """
    import json
    from dataclasses import asdict
    
    if location not in _dlna_clients:
        _dlna_clients[location] = DlnaClient(location)
    
    client = _dlna_clients[location]
    items, total = await client.browse(object_id=object_id, start_index=start_index)
    
    return json.dumps({
        "items": [asdict(item) for item in items],
        "total": total
    })

@mcp.tool()
async def play_stream_url(url: str, metadata: str = "", host: str = "") -> str:
    """
    Play a specific URL (e.g. from a DLNA server) on the Cambridge Audio device.
    
    Args:
        url: The URL of the media resource to play.
        metadata: Optional DIDL-Lite metadata for the item (improves display on device).
        host: The IP address of the Cambridge Audio device.
    """
    # To play a URL, we need to talk to the AVTransport service of the DEVICE.
    # We need the device's UPnP location URL.
    # 1. Try to find it in our existing discovery cache or rescan.
    from streammagic_mcp.discovery import discover_streammagic_devices
    
    target_host = host or os.environ.get("STREAMMAGIC_HOST")
    if not target_host:
         raise ValueError("Host required")

    # Quick scan to find the UPnP location of the target host
    devices = await discover_streammagic_devices(timeout=2)
    device_loc = None
    for d in devices:
        if d['host'] == target_host:
            device_loc = d.get('location')
            break
            
    if not device_loc:
        raise RuntimeError(f"Could not find UPnP service for {target_host}. Ensure it is on the same network.")

    # Create DLNA client for the RENDERER
    if device_loc not in _dlna_clients:
        _dlna_clients[device_loc] = DlnaClient(device_loc)
        
    renderer = _dlna_clients[device_loc]
    await renderer.set_av_transport_uri(url, metadata)
    await renderer.play()
    
    return f"Playing {url}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()
