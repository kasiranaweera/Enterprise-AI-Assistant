"""
LangGraph orchestration.

Graph shape:

    START -> supervisor -> (conditional)
                 |-- blocked --> END
                 |-- routed  --> retrieval -> (conditional)
                                                 |-- research needed --> research -> response -> END
                                                 |-- else            --> response -> END

Each node is a plain async function operating on the shared
`GraphState`. LangSmith tracing is enabled globally via env vars
(LANGCHAIN_TRACING_V2=true, LANGCHAIN_API_KEY, LANGCHAIN_PROJECT) —
no extra code is needed per-node because LangGraph auto-instruments
every node execution, tool call, and state transition as a run/span
in that project.
"""
import os

from langgraph.graph import END, StateGraph

from backend.app.agents.research_agent import run_research
from backend.app.agents.response_agent import run_response
from backend.app.agents.retrieval_agent import run_retrieval
from backend.app.agents.state import GraphState
from backend.app.agents.supervisor import run_supervisor
from backend.app.config import get_settings

settings = get_settings()

# Wire LangSmith tracing env vars if configured (mandatory observability requirement).
if settings.langchain_tracing_v2:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
    if settings.langchain_api_key:
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)


def _route_after_supervisor(state: GraphState) -> str:
    return "end" if state.blocked else "retrieval"


def _route_after_retrieval(state: GraphState) -> str:
    if state.blocked:
        return "end"
    return "research" if "research" in state.plan else "response"


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("supervisor", run_supervisor)
    graph.add_node("retrieval", run_retrieval)
    graph.add_node("research", run_research)
    graph.add_node("response", run_response)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor", _route_after_supervisor, {"retrieval": "retrieval", "end": END}
    )
    graph.add_conditional_edges(
        "retrieval", _route_after_retrieval, {"research": "research", "response": "response", "end": END}
    )
    graph.add_edge("research", "response")
    graph.add_edge("response", END)

    return graph.compile()


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
