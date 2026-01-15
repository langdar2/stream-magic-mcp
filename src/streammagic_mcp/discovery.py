import asyncio
import socket
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class SSDPDiscovery:
    def __init__(self):
        self._found_devices: List[Dict[str, str]] = []

    async def discover(self, target: str = "urn:schemas-upnp-org:device:MediaRenderer:1", timeout: int = 3) -> List[Dict[str, str]]:
        """
        Discover UPnP devices using SSDP.
        Returns a list of dicts with 'host', 'model', 'name', 'location', 'usn'.
        """
        self._found_devices = []
        
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: SSDPProtocol(self._found_devices, target),
            family=socket.AF_INET
        )
        
        try:
            m_search = (
                f'M-SEARCH * HTTP/1.1\r\n'
                f'HOST: 239.255.255.250:1900\r\n'
                f'MAN: "ssdp:discover"\r\n'
                f'MX: {timeout}\r\n'
                f'ST: {target}\r\n'
                f'\r\n'
            ).encode()
            
            transport.sendto(m_search, ('239.255.255.250', 1900))
            await asyncio.sleep(timeout)
        finally:
            transport.close()
            
        return self._unique_devices(self._found_devices)

    def _unique_devices(self, devices: List[Dict[str, str]]) -> List[Dict[str, str]]:
        unique = {}
        for d in devices:
            # Use USN as unique identifier if available, else host+location
            key = d.get('usn') or (d['host'] + d.get('location', ''))
            if key not in unique:
                unique[key] = d
        return list(unique.values())

class SSDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, device_list: List[Dict[str, str]], target: str):
        self.device_list = device_list
        self.target = target

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        try:
            message = data.decode('utf-8')
            headers = self._parse_headers(message)
            
            location = headers.get('LOCATION', '')
            if not location:
                return

            usn = headers.get('USN', '')
            server = headers.get('SERVER', 'Unknown')
            
            # For MediaServers, we want to extract the description XML URL (location)
            # We don't filter rigorously here, letting the caller decide.
            
            # Fix for Dockerized servers advertising internal IP (e.g. 172.x)
            # We rewrite the LOCATION url to use the IP address we received the packet from.
            try:
                from urllib.parse import urlparse
                host = addr[0]
                parsed = urlparse(location)
                if parsed.hostname and parsed.hostname != host:
                    # Replace hostname in netloc (keeping port)
                    new_netloc = parsed.netloc.replace(parsed.hostname, host)
                    location = location.replace(parsed.netloc, new_netloc)
                    # logger.debug(f"Rewrote location {parsed.netloc} -> {new_netloc}")
            except Exception:
                pass

            self.device_list.append({
                "host": addr[0],
                "location": location,
                "usn": usn,
                "server": server,
                "model": server, # Proxy
                "name": f"UPnP Device ({addr[0]})" # Will be updated if we fetch XML
            })
            
        except Exception as e:
            logger.debug(f"Error parsing SSDP packet: {e}")

    def _parse_headers(self, message: str) -> Dict[str, str]:
        headers = {}
        lines = message.split('\r\n')
        # Line 0 is like "HTTP/1.1 200 OK"
        for line in lines[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.upper().strip()] = value.strip()
        return headers

async def discover_streammagic_devices(timeout: int = 3) -> List[Dict[str, str]]:
    """Helper function to run discovery for StreamMagic (Renderers)."""
    discovery = SSDPDiscovery()
    devices = await discovery.discover("urn:schemas-upnp-org:device:MediaRenderer:1", timeout)
    # Filter for known StreamMagic signatures if strict mode needed, 
    # but for now we return all Renderers.
    return devices

async def discover_media_servers(timeout: int = 3) -> List[Dict[str, str]]:
    """Helper function to run discovery for DLNA Media Servers."""
    discovery = SSDPDiscovery()
    return await discovery.discover("urn:schemas-upnp-org:device:MediaServer:1", timeout)
