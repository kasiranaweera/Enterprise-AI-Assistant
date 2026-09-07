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
- Groq is wired in as the "open-source alternative" (spec explicitly
  lists this as an acceptable LLM choice): Groq's LPU inference serves
  open-weight models (Llama 3.3, Mixtral, Gemma...) at very low
  latency, which is a good fit for a chat UI where the Agent Activity
  Panel benefits from fast per-node turnaround. Default model is
  `llama-3.3-70b-versatile` — a strong general-purpose open model with
  good instruction-following for RAG/citation tasks; swap via
  `LLM_MODEL` for other Groq-hosted models (e.g. `mixtral-8x7b-32768`,
  `gemma2-9b-it`) with no code changes.
- Swapping providers is a one-line env var change (LLM_PROVIDER) with
  no code changes anywhere else in the graph, because every node only
  depends on this factory, never on a provider-specific SDK.
"""
from backend.app.config import get_settings

settings = get_settings()

_llm_singleton = None

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-6",
    "groq": "openai/gpt-oss-120b",
}


def get_llm(temperature: float = 0.1):
    global _llm_singleton
    if _llm_singleton is not None:
        return _llm_singleton

    provider = settings.llm_provider.lower()

    if provider == "groq" and settings.groq_api_key:
        from langchain_groq import ChatGroq

        model = (
            settings.llm_model
            if settings.llm_model not in ("claude-sonnet-4-6", "gpt-4o-mini", "llama-3.3-70b-versatile")
            else DEFAULT_MODELS["groq"]
        )
        _llm_singleton = ChatGroq(
            model=model,
            api_key=settings.groq_api_key,
            temperature=temperature,
        )
    elif provider == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        model = settings.llm_model if "gpt" in settings.llm_model else DEFAULT_MODELS["openai"]
        _llm_singleton = ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )
    elif provider == "anthropic" and settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic

        model = settings.llm_model if "claude" in settings.llm_model else DEFAULT_MODELS["anthropic"]
        _llm_singleton = ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )
    elif settings.groq_api_key:
        # Configured provider's key was missing — fall back to whichever
        # key IS actually present rather than erroring, so a misconfigured
        # LLM_PROVIDER doesn't silently drop straight to the offline stub.
        from langchain_groq import ChatGroq

        _llm_singleton = ChatGroq(model=DEFAULT_MODELS["groq"], api_key=settings.groq_api_key, temperature=temperature)
    elif settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        _llm_singleton = ChatOpenAI(model=DEFAULT_MODELS["openai"], api_key=settings.openai_api_key, temperature=temperature)
    elif settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic

        _llm_singleton = ChatAnthropic(model=DEFAULT_MODELS["anthropic"], api_key=settings.anthropic_api_key, temperature=temperature)
    else:
        # No key configured anywhere -> deterministic offline stub so the
        # whole pipeline (routing, retrieval, RLM batching, guardrails) is
        # still demonstrable without any paid API key.
        from backend.app.agents.offline_llm import OfflineStubLLM

        _llm_singleton = OfflineStubLLM()

    return _llm_singleton
