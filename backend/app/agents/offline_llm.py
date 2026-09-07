"""
Offline stub LLM.

Used only when neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set.
It implements just enough of the LangChain chat-model surface
(`.invoke(prompt) -> object with .content`) for every node in the
graph to run end-to-end, so the evaluator can clone the repo and see
the full agent architecture, RLM batching, RBAC, and guardrails work
mechanically — with an obviously-templated answer instead of a real
generative one. Swapping in a real key upgrades every node's output
quality with zero code changes.
"""
import re
from dataclasses import dataclass


@dataclass
class _Response:
    content: str


class OfflineStubLLM:
    def invoke(self, prompt) -> _Response:
        text = prompt if isinstance(prompt, str) else str(prompt)

        if "one word: SAFE or UNSAFE" in text:
            return _Response(content="SAFE")

        if "Classify the user's intent" in text:
            return _Response(content="knowledge_qa")

        if "Summarize the following batch" in text:
            snippet = text[-400:].replace("\n", " ")
            return _Response(content=f"[offline-summary] Key points extracted from batch: {snippet[:200]}...")

        if "Compress the OLDER turns" in text:
            return _Response(content="[offline-summary] Earlier discussion condensed (no LLM key configured).")

        if "Combine the following batch summaries" in text:
            return _Response(
                content=(
                    "[OFFLINE MODE — no LLM API key configured] Based on the retrieved "
                    "documents, here is a templated aggregate answer. Configure "
                    "ANTHROPIC_API_KEY or OPENAI_API_KEY in .env for a real generated answer.\n\n"
                    + text[-600:]
                )
            )

        return _Response(
            content="[OFFLINE MODE] Configure ANTHROPIC_API_KEY or OPENAI_API_KEY for a real response. "
            f"Echo of prompt tail: {text[-300:]}"
        )
