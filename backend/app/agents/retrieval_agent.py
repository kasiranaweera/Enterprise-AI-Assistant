"""
Retrieval Agent — RAG operations / vector search.

Every tool invocation goes through `require_permission` first. This
is the actual enforcement point the RBAC spec cares about: even
though every role is allowed to "search" in this POC's permission
matrix, the pattern generalizes — e.g. if "restricted" search were
gated behind Permission.ANALYTICS_TOOLS, a viewer's request would be
denied here regardless of what the LLM decided to do.
"""
from backend.app.auth.models import Role
from backend.app.auth.rbac import AuthorizationError, require_permission
from backend.app.agents.state import GraphState, ToolCallRecord
from backend.app.logging_config import get_logger, log_event
from backend.app.tools.knowledge_search_tool import knowledge_search

logger = get_logger("agents.retrieval")


async def run_retrieval(state: GraphState) -> GraphState:
    state.log("retrieval", "started", f"query='{state.user_message[:80]}'")

    try:
        require_permission(Role(state.user_role), "knowledge_search")
    except AuthorizationError as exc:
        state.blocked = True
        state.block_reason = str(exc)
        state.next_agent = "end"
        state.final_answer = "You don't have permission to search the knowledge base."
        state.tool_calls.append(
            ToolCallRecord(tool="knowledge_search", status="blocked", result_summary=str(exc))
        )
        log_event(logger, "rbac_denied", session=state.session_id, tool="knowledge_search")
        return state

    try:
        results = await knowledge_search(
            query=state.user_message,
            role=state.user_role,
            department_filter=None,  # left open so cross-department incidents are findable
            top_k=8,
        )
        state.retrieved_chunks = results
        state.tool_calls.append(
            ToolCallRecord(
                tool="knowledge_search",
                params={"query": state.user_message, "top_k": 8},
                result_summary=f"{len(results)} chunks retrieved",
            )
        )
        log_event(logger, "retrieval_complete", session=state.session_id, n_chunks=len(results))
        state.log("retrieval", "completed", f"{len(results)} chunks")
    except Exception as exc:  # graceful degradation per spec's error-handling requirement
        state.tool_calls.append(
            ToolCallRecord(tool="knowledge_search", status="error", result_summary=str(exc))
        )
        state.retrieved_chunks = []
        log_event(logger, "retrieval_error", session=state.session_id, error=str(exc))
        state.log("retrieval", "error", str(exc))

    state.next_agent = "research" if "research" in state.plan else "response"
    return state
