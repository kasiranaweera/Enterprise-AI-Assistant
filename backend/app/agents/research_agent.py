"""
Research Agent — simplified Recursive Language Model (RLM).

The spec's RLM concept, implemented at POC scale:

  1. EXPLORE   - instead of stuffing every retrieved chunk into one
                 giant prompt, we first look at *how much* material
                 matched and what documents it spans.
  2. PLAN      - we generate a small structured "search plan" (a plain
                 Python dict, not free-text) describing how to slice
                 the material: batch size, and optionally a metadata
                 filter (e.g. only "incident" documents about
                 "payments"). This is the "generate Python-based
                 search plans" requirement — kept as data structures
                 (safe, inspectable, loggable) rather than executing
                 LLM-authored code.
  3. DECOMPOSE - split the matched chunks into batches so each
                 sub-call only ever sees a bounded amount of text,
                 regardless of how many documents matched overall.
  4. RECURSE   - call a "sub-agent" (the same LLM, scoped to one
                 batch) once per batch. Each call is independent and
                 could trivially be parallelized or, for a truly large
                 corpus, recursively re-batched if a batch is itself
                 still too large (hence "recursive").
  5. AGGREGATE - combine the per-batch summaries into one coherent
                 finding set, which the Response Agent then turns into
                 the final prose answer with citations.

This mirrors the worked example in the spec (summarize a year of
payment-outage reports and find recurring root causes) without
requiring the entire corpus to fit in a single context window.
"""
from backend.app.agents.llm import get_llm
from backend.app.agents.state import GraphState
from backend.app.logging_config import get_logger, log_event

logger = get_logger("agents.research")

BATCH_SIZE = 3  # chunks per sub-agent call; small on purpose for the demo


def _build_search_plan(state: GraphState) -> dict:
    """Step 2: PLAN. A plain, inspectable dict — this *is* the
    'Python-based search plan' the spec asks for, deliberately kept as
    data rather than LLM-generated code for safety/explainability."""
    n_chunks = len(state.retrieved_chunks)
    plan = {
        "task": state.user_message,
        "total_matched_chunks": n_chunks,
        "batch_size": BATCH_SIZE,
        "num_batches": max(1, (n_chunks + BATCH_SIZE - 1) // BATCH_SIZE),
        "strategy": "sequential_batch_summarize_then_aggregate",
    }
    return plan


def _make_batches(chunks: list[dict], batch_size: int) -> list[list[dict]]:
    return [chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)]


def _summarize_batch(llm, task: str, batch: list[dict], batch_index: int) -> str:
    """Step 4: RECURSE — one bounded sub-agent call per batch."""
    context = "\n\n".join(
        f"[doc:{c['doc_id']}] ({c['metadata'].get('document_type')}, {c['metadata'].get('created_date')})\n{c['text']}"
        for c in batch
    )
    prompt = (
        f"You are a research sub-agent. Summarize the following batch of "
        f"document excerpts *only as it relates to*: \"{task}\".\n"
        f"Cite sources inline like [doc:ID]. Be concise.\n\n{context}"
    )
    result = llm.invoke(prompt)
    return getattr(result, "content", str(result))


def _aggregate(llm, task: str, batch_summaries: list[str]) -> str:
    """Step 5: AGGREGATE."""
    joined = "\n\n---\n\n".join(f"Batch {i+1} findings:\n{s}" for i, s in enumerate(batch_summaries))
    prompt = (
        f"Combine the following batch summaries into one coherent research "
        f"finding for the task: \"{task}\". Identify recurring themes / root "
        f"causes across batches if applicable. Keep citations [doc:ID] intact.\n\n{joined}"
    )
    result = llm.invoke(prompt)
    return getattr(result, "content", str(result))


def run_research(state: GraphState) -> GraphState:
    state.log("research", "started", "Building RLM search plan")
    llm = get_llm()

    if not state.retrieved_chunks:
        state.research_findings = "No matching documents were found to research."
        state.next_agent = "response"
        state.log("research", "skipped", "no chunks to research")
        return state

    plan = _build_search_plan(state)
    log_event(logger, "rlm_plan_generated", session=state.session_id, **plan)
    state.log("research", "plan_generated", str(plan))

    batches = _make_batches(state.retrieved_chunks, plan["batch_size"])
    state.rlm_batches = [{"batch_index": i, "chunk_ids": [c["chunk_id"] for c in b]} for i, b in enumerate(batches)]

    summaries = []
    for i, batch in enumerate(batches):
        state.log("research", "batch_processing", f"batch {i+1}/{len(batches)}")
        summary = _summarize_batch(llm, state.user_message, batch, i)
        summaries.append(summary)
        log_event(logger, "rlm_batch_summarized", session=state.session_id, batch_index=i)

    state.rlm_batch_summaries = summaries
    state.research_findings = _aggregate(llm, state.user_message, summaries)

    log_event(logger, "rlm_aggregation_complete", session=state.session_id, n_batches=len(batches))
    state.log("research", "completed", f"aggregated {len(batches)} batches")
    state.next_agent = "response"
    return state
