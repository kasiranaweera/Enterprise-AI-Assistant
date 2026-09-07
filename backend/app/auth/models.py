"""
RBAC model — Option A from the spec (hardcoded users/roles).

Swap this module for a Keycloak/OIDC integration (Option B) later
without touching any calling code: everything downstream only relies
on `User.role` and `has_permission()`.
"""
from enum import Enum

from pydantic import BaseModel


class Role(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    ADMINISTRATOR = "administrator"


class Permission(str, Enum):
    CHAT = "chat"
    SEARCH = "search"
    ANALYTICS_TOOLS = "analytics_tools"
    MCP_TOOLS = "mcp_tools"
    ADMIN_TOOLS = "admin_tools"


# Explicit allow-list per the spec's table. Nothing is inherited implicitly —
# this makes the security review trivial: read top to bottom, that's the
# entire authorization surface.
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: {Permission.CHAT, Permission.SEARCH},
    Role.ANALYST: {
        Permission.CHAT,
        Permission.SEARCH,
        Permission.ANALYTICS_TOOLS,
        Permission.MCP_TOOLS,
    },
    Role.ADMINISTRATOR: {
        Permission.CHAT,
        Permission.SEARCH,
        Permission.ANALYTICS_TOOLS,
        Permission.MCP_TOOLS,
        Permission.ADMIN_TOOLS,
    },
}


class User(BaseModel):
    username: str
    role: Role
    department: str = "general"


# Hardcoded demo user directory. In a real system this is a DB table;
# passwords below are demo-only and hashed at auth time (see security.py).
DEMO_USERS: dict[str, dict] = {
    "viewer1": {"password": "viewer123", "role": Role.VIEWER, "department": "general"},
    "analyst1": {"password": "analyst123", "role": Role.ANALYST, "department": "payments"},
    "admin1": {"password": "admin123", "role": Role.ADMINISTRATOR, "department": "platform"},
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_all_users() -> list[dict]:
    return [
        {"username": u, "role": info["role"].value if isinstance(info["role"], Role) else info["role"], "department": info["department"]}
        for u, info in DEMO_USERS.items()
    ]


def get_roles_permissions_matrix() -> dict[str, list[str]]:
    return {
        role.value: sorted([p.value for p in perms])
        for role, perms in ROLE_PERMISSIONS.items()
    }

