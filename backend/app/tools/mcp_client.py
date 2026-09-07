"""
MCP Client.

Talks to the dummy MCP server (backend/app/mcp_server/server.py) over
plain HTTP for this POC. A real MCP integration would use the MCP
protocol's stdio/SSE transport and langchain-mcp-adapters to expose
the server's tools directly to LangGraph; the HTTP shape below is
intentionally simple so the concept ("agent invokes an external
enterprise system as a tool") is easy to follow and demo without
extra transport plumbing.
"""
import httpx

from backend.app.config import get_settings

settings = get_settings()


async def mcp_lookup(resource: str, query: str = "") -> dict:
    """resource: 'employees' | 'services' | 'incidents'"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{settings.mcp_server_url}/mcp/{resource}", params={"q": query}
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            return {"error": f"MCP server call failed: {exc}"}
