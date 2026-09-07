"""
Tools & Analysis API.
Exposes document search, Python analysis tool, MCP tool lookups, and analytics.
Role restrictions:
- Search: Viewer, Analyst, Administrator (respecting document access filters)
- Python Analysis: Analyst, Administrator (Permission.ANALYTICS_TOOLS)
- MCP Tools: Analyst, Administrator (Permission.MCP_TOOLS)
- Analytics: Analyst, Administrator (Permission.ANALYTICS_TOOLS)
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from backend.app.auth.models import Permission, Role, User
from backend.app.auth.rbac import require_permission
from backend.app.auth.security import get_current_user, require_role
from backend.app.guardrails.validators import validate_tool_params
from backend.app.logging_config import get_audit_logs, get_logger, log_event
from backend.app.memory.conversation_memory import memory_store
from backend.app.rate_limit.token_bucket import enforce_rate_limit, rate_limiter_registry
from backend.app.retrieval.hybrid_search import HybridRetriever
from backend.app.tools.knowledge_search_tool import knowledge_search
from backend.app.tools.mcp_client import mcp_lookup
from backend.app.tools.python_analysis_tool import analyze

router = APIRouter(prefix="/tools", tags=["tools"])
logger = get_logger("api.tools")


class SearchRequest(BaseModel):
    query: str
    department: str | None = None
    document_type: str | None = None
    top_k: int = 6


class AnalysisRequest(BaseModel):
    operation: str
    params: dict[str, Any] = {}
    department: str | None = None
    document_type: str | None = None


@router.post("/search")
async def search_documents(payload: SearchRequest, user: User = Depends(get_current_user)):
    """Search documents in the knowledge base, filtered by the user's role access level."""
    await enforce_rate_limit(user)
    require_permission(user.role, "knowledge_search")
    results = await knowledge_search(
        query=payload.query,
        role=user.role.value,
        department_filter=payload.department or None,
        document_type=payload.document_type or None,
        top_k=payload.top_k,
    )
    log_event(
        logger,
        "document_search_executed",
        user=user.username,
        role=user.role.value,
        query=payload.query,
        hits=len(results),
    )
    return {"results": results, "count": len(results)}


@router.post("/python-analysis", dependencies=[Depends(require_role([Role.ANALYST, Role.ADMINISTRATOR]))])
async def run_python_analysis(payload: AnalysisRequest, user: User = Depends(get_current_user)):
    """Run structured Python analysis over knowledge-base documents (counts, timeline, keywords)."""
    await enforce_rate_limit(user)
    require_permission(user.role, "python_analysis")
    valid, err = validate_tool_params("python_analysis", payload.params)
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    retriever = HybridRetriever.instance()
    # Filter chunks based on user role
    allowed_access = {"internal", "restricted"} if user.role == Role.ANALYST else {"internal", "restricted", "confidential"}
    records = []
    for c in retriever.chunks:
        if c.metadata.get("access_level") in allowed_access:
            if payload.department and c.metadata.get("department") != payload.department:
                continue
            if payload.document_type and c.metadata.get("document_type") != payload.document_type:
                continue
            records.append({"text": c.text, "metadata": c.metadata})

    result = analyze(payload.operation, records, payload.params)
    log_event(
        logger,
        "python_analysis_executed",
        user=user.username,
        role=user.role.value,
        operation=payload.operation,
        records_analyzed=len(records),
    )
    return {"analysis": result, "records_analyzed": len(records)}


@router.get("/mcp/{resource}", dependencies=[Depends(require_role([Role.ANALYST, Role.ADMINISTRATOR]))])
async def query_mcp_tool(
    resource: str,
    q: str = Query(default=""),
    user: User = Depends(get_current_user),
):
    """Query external enterprise systems via MCP (employees, services, incidents)."""
    await enforce_rate_limit(user)
    require_permission(user.role, "mcp_lookup")
    res = await mcp_lookup(resource=resource, query=q)
    log_event(
        logger,
        "mcp_lookup_executed",
        user=user.username,
        role=user.role.value,
        resource=resource,
        query=q,
    )
    return res


@router.get("/analytics", dependencies=[Depends(require_role([Role.ANALYST, Role.ADMINISTRATOR]))])
async def get_analytics(user: User = Depends(get_current_user)):
    """Retrieve system, session, and assistant usage analytics."""
    await enforce_rate_limit(user)
    logs = get_audit_logs(limit=300)
    retriever = HybridRetriever.instance()

    events_counter: dict[str, int] = {}
    users_counter: dict[str, int] = {}
    for entry in logs:
        ev = entry.get("event", "unknown")
        events_counter[ev] = events_counter.get(ev, 0) + 1
        u = entry.get("user", "system")
        users_counter[u] = users_counter.get(u, 0) + 1

    bucket = await rate_limiter_registry.get_bucket(user.username)
    rate_info = {
        "user": user.username,
        "current_tokens": round(bucket.tokens, 2),
        "capacity": bucket.capacity,
        "refill_rate": bucket.refill_per_sec,
    }


    return {
        "total_indexed_chunks": len(retriever.chunks),
        "active_sessions_count": len(memory_store._sessions),
        "total_audit_events": len(logs),
        "event_distribution": events_counter,
        "user_activity": users_counter,
        "rate_limit_status": rate_info,
    }
