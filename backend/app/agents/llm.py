"""
LLM provider factory.

Model selection rationale (documented per spec requirement):
- Default provider is Anthropic Claude (claude-sonnet-4-6): strong
  instruction-following and long-context reasoning, which matters for
  the Supervisor's routing/decomposition step and the Response Agent's
  citation discipline.
- OpenAI is wired in as a first-class alternative (gpt-4o-mini class
  models) for cost-sensitive deployments or when only an OpenAI key is
  available.
- Swapping providers is a one-line env var change (LLM_PROVIDER) with
  no code changes anywhere else in the graph, because every node only
  depends on this factory, never on a provider-specific SDK.
"""
from backend.app.config import get_settings

settings = get_settings()

_llm_singleton = None


def get_llm(temperature: float = 0.1):
    global _llm_singleton
    if _llm_singleton is not None:
        return _llm_singleton

    if settings.llm_provider == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        _llm_singleton = ChatOpenAI(
            model=settings.llm_model if "gpt" in settings.llm_model else "gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=temperature,
        )
    elif settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic

        _llm_singleton = ChatAnthropic(
            model=settings.llm_model if "claude" in settings.llm_model else "claude-sonnet-4-6",
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )
    else:
        # No key configured anywhere -> deterministic offline stub so the
        # whole pipeline (routing, retrieval, RLM batching, guardrails) is
        # still demonstrable without any paid API key.
        from backend.app.agents.offline_llm import OfflineStubLLM

        _llm_singleton = OfflineStubLLM()

    return _llm_singleton
