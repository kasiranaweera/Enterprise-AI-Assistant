"""
Shared state object threaded through every LangGraph node.

Kept as a single TypedDict-like structure (dataclass here for typing
convenience under Pydantic) so the Streamlit "Agent Activity Panel"
can be given the *entire* state after each node runs and render
whatever changed, rather than the UI needing bespoke per-node logic.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

AgentName = Literal["supervisor", "retrieval", "research", "response", "end"]


class ToolCallRecord(BaseModel):
    tool: str
    params: dict = Field(default_factory=dict)
    result_summary: str = ""
    status: Literal["success", "error", "blocked"] = "success"


class ActivityEvent(BaseModel):
    node: str
    event: str
    detail: str = ""


class GraphState(BaseModel):
    # Input
    session_id: str
    user_role: str
    user_department: str
    user_message: str
    conversation_context: str = ""

    # Routing
    intent: str = ""
    plan: list[str] = Field(default_factory=list)
    next_agent: AgentName = "supervisor"

    # Retrieval
    retrieved_chunks: list[dict] = Field(default_factory=list)

    # RLM / Research
    rlm_batches: list[dict] = Field(default_factory=list)
    rlm_batch_summaries: list[str] = Field(default_factory=list)
    research_findings: str = ""

    # Tool calls
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)

    # Guardrails
    blocked: bool = False
    block_reason: Optional[str] = None
    guardrail_warnings: list[str] = Field(default_factory=list)

    # Output
    final_answer: str = ""
    citations: list[dict] = Field(default_factory=list)

    # Observability (mirrors what LangSmith captures, kept here too so the
    # Streamlit panel can show it without a LangSmith API round-trip)
    activity_log: list[ActivityEvent] = Field(default_factory=list)

    def log(self, node: str, event: str, detail: str = "") -> None:
        self.activity_log.append(ActivityEvent(node=node, event=event, detail=detail))
