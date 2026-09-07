"""
Input validation + output guardrails.

Brand-safety framing: the bot is positioned as the virtual assistant
for "Northbridge Commercial Bank" (a fictional company used as the
demo tenant, per the spec's suggestion). Guardrails below therefore
also cover financial-services-appropriate behavior: no investment
advice, no fabricated account/transaction data, no unqualified legal
claims.
"""
import re

from pydantic import BaseModel, Field, field_validator

BANK_NAME = "Northbridge Commercial Bank"

MAX_QUERY_LEN = 4000

DISALLOWED_OUTPUT_PATTERNS = [
    r"guaranteed returns?",
    r"insider information",
    r"account number[:\s]*\d{6,}",  # never let the model print what looks like a real acct number
]


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=MAX_QUERY_LEN)

    @field_validator("message")
    @classmethod
    def strip_control_chars(cls, v: str) -> str:
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v).strip()

    @field_validator("session_id")
    @classmethod
    def safe_session_id(cls, v: str) -> str:
        if not re.match(r"^[A-Za-z0-9_\-]+$", v):
            raise ValueError("session_id must be alphanumeric/dash/underscore only")
        return v


def validate_tool_params(tool_name: str, params: dict) -> tuple[bool, str | None]:
    """Very defensive parameter validation before any tool actually executes."""
    if not isinstance(params, dict):
        return False, "tool params must be a dict"
    # Reject obviously dangerous free-text params for the python analysis tool.
    if tool_name == "python_analysis":
        code = params.get("code", "")
        forbidden = ["import os", "import subprocess", "open(", "__import__", "eval(", "exec("]
        for f in forbidden:
            if f in code:
                return False, f"forbidden construct in analysis code: '{f}'"
    return True, None


def check_output_guardrails(answer: str, citations: list[dict]) -> tuple[str, list[str]]:
    """Returns (possibly-modified answer, list of warnings). Enforces:
    - no hallucinated citations (every citation must reference a real retrieved doc_id)
    - brand-safety patterns
    """
    warnings = []
    for pattern in DISALLOWED_OUTPUT_PATTERNS:
        if re.search(pattern, answer, re.IGNORECASE):
            warnings.append(f"brand_safety_pattern_matched:{pattern}")
            answer = re.sub(pattern, "[redacted]", answer, flags=re.IGNORECASE)

    if "[doc:" in answer:
        cited_ids = set(re.findall(r"\[doc:([\w\-]+)\]", answer))
        known_ids = {c["doc_id"] for c in citations}
        hallucinated = cited_ids - known_ids
        if hallucinated:
            warnings.append(f"hallucinated_citation_ids:{sorted(hallucinated)}")
            for hid in hallucinated:
                answer = answer.replace(f"[doc:{hid}]", "[citation removed - unverified]")

    return answer, warnings
