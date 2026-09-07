"""
Resilient wrapper around `llm.invoke()`.

Spec requirement: "LLM failures" must be handled gracefully, not just
"the process doesn't crash." This wraps every LLM call site with:

1. A bounded retry (via tenacity) for transient failures — timeouts,
   rate limits, transient 5xxs from the provider.
2. A safe final fallback: if all retries are exhausted, we return a
   clearly-labeled degraded string instead of raising, so a single
   flaky LLM call degrades one answer instead of 500-ing the whole
   request. Callers can check `.degraded` on the result if they need
   to react (e.g. skip guardrail checks that assume real content).
"""
from dataclasses import dataclass

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.app.logging_config import get_logger

logger = get_logger("agents.resilient_invoke")

# Broad on purpose: different providers (Anthropic/OpenAI/Groq SDKs) raise
# their own exception hierarchies; we don't want a provider-specific import
# just to catch "the network call failed."
RETRYABLE_EXCEPTIONS = (Exception,)


@dataclass
class LLMResult:
    content: str
    degraded: bool = False


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
)
def _invoke_with_retry(llm, prompt: str):
    return llm.invoke(prompt)


def safe_invoke(llm, prompt: str, *, node: str, session_id: str = "") -> LLMResult:
    """Call the LLM with retries; degrade gracefully instead of raising."""
    try:
        result = _invoke_with_retry(llm, prompt)
        content = getattr(result, "content", str(result))
        return LLMResult(content=content, degraded=False)
    except Exception as exc:  # noqa: BLE001 - last-resort graceful degradation
        logger.warning(
            "llm_invoke_failed_after_retries",
            extra={"node": node, "session": session_id, "error": str(exc)},
        )
        return LLMResult(
            content=(
                "I wasn't able to generate a response right now because the "
                "language model provider is unavailable. Please try again "
                "shortly, or contact support if this persists."
            ),
            degraded=True,
        )
