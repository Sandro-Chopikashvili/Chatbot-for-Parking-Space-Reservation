import asyncio
import os
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def _call(rid: int) -> str:
    url = os.getenv("MCP_URL", "http://127.0.0.1:8001/mcp")
    headers = {"Authorization": f"Bearer {os.getenv('MCP_TOKEN', '')}"}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("record_approved_reservation", {"reservation_id": rid})
            return result.content[0].text


def record_approved(rid: int, retries: int = 3) -> str:
    """Ask the MCP server to write the reservation to the file. Never raises.
    Returns the server's status, or 'unavailable' if every attempt failed."""
    for attempt in range(retries):
        try:
            return asyncio.run(asyncio.wait_for(_call(rid), timeout=10))
        except Exception as e:
            print(f"(MCP call failed: {type(e).__name__})")
            if attempt < retries - 1:
                time.sleep(1 + attempt)
    return "unavailable"