import pytest

from backend.app.auth.models import Role
from backend.app.auth.rbac import AuthorizationError, require_permission


def test_viewer_can_search():
    require_permission(Role.VIEWER, "knowledge_search")  # should not raise


def test_viewer_cannot_use_analytics_tool():
    with pytest.raises(AuthorizationError):
        require_permission(Role.VIEWER, "python_analysis")


def test_analyst_can_use_mcp():
    require_permission(Role.ANALYST, "mcp_lookup")  # should not raise


def test_analyst_cannot_use_admin_tool():
    with pytest.raises(AuthorizationError):
        require_permission(Role.ANALYST, "admin_reindex")


def test_administrator_can_use_everything():
    for tool in ["knowledge_search", "python_analysis", "mcp_lookup", "admin_reindex"]:
        require_permission(Role.ADMINISTRATOR, tool)


def test_unknown_tool_fails_closed():
    with pytest.raises(AuthorizationError):
        require_permission(Role.ADMINISTRATOR, "some_unregistered_tool")
