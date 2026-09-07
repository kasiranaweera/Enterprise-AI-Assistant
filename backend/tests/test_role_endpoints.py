import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.auth.models import Role, User
from backend.app.auth.security import create_access_token
from backend.app.main import app


@pytest.fixture
def viewer_token():
    user = User(username="viewer1", role=Role.VIEWER, department="general")
    return create_access_token(user)


@pytest.fixture
def analyst_token():
    user = User(username="analyst1", role=Role.ANALYST, department="payments")
    return create_access_token(user)


@pytest.fixture
def admin_token():
    user = User(username="admin1", role=Role.ADMINISTRATOR, department="platform")
    return create_access_token(user)


@pytest.mark.asyncio
async def test_viewer_can_search_documents(viewer_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/tools/search",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"query": "payment outage", "top_k": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_viewer_forbidden_from_analyst_and_admin_tools(viewer_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Python analysis forbidden
        resp1 = await client.post(
            "/tools/python-analysis",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"operation": "count_by_field", "params": {"field": "department"}},
        )
        assert resp1.status_code == 403

        # MCP forbidden
        resp2 = await client.get(
            "/tools/mcp/employees",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp2.status_code == 403

        # Admin tools forbidden
        resp3 = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp3.status_code == 403


@pytest.mark.asyncio
async def test_analyst_can_use_analysis_and_mcp_but_not_admin(analyst_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Python analysis permitted
        resp1 = await client.post(
            "/tools/python-analysis",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"operation": "count_by_field", "params": {"field": "document_type"}},
        )
        assert resp1.status_code == 200
        assert "analysis" in resp1.json()

        # Analytics permitted
        resp2 = await client.get(
            "/tools/analytics",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert resp2.status_code == 200
        assert "total_indexed_chunks" in resp2.json()

        # Admin forbidden
        resp3 = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert resp3.status_code == 403


@pytest.mark.asyncio
async def test_administrator_has_full_access(admin_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin users list
        resp1 = await client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp1.status_code == 200
        assert "users" in resp1.json()

        # Admin roles matrix
        resp2 = await client.get(
            "/admin/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp2.status_code == 200
        assert "matrix" in resp2.json()

        # Admin documents catalog
        resp3 = await client.get(
            "/admin/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp3.status_code == 200
        assert "documents" in resp3.json()

        # Admin reindex
        resp4 = await client.post(
            "/admin/reindex",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp4.status_code == 200
        assert resp4.json()["status"] == "reindexed"

        # Admin audit logs
        resp5 = await client.get(
            "/admin/logs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp5.status_code == 200
        assert "logs" in resp5.json()


@pytest.mark.asyncio
async def test_deep_research_blocked_for_viewer(viewer_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/chat/stream",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"session_id": "test-v", "message": "tell me about incidents", "deep_research": True},
        )
        assert resp.status_code == 200
        content = resp.text
        assert "Deep/RLM research requires Analyst or Administrator" in content


@pytest.mark.asyncio
async def test_standard_chat_stream_all_roles(viewer_token, analyst_token):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Standard chat without deep_research (deep_research=False)
        resp1 = await client.post(
            "/chat/stream",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"session_id": "test-v-std", "message": "hello payment gateway", "deep_research": False},
        )
        assert resp1.status_code == 200
        assert "data: " in resp1.text
        assert "state_update" in resp1.text or "final" in resp1.text

        # Analyst chat with deep_research
        resp2 = await client.post(
            "/chat/stream",
            headers={"Authorization": f"Bearer {analyst_token}"},
            json={"session_id": "test-a-deep", "message": "summarize all payment incidents", "deep_research": True},
        )
        assert resp2.status_code == 200
        assert "data: " in resp2.text

