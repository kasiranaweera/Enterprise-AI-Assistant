"""
Python Analysis Tool.

Performs structured analysis (counts, groupings, simple stats) over
retrieved data — e.g. "how many payment-related incidents per month".
For safety this does NOT eval() arbitrary LLM-authored code against
the live interpreter. Instead it exposes a small, fixed set of safe
analysis *operations* that the agent selects by name + params. This
sidesteps the entire "sandbox escape" class of risk that comes with
running LLM-generated Python directly (the spec's guardrail around
"unsafe tool execution").

If you truly need free-form code execution, run it in a hardened,
network-isolated subprocess/container with a strict timeout — noted
as a production trade-off in README, deliberately out of scope here.
"""
from collections import Counter
from datetime import datetime


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def analyze(operation: str, records: list[dict], params: dict | None = None) -> dict:
    params = params or {}

    if operation == "count_by_field":
        field = params.get("field", "document_type")
        counts = Counter(r.get("metadata", {}).get(field, "unknown") for r in records)
        return {"operation": operation, "field": field, "counts": dict(counts)}

    if operation == "count_by_month":
        date_field = params.get("date_field", "created_date")
        counts: Counter = Counter()
        for r in records:
            dt = _parse_date(r.get("metadata", {}).get(date_field, ""))
            key = dt.strftime("%Y-%m") if dt else "unknown"
            counts[key] += 1
        return {"operation": operation, "counts": dict(sorted(counts.items()))}

    if operation == "top_keywords":
        import re
        from collections import Counter as C

        text = " ".join(r.get("text", "") for r in records).lower()
        words = re.findall(r"[a-z]{4,}", text)
        stop = {"this", "that", "with", "from", "were", "have", "been", "will", "into"}
        words = [w for w in words if w not in stop]
        top = C(words).most_common(params.get("n", 10))
        return {"operation": operation, "top_keywords": top}

    return {"operation": operation, "error": "unsupported operation"}


SUPPORTED_OPERATIONS = ["count_by_field", "count_by_month", "top_keywords"]
