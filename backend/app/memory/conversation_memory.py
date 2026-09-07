"""
Conversation memory.

Design decisions (documented per spec requirement):

1. Two tiers:
   - SHORT-TERM (per session): the raw last-N turns, kept verbatim so
     the Response Agent can resolve pronouns / follow-ups ("what about
     last month?"). Stored in-process keyed by session_id.
   - LONG-TERM summary (bonus: "long-term memory"): every ~6 turns we
     ask the LLM to compress the older turns into a running summary,
     so the context sent to the graph stays bounded in size even for
     very long sessions, instead of growing linearly forever.

2. Survives "multiple turns during a session" as required — it does
   NOT persist across server restarts in this POC (an in-memory dict).
   Swapping the backing store for Redis or a Postgres table is a
   drop-in change because everything goes through this one class.

3. We also keep a lightweight `user_context` dict (role, department)
   so retrieval filtering and guardrails can use it without re-deriving
   it from the JWT on every node.
"""
from dataclasses import dataclass, field

MAX_RAW_TURNS = 6


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class SessionMemory:
    session_id: str
    user_context: dict = field(default_factory=dict)
    raw_turns: list[Turn] = field(default_factory=list)
    running_summary: str = ""

    def add_turn(self, role: str, content: str) -> None:
        self.raw_turns.append(Turn(role=role, content=content))

    def needs_compaction(self) -> bool:
        return len(self.raw_turns) > MAX_RAW_TURNS

    def compact(self, summarizer_fn) -> None:
        """Compress the oldest turns into running_summary using an LLM call.
        `summarizer_fn(existing_summary, turns_text) -> new_summary` is injected
        so this class has no direct LLM dependency (easier to unit test)."""
        if not self.needs_compaction():
            return
        overflow = self.raw_turns[:-MAX_RAW_TURNS]
        keep = self.raw_turns[-MAX_RAW_TURNS:]
        overflow_text = "\n".join(f"{t.role}: {t.content}" for t in overflow)
        self.running_summary = summarizer_fn(self.running_summary, overflow_text)
        self.raw_turns = keep

    def as_context_string(self) -> str:
        parts = []
        if self.running_summary:
            parts.append(f"[Earlier conversation summary]\n{self.running_summary}")
        for t in self.raw_turns:
            parts.append(f"{t.role}: {t.content}")
        return "\n".join(parts)


class MemoryStore:
    """Process-wide registry of SessionMemory, keyed by session_id."""

    def __init__(self):
        self._sessions: dict[str, SessionMemory] = {}

    def get_or_create(self, session_id: str, user_context: dict | None = None) -> SessionMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(
                session_id=session_id, user_context=user_context or {}
            )
        return self._sessions[session_id]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


memory_store = MemoryStore()
