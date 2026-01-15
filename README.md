# StreamMagic Explorer (MCP Server & Web Dashboard)

A powerful MCP (Model Context Protocol) server and modern web-based dashboard for controlling Cambridge Audio StreamMagic devices (Evo, CXN, CXN V2, etc.).

## 🚀 Features

- **Modern Web Dashboard**: Glassmorphism UI with real-time state polling and "Now Playing" metadata.
- **DLNA Media Browsing**: Browse and play music directly from your home Media Servers (MinimServer, NAS, etc.).
- **Smart Queueing**: Client-side playback queue with automatic track fallback and "Play All" folder support.
- **Automatic Discovery**: Instant SSDP/UPnP scanning for both StreamMagic devices and DLNA servers.
- **High Performance**: Batched rendering and paginated browsing for large media collections.
- **Full Metadata Support**: View high-res album art, technical badges (Bitrate, Sample Rate, Codec), and track progress.

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/langdar2/stream-magic-mcp.git
cd streammagic-mcp

# Install dependencies
pip install .

# Install web client dependencies
pip install fastapi uvicorn
```

## 🎮 Usage

### 1. Web Dashboard (Recommended)
The web client provides a complete interface for discovery, control, and library browsing.

```bash
# Start the web bridge (starts both the UI and the MCP explorer)
python web_client/backend.py
```
Then visit: `http://localhost:8000`

### 2. Standard MCP Usage
You can use it as a standard MCP server with agents or directly via the CLI.

```bash
# Using mcp CLI
mcp run src/streammagic_mcp/server.py

# Or directly
python src/streammagic_mcp/server.py
```

## 🔧 Configuration

While the Web Dashboard handles discovery automatically, you can manually target a device via environment variables:

```bash
export STREAMMAGIC_HOST=192.168.1.50
```

## 🧰 Available Tools

- **Device Control**: `get_state`, `get_now_playing`, `set_volume`, `set_mute`, `control_playback`, `set_source`, `set_power`.
- **Discovery**: `discover_devices`, `discover_media_servers`.
- **DLNA**: `browse_media_server`, `search_media_server`, `play_stream_url`.

## 📜 License

MIT
