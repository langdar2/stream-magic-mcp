import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from streammagic_mcp.server import (
    get_info, get_state, set_power, set_volume, control_playback, 
    _clients
)
from aiostreammagic.models import Info, State

@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Mock return values for common methods
    client.connect = AsyncMock()
    client.is_connected = MagicMock(return_value=True)
    
    # Mock Info
    info_mock = MagicMock(spec=Info)
    info_mock.__str__.return_value = "Cambridge Audio Evo 150 (v1.0)"
    client.get_info.return_value = info_mock

    # Mock State
    state_mock = MagicMock(spec=State)
    state_mock.__str__.return_value = "Power: ON, Source: NETWORK"
    client.get_state.return_value = state_mock

    return client

@pytest_asyncio.fixture
async def patched_client(mock_client):
    # Patch the _clients dictionary to inject our mock without needing a real connection
    host = "192.168.1.100"
    _clients[host] = mock_client
    yield mock_client, host
    # Cleanup
    if host in _clients:
        del _clients[host]

@pytest.mark.asyncio
async def test_get_info(patched_client):
    client, host = patched_client
    result = await get_info(host=host)
    assert "Cambridge Audio Evo 150" in result
    client.get_info.assert_called_once()

@pytest.mark.asyncio
async def test_get_state(patched_client):
    client, host = patched_client
    result = await get_state(host=host)
    assert "Power: ON" in result
    client.get_state.assert_called_once()

@pytest.mark.asyncio
async def test_set_power(patched_client):
    client, host = patched_client
    
    # Test ON
    await set_power(True, host=host)
    client.power_on.assert_called_once()
    
    # Test OFF
    client.reset_mock()
    await set_power(False, host=host)
    client.power_off.assert_called_once()

@pytest.mark.asyncio
async def test_set_volume(patched_client):
    client, host = patched_client
    await set_volume(50, host=host)
    client.set_volume.assert_called_once_with(50)

@pytest.mark.asyncio
async def test_control_playback(patched_client):
    client, host = patched_client
    
    await control_playback("play", host=host)
    client.play.assert_called_once()
    
    client.reset_mock()
    await control_playback("pause", host=host)
    client.pause.assert_called_once()
    
    client.reset_mock()
    await control_playback("next", host=host)
    client.next_track.assert_called_once()
