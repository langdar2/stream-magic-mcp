import os
import sys
import asyncio
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool

# Add src to path to find the server script
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

app = FastAPI(title="StreamMagic MCP Web Client")

# Serve static files
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static/index.html"))

# --------------------------------------------------------------------------------
# MCP Bridge Logic
# --------------------------------------------------------------------------------

class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]

# Helper to get absolute path to server.py
# Go up one level from web_client, then into src/streammagic_mcp/server.py
SERVER_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/streammagic_mcp/server.py"))

if not os.path.exists(SERVER_SCRIPT):
    print(f"CRITICAL ERROR: Server script not found at {SERVER_SCRIPT}")

@app.get("/api/tools")
async def list_tools():
    """List available tools from the MCP server."""
    host = os.environ.get("STREAMMAGIC_HOST", "") 
    
    # Use sys.executable to ensure we use the same python environment
    cmd = sys.executable
    print(f"Connecting to MCP server: {cmd} {SERVER_SCRIPT}")

    env = os.environ.copy()
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_path}:{current_pythonpath}" if current_pythonpath else src_path
    
    server_params = StdioServerParameters(
        command=cmd,
        args=[SERVER_SCRIPT], 
        env=env
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                # Serialize tools
                tools_data = []
                for tool in result.tools:
                    tools_data.append({
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    })
                return tools_data
    except Exception as e:
         import traceback
         traceback.print_exc() # Print to server console
         raise HTTPException(status_code=500, detail=f"MCP Server Error: {str(e)}")

@app.post("/api/execute")
async def execute_tool(request: ToolCallRequest):
    """Execute a tool on the MCP server."""
    host = os.environ.get("STREAMMAGIC_HOST", "") 
    
    # Allow execution without host if tool is a discovery or DLNA tool
    dlna_tools = ["discover_devices", "discover_media_servers", "browse_media_server", "search_media_server"]
    if not host and request.tool_name not in dlna_tools:
         # Check if host is provided in arguments
         if "host" not in request.arguments or not request.arguments["host"]:
             raise HTTPException(status_code=400, detail="Host not configured. Please scan for devices.")

    # Use sys.executable to ensure we use the same python environment
    cmd = sys.executable
    env = os.environ.copy()
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_path}:{current_pythonpath}" if current_pythonpath else src_path

    server_params = StdioServerParameters(
        command=cmd,
        args=[SERVER_SCRIPT],
        env=env
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(request.tool_name, arguments=request.arguments)
                
                # Check for errors in result content
                output_text = []
                is_error = False
                for content in result.content:
                    output_text.append(content.text)
                    
                if result.isError:
                     is_error = True

                return {
                    "status": "error" if is_error else "success",
                    "output": "\n".join(output_text)  
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Check for host
    if not os.environ.get("STREAMMAGIC_HOST"):
        print("WARNING: STREAMMAGIC_HOST environment variable not set.")
    
    print("Starting Web Client on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
