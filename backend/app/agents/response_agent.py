"""
Response Agent — final answer generation.

Builds the answer either from the RLM's aggregated research findings
(research path) or directly from retrieved chunks (simple Q&A path),
always instructing the model to cite using [doc:ID] tags so the
output guardrail can verify every citation actually corresponds to a
retrieved document (no hallucinated citations).
"""
from backend.app.agents.llm import get_llm
from backend.app.agents.resilient_invoke import safe_invoke
from backend.app.agents.state import GraphState
from backend.app.guardrails.validators import check_output_guardrails
from backend.app.logging_config import get_logger, log_event

logger = get_logger("agents.response")


def _build_prompt(state: GraphState) -> str:
    context_block = state.conversation_context
    if state.research_findings:
        material = f"Research findings (already synthesized across multiple documents):\n{state.research_findings}"
    else:
        material = "\n\n".join(
            f"[doc:{c['doc_id']}] {c['text']}" for c in state.retrieved_chunks
        ) or "No relevant documents were retrieved."

    return (
        "You are an internal enterprise assistant for Northbridge Commercial Bank. "
        "Answer the user's question using ONLY the material provided below. "
        "Cite every factual claim with [doc:ID] using the IDs shown. "
        "If the material doesn't contain the answer, say so plainly — do not guess.\n\n"
        f"Conversation so far:\n{context_block}\n\n"
        f"Material:\n{material}\n\n"
        f"User question: {state.user_message}\n\nAnswer:"
    )


def run_response(state: GraphState) -> GraphState:
    state.log("response", "started", "Generating final answer")
    llm = get_llm()

    prompt = _build_prompt(state)
    llm_result = safe_invoke(llm, prompt, node="response", session_id=state.session_id)
    raw_answer = llm_result.content

    if llm_result.degraded:
        # Don't run citation/hallucination checks against a canned outage
        # message — there's nothing to verify, and it would just add a
        # confusing "no citations found" warning on top of the real issue.
        safe_answer, warnings = raw_answer, ["llm_provider_unavailable"]
    else:
        safe_answer, warnings = check_output_guardrails(raw_answer, state.retrieved_chunks)
    state.guardrail_warnings.extend(warnings)
    state.final_answer = safe_answer
    state.citations = [
        {"doc_id": c["doc_id"], "chunk_id": c["chunk_id"], "hybrid_score": c["hybrid_score"]}
        for c in state.retrieved_chunks
    ]

    log_event(
        logger,
        "response_generated",
        session=state.session_id,
        warnings=warnings,
        n_citations=len(state.citations),
    )
    state.log("response", "completed", f"{len(warnings)} guardrail warnings")
    state.next_agent = "end"
    return state
