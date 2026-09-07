"""
Chat API.

POST /chat/stream is the primary endpoint: it drives the LangGraph
graph via `.astream(..., stream_mode="values")`, which yields the
*entire* GraphState after every node finishes. Each yield is emitted
as a Server-Sent Event so the Streamlit Agent Activity Panel can
render "current node / tool calls / retrieval status / validation
results" in real time, and the final event carries the finished
answer for the chat window (satisfying both the "streaming responses"
and "agent activity panel" UI requirements from one graph run).
"""
import asyncio
import json

import orjson
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.app.agents.graph import get_compiled_graph
from backend.app.agents.llm import get_llm
from backend.app.agents.state import GraphState
from backend.app.auth.models import User
from backend.app.auth.security import get_current_user
from backend.app.guardrails.validators import ChatRequest
from backend.app.logging_config import get_logger, log_event, request_context
from backend.app.memory.conversation_memory import memory_store
from backend.app.rate_limit.token_bucket import rate_limiter_registry

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger("api.chat")


def _summarizer_fn(existing_summary: str, overflow_text: str) -> str:
    llm = get_llm()
    prompt = (
        "Compress the OLDER turns of a conversation into a short running "
        f"summary, merging with any existing summary.\n\nExisting summary:\n{existing_summary}\n\n"
        f"Older turns to fold in:\n{overflow_text}\n\nNew combined summary:"
    )
    result = llm.invoke(prompt)
    return getattr(result, "content", str(result))


async def _event_stream(request: ChatRequest, user: User):
    request_context.set({"session_id": request.session_id, "user": user.username, "role": user.role.value})

    allowed, retry_after = await rate_limiter_registry.check(user.username)
    if not allowed:
        yield _sse({"type": "error", "detail": f"Rate limit exceeded. Retry after {retry_after:.1f}s"})
        return

    if request.deep_research and user.role.value == "viewer":
        yield _sse({"type": "error", "detail": "Deep/RLM research requires Analyst or Administrator role."})
        return

    session = memory_store.get_or_create(
        request.session_id, user_context={"role": user.role.value, "department": user.department}
    )
    session.add_turn("user", request.message)
    session.compact(_summarizer_fn)

    initial_state = GraphState(
        session_id=request.session_id,
        user_role=user.role.value,
        user_department=user.department,
        user_message=request.message,
        conversation_context=session.as_context_string(),
        intent="research_task" if request.deep_research else "",
    )



    graph = get_compiled_graph()
    last_state: GraphState | None = None

    try:
        async for state_dict in graph.astream(initial_state, stream_mode="values"):
            last_state = state_dict if isinstance(state_dict, GraphState) else GraphState(**state_dict)
            yield _sse(
                {
                    "type": "state_update",
                    "next_agent": last_state.next_agent,
                    "activity_log": [e.model_dump() for e in last_state.activity_log],
                    "tool_calls": [t.model_dump() for t in last_state.tool_calls],
                    "guardrail_warnings": last_state.guardrail_warnings,
                    "retrieved_count": len(last_state.retrieved_chunks),
                }
            )
            await asyncio.sleep(0)  # yield control so the client sees incremental frames
    except Exception as exc:
        log_event(logger, "graph_execution_error", session=request.session_id, error=str(exc))
        yield _sse({"type": "error", "detail": "The assistant hit an internal error. Please try again."})
        return

    if last_state:
        session.add_turn("assistant", last_state.final_answer)
        yield _sse(
            {
                "type": "final",
                "answer": last_state.final_answer,
                "citations": last_state.citations,
                "guardrail_warnings": last_state.guardrail_warnings,
            }
        )


def _sse(payload: dict) -> str:
    return f"data: {orjson.dumps(payload).decode()}\n\n"


@router.post("/stream")
async def chat_stream(payload: ChatRequest, user: User = Depends(get_current_user)):
    return StreamingResponse(_event_stream(payload, user), media_type="text/event-stream")


@router.post("")
async def chat_once(payload: ChatRequest, user: User = Depends(get_current_user)):
    """Non-streaming convenience endpoint (used by simple clients / tests)."""
    final = None
    async for chunk in _event_stream(payload, user):
        data = json.loads(chunk.removeprefix("data: ").strip())
        if data.get("type") == "error":
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=data["detail"])
        if data.get("type") == "final":
            final = data
    if final is None:
        raise HTTPException(status_code=500, detail="No response generated")
    return final


@router.get("/memory/{session_id}")
async def get_session_memory(session_id: str, user: User = Depends(get_current_user)):
    session = memory_store.get_or_create(session_id)
    return {
        "session_id": session.session_id,
        "raw_turns_count": len(session.raw_turns),
        "raw_turns": [{"role": t.role, "content": t.content} for t in session.raw_turns],
        "running_summary": session.running_summary,
        "user_context": session.user_context,
    }


@router.delete("/memory/{session_id}")
async def clear_session_memory(session_id: str, user: User = Depends(get_current_user)):
    memory_store.clear(session_id)
    return {"status": "cleared", "session_id": session_id}

