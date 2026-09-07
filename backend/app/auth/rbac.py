"""
RBAC enforcement at the *tool-invocation* boundary.

Important design decision: permission checks are NOT only on the API
route. The agent graph itself calls `require_permission()` immediately
before executing any tool (see agents/graph.py -> tool_node). This is
what "the agent should not be able to bypass authorization" means in
practice — even if a prompt injection convinces the LLM to try to call
an admin tool, the tool node hard-stops it before execution because it
checks the *authenticated* role from the JWT, not anything the LLM
said.
"""
from backend.app.auth.models import Permission, Role, has_permission

TOOL_PERMISSIONS: dict[str, Permission] = {
    "knowledge_search": Permission.SEARCH,
    "python_analysis": Permission.ANALYTICS_TOOLS,
    "mcp_lookup": Permission.MCP_TOOLS,
    "admin_reindex": Permission.ADMIN_TOOLS,
}


class AuthorizationError(Exception):
    pass


def require_permission(role: Role, tool_name: str) -> None:
    needed = TOOL_PERMISSIONS.get(tool_name)
    if needed is None:
        # Unknown tool name -> fail closed, not open.
        raise AuthorizationError(f"Unknown tool '{tool_name}' is not permitted.")
    if not has_permission(role, needed):
        raise AuthorizationError(
            f"Role '{role.value}' lacks permission '{needed.value}' required for tool '{tool_name}'."
        )
