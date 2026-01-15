import asyncio
import aiohttp
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BrowsedItem:
    id: str
    parent_id: str
    title: str
    upnp_class: str
    is_container: bool
    res_url: Optional[str] = None
    album_art: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None

class DlnaClient:
    def __init__(self, location: str):
        self.location = location
        self._content_directory_url: Optional[str] = None
        self._av_transport_url: Optional[str] = None
        self._friendly_name: str = "Unknown Device"
        self._base_url: str = ""

    async def initialize(self):
        """Fetch description XML and parse service URLs."""
        if self._content_directory_url:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.location, timeout=5) as resp:
                    if resp.status != 200:
                        raise Exception(f"Failed to fetch description: {resp.status}")
                    xml_content = await resp.text()

            # Base URL logic (if provided in XML, else derive from location)
            root = ET.fromstring(xml_content)
            # Handle XML namespaces... simplified heavily here
            ns = {'n': 'urn:schemas-upnp-org:device-1-0'}
            # Some devices use default namespace
            
            # Simple recursive search for services
            # This is a naive parser but sufficient for basic DLNA
            
            # Extract Friendly Name
            # Typically under root -> device -> friendlyName
            # We'll use a lenient find
            fn_node = root.find(".//{urn:schemas-upnp-org:device-1-0}friendlyName")
            if fn_node is None:
                fn_node = root.find(".//friendlyName") # Try without NS
            if fn_node is not None and fn_node.text:
                self._friendly_name = fn_node.text

            # Resolve Base URL
            # If URLBase exists use it, otherwise location root
            params = urlparse(self.location)
            self._base_url = f"{params.scheme}://{params.netloc}"
            
            url_base_node = root.find(".//{urn:schemas-upnp-org:device-1-0}URLBase")
            if url_base_node is not None and url_base_node.text:
                self._base_url = url_base_node.text.rstrip('/')

            # Find Services (Robust / Namespace-agnostic)
            # Iterate all elements to find 'service' tags
            for elem in root.iter():
                if elem.tag.endswith("service"):
                    # Found a service tag, look for type and controlURL in children
                    st_text = None
                    ctrl_text = None
                    
                    for child in elem:
                        if child.tag.endswith("serviceType") and child.text:
                            st_text = child.text
                        elif child.tag.endswith("controlURL") and child.text:
                            ctrl_text = child.text
                            
                    if st_text and ctrl_text:
                        # Normalize URL
                        if not ctrl_text.startswith("http"):
                            if ctrl_text.startswith("/"):
                                 ctrl_text = self._base_url + ctrl_text
                            else:
                                 ctrl_text = self._base_url + "/" + ctrl_text
    
                        if "ContentDirectory" in st_text:
                            self._content_directory_url = ctrl_text
                            logger.debug(f"Found ContentDirectory: {ctrl_text}")
                        elif "AVTransport" in st_text:
                            self._av_transport_url = ctrl_text
                            logger.debug(f"Found AVTransport: {ctrl_text}")

        except Exception as e:
            logger.error(f"Error initializing DLNA client for {self.location}: {e}")
            raise

    async def browse(self, object_id: str = "0", start_index: int = 0, count: int = 100) -> Tuple[List[BrowsedItem], int]:
        """Browse a container on ContentDirectory."""
        if not self._content_directory_url:
            await self.initialize()
        
        if not self._content_directory_url:
            raise Exception("No ContentDirectory service found.")

        # Construct SOAP body
        soap_body = f"""<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
                    <ObjectID>{object_id}</ObjectID>
                    <BrowseFlag>BrowseDirectChildren</BrowseFlag>
                    <Filter>*</Filter>
                    <StartingIndex>{start_index}</StartingIndex>
                    <RequestedCount>{count}</RequestedCount>
                    <SortCriteria></SortCriteria>
                </u:Browse>
            </s:Body>
        </s:Envelope>"""

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"urn:schemas-upnp-org:service:ContentDirectory:1#Browse"'
        }

        async with aiohttp.ClientSession() as session:
            logger.debug(f"Browsing {self._content_directory_url} with object_id {object_id}")
            async with session.post(self._content_directory_url, data=soap_body, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Browse SOAP Error {resp.status}: {text}")
                    raise Exception(f"Browse failed: {resp.status} - {text}")
                
                response_xml = await resp.text()
        
        return self._parse_didl_result(response_xml)

    async def search(self, search_criteria: str, start_index: int = 0, count: int = 50) -> Tuple[List[BrowsedItem], int]:
        """Search for items on ContentDirectory."""
        if not self._content_directory_url:
            await self.initialize()
        
        if not self._content_directory_url:
            raise Exception("No ContentDirectory service found.")

        # Construct SOAP body for Search
        import html
        criteria_esc = html.escape(search_criteria)

        soap_body = f"""<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:Search xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">
                    <ContainerID>0</ContainerID>
                    <SearchCriteria>{criteria_esc}</SearchCriteria>
                    <Filter>*</Filter>
                    <StartingIndex>{start_index}</StartingIndex>
                    <RequestedCount>{count}</RequestedCount>
                    <SortCriteria></SortCriteria>
                </u:Search>
            </s:Body>
        </s:Envelope>"""

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"urn:schemas-upnp-org:service:ContentDirectory:1#Search"'
        }

        async with aiohttp.ClientSession() as session:
            logger.debug(f"Searching {self._content_directory_url} with criteria: {search_criteria}")
            async with session.post(self._content_directory_url, data=soap_body, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Search SOAP Error {resp.status}: {text}")
                    raise Exception(f"Search failed (might be unsupported by server): {resp.status}")
                
                response_xml = await resp.text()

        return self._parse_didl_result(response_xml)

    def _parse_didl_result(self, response_xml: str) -> Tuple[List[BrowsedItem], int]:
        """Helper to parse DIDL-Lite from a SOAP response."""
        try:
            root = ET.fromstring(response_xml)
            result_node = None
            total_matches = 0
            
            for elem in root.iter():
                tag = elem.tag.lower()
                if tag.endswith("result") and elem.text:
                    result_node = elem
                elif tag.endswith("totalmatches") and elem.text:
                    try:
                        total_matches = int(elem.text)
                    except:
                        pass
            
            if result_node is None or not result_node.text:
                return [], 0
            
            didl_string = result_node.text
            didl_root = ET.fromstring(didl_string)
            
            items = []
            for elem in didl_root:
                tag = elem.tag.lower()
                if "container" in tag or "item" in tag:
                    is_container = "container" in tag
                    oid = elem.attrib.get("id", "")
                    pid = elem.attrib.get("parentID", "")
                    
                    title = ""
                    upnp_class = ""
                    res_url = None
                    art = None
                    artist = None
                    album = None
                    
                    for child in elem:
                        ctag = child.tag
                        if "title" in ctag:
                            title = child.text
                        elif "class" in ctag:
                            upnp_class = child.text
                        elif "res" in ctag:
                            if not res_url:
                                res_url = child.text
                        elif "albumArtURI" in ctag:
                            art = child.text
                        elif "artist" in ctag:
                            artist = child.text
                        elif "album" in ctag:
                            album = child.text
                            
                    items.append(BrowsedItem(
                        id=oid,
                        parent_id=pid,
                        title=title or "Unknown",
                        upnp_class=upnp_class,
                        is_container=is_container,
                        res_url=res_url,
                        album_art=art,
                        artist=artist,
                        album=album
                    ))
            return items, total_matches
        except Exception as e:
            logger.error(f"Error parsing Result: {e}")
            raise e

    async def set_av_transport_uri(self, uri: str, metadata: str = ""):
        """Call SetAVTransportURI on AVTransport service."""
        if not self._av_transport_url:
            await self.initialize()
            
        if not self._av_transport_url:
            raise Exception("No AVTransport service found on device.")

        # HTML Escaping for URI and Metadata needed? Usually XML escaping.
        import html
        uri_esc = html.escape(uri)
        meta_esc = html.escape(metadata)

        soap_body = f"""<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                    <InstanceID>0</InstanceID>
                    <CurrentURI>{uri_esc}</CurrentURI>
                    <CurrentURIMetaData>{meta_esc}</CurrentURIMetaData>
                </u:SetAVTransportURI>
            </s:Body>
        </s:Envelope>"""

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self._av_transport_url, data=soap_body, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"SetAVTransportURI failed: {resp.status} - {text}")
                    
    async def play(self):
        """Call Play on AVTransport service."""
        if not self._av_transport_url:
             await self.initialize()

        soap_body = f"""<?xml version="1.0"?>
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
            <s:Body>
                <u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
                    <InstanceID>0</InstanceID>
                    <Speed>1</Speed>
                </u:Play>
            </s:Body>
        </s:Envelope>"""

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"urn:schemas-upnp-org:service:AVTransport:1#Play"'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self._av_transport_url, data=soap_body, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Play failed: {resp.status} - {text}")

