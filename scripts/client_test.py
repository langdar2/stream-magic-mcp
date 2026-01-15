import asyncio
import sys
import os

# Add src to path to allow direct import if needed for inspection, 
# but ideally we just run the server process.

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_client():
    # Check for host
    host = os.environ.get("STREAMMAGIC_HOST")
    if not host:
        print("Please set STREAMMAGIC_HOST environment variable.")
        return

    # Ensure we use the correct python and absolute path to server
    # Go up one level from scripts, then into src/streammagic_mcp/server.py
    server_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/streammagic_mcp/server.py"))
    
    if not os.path.exists(server_script):
        print(f"Error: Server script not found at {server_script}")
        return

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=os.environ.copy()
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print(f"Connected to server. Found {len(tools.tools)} tools.")
            for tool in tools.tools:
                print(f"- {tool.name}: {tool.description}")

            # Interactive loop
            print("\nEnter a tool name to execute (or 'quit'):")
            while True:
                tool_name = input("> ").strip()
                if tool_name == "quit":
                    break
                
                # Simple argument parsing for demo (assuming 1-2 args)
                args = {}
                if tool_name == "set_volume":
                    val = input("Volume (0-100): ")
                    args["level"] = int(val)
                elif tool_name == "set_power":
                    val = input("Power (on/off): ")
                    args["power"] = (val.lower() == "on")
                elif tool_name in ["set_source", "control_playback"]:
                    val = input("Value: ")
                    arg_name = "source_id" if tool_name == "set_source" else "action"
                    args[arg_name] = val
                
                # Always pass host if checking (though server defaults to env var if omitted in args)
                # But our wrapper in server.py expects args defined in tool definition.
                # Since server.py tools have host as optional, we can skip it if env var works.
                
                try:
                    result = await session.call_tool(tool_name, arguments=args)
                    print(f"Result: {result.content[0].text}")
                except Exception as e:
                    print(f"Error: {e}")

if __name__ == "__main__":
    # Ensure start from root
    if not os.path.exists("src/streammagic_mcp/server.py"):
         print("Please run this script from the project root: python scripts/client_test.py")
         sys.exit(1)
         
    asyncio.run(run_client())
