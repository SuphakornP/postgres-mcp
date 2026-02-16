"""
Local MCP Client for testing the PostgreSQL MCP Server.

Usage:
    1. Start the MCP server: python mcp_server.py
    2. Run this client: python mcp_client.py

Environment:
    MCP_API_KEY: API key for authentication (optional if server has no key configured)
"""

import asyncio
import os
from datetime import timedelta

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Load environment variables
load_dotenv()


async def main():
    """Test the PostgreSQL MCP server locally."""
    mcp_url = "http://localhost:8000/mcp"
    
    # Get API key from environment
    api_key = os.getenv("MCP_API_KEY", "")
    headers = {"X-API-Key": api_key} if api_key else {}

    print(f"Connecting to MCP server at {mcp_url}...")
    print(f"API Key: {'configured' if api_key else 'not configured (may fail if server requires auth)'}")
    
    async with streamablehttp_client(
        mcp_url, 
        headers, 
        timeout=timedelta(seconds=120), 
        terminate_on_close=False
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            print("Initializing MCP session...")
            await session.initialize()
            print("✓ MCP session initialized\n")

            # List available tools
            print("=" * 50)
            print("Available Tools:")
            print("=" * 50)
            tool_result = await session.list_tools()
            for tool in tool_result.tools:
                print(f"  - {tool.name}")
                if hasattr(tool, 'inputSchema') and tool.inputSchema:
                    props = tool.inputSchema.get('properties', {})
                    if props:
                        print(f"    Parameters: {list(props.keys())}")
            print()

            # List available resources
            print("=" * 50)
            print("Available Resources:")
            print("=" * 50)
            try:
                resource_result = await session.list_resources()
                if resource_result.resources:
                    for resource in resource_result.resources:
                        print(f"  - {resource.uri}")
                        print(f"    Name: {resource.name}")
                else:
                    print("  (No static resources - use postgres_query tool to explore)")
            except Exception as e:
                print(f"  Could not list resources: {e}")
            print()

            # Test the postgres_query tool - list tables
            print("=" * 50)
            print("Testing postgres_query tool - List tables:")
            print("=" * 50)
            try:
                result = await session.call_tool("postgres_query", {
                    "sql": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 10"
                })
                print(f"Result: {result.content[0].text}")
            except Exception as e:
                print(f"Error: {e}")
            print()

            # Test the postgres_query tool - simple query
            print("=" * 50)
            print("Testing postgres_query tool - SELECT 1:")
            print("=" * 50)
            try:
                result = await session.call_tool("postgres_query", {
                    "sql": "SELECT 1 as test_value, 'MCP Server Working!' as message"
                })
                print(f"Result: {result.content[0].text}")
            except Exception as e:
                print(f"Error: {e}")
            print()

            print("✓ MCP client test completed!")


if __name__ == "__main__":
    asyncio.run(main())
