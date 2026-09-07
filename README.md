# Enterprise AI Assistant — POC

An enterprise-grade conversational AI assistant demonstrating agentic
patterns (LangGraph multi-agent orchestration + a simplified Recursive
Language Model), hybrid RAG, RBAC, guardrails, observability, and
production-leaning async engineering — built for **Northbridge
Commercial Bank** (fictional demo tenant) as internal knowledge-base
assistant.

> **Scope note:** this is a POC built to demonstrate architecture and
> patterns within a limited timebox, not a production system. Every
> place a corner was deliberately cut is called out explicitly in
> [Assumptions & Trade-offs](#assumptions--trade-offs) below.

---

## 1. Quick Start

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env
# edit .env: at minimum set GROQ_API_KEY (default provider), or ANTHROPIC_API_KEY / OPENAI_API_KEY.
# Everything else (Pinecone, LangSmith) is optional — see "Zero-key mode" below.

docker compose up --build
```

- Backend: http://localhost:8000 (docs at `/docs`)
- MCP dummy server: http://localhost:8100
- Frontend (Streamlit): http://localhost:8501

### Option B — Run locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in keys as desired

# Terminal 1 — backend
uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — dummy MCP server
uvicorn backend.app.mcp_server.server:app --reload --port 8100

# Terminal 3 — frontend
streamlit run frontend/streamlit_app.py
```

### Demo logins (hardcoded RBAC — Option A from the spec)

| Username  | Password    | Role          |
|-----------|-------------|---------------|
| viewer1   | viewer123   | viewer        |
| analyst1  | analyst123  | analyst       |
| admin1    | admin123    | administrator |

### Zero-key ("offline") mode

The whole pipeline — routing, hybrid retrieval, RLM batching, RBAC,
guardrails, streaming activity panel — runs **with no API keys at
all**: no LLM key falls back to a deterministic offline stub model,
no Pinecone key falls back to an in-memory vector store, no LangSmith
key simply skips tracing. This is intentional so a reviewer can clone
the repo and see the whole architecture work mechanically before
spending anything on LLM calls. Set `GROQ_API_KEY` (default provider —
free tier, fast Llama 3.3 inference), or `ANTHROPIC_API_KEY` /
`OPENAI_API_KEY`, in `.env` to get real generated answers.

### LLM provider

Default is **Groq** (`LLM_PROVIDER=groq`, model `llama-3.3-70b-versatile`)
— Groq's LPU inference is very low-latency, which suits the Agent
Activity Panel's per-node streaming, and its free tier makes the demo
cheap to reproduce. Anthropic Claude and OpenAI are wired in as
first-class alternatives; switch by setting `LLM_PROVIDER` to
`anthropic` or `openai` and supplying the matching key — no code
changes needed anywhere else in the graph. If the configured
provider's key is missing, the factory automatically falls back to
whichever key *is* present (groq → openai → anthropic → offline stub),
so a misconfigured `LLM_PROVIDER` never silently breaks the demo.

### Sanity-check the retrieval stack directly

```bash
python -m scripts.ingest_documents
```

### Run tests

```bash
pytest backend/tests -v
```

---

## 2. Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full
diagram and component-by-component write-up. Summary:

```
Streamlit UI  ──(SSE)──►  FastAPI  ──►  LangGraph
                                          │
                    ┌─────────────────────┼───────────────────────┐
                    ▼                     ▼                       ▼
              Supervisor Agent     Retrieval Agent          Research Agent (RLM)
              (intent + routing)   (hybrid RAG)              (batch/recurse/aggregate)
                    │                     │                       │
                    └─────────────────────┴───────────┬───────────┘
                                                        ▼
                                                Response Agent
                                          (citations + output guardrails)
```

Cross-cutting: RBAC enforced at the tool-call boundary, per-user token
bucket rate limiting, structured JSON logging, LangSmith tracing.

---

## 3. Requirement-by-requirement mapping

| Spec requirement | Where it lives |
|---|---|
| Streamlit chat UI, multi-turn, streaming | `frontend/streamlit_app.py`, `backend/app/api/routes_chat.py` (`/chat/stream`, SSE) |
| Agent Activity Panel | Same SSE stream drives `render_activity()` in the Streamlit app — it's literally the LangGraph state after each node |
| FastAPI async backend | `backend/app/main.py`, all routes/tools are `async def` |
| LangGraph multi-agent orchestration | `backend/app/agents/graph.py` + `supervisor.py`/`retrieval_agent.py`/`research_agent.py`/`response_agent.py` |
| Recursive Language Model (RLM) | `backend/app/agents/research_agent.py` — explore → plan (as a plain dict) → batch → recursive sub-agent calls → aggregate |
| Hybrid retrieval (dense + sparse) | `backend/app/retrieval/hybrid_search.py`, `embeddings.py`, `sparse_search.py` |
| Pinecone (namespaces, metadata filtering) | `backend/app/retrieval/vector_store.py` (`PineconeVectorStore`, with `LocalVectorStore` fallback) |
| Conversational memory | `backend/app/memory/conversation_memory.py` |
| Knowledge Search Tool | `backend/app/tools/knowledge_search_tool.py` |
| MCP Tool + dummy MCP server | `backend/app/mcp_server/server.py`, `backend/app/tools/mcp_client.py` |
| Python Analysis Tool | `backend/app/tools/python_analysis_tool.py` |
| LLM (any modern LLM, rationale documented) | `backend/app/agents/llm.py` — Groq (default), Anthropic, OpenAI, or offline stub, switchable via `LLM_PROVIDER` |
| LangSmith tracing | `backend/app/agents/graph.py` (env wiring); automatic once `LANGCHAIN_API_KEY` is set |
| Prompt injection / exfiltration / tool-abuse protection | `backend/app/guardrails/prompt_injection.py` |
| Input validation | `backend/app/guardrails/validators.py` (`ChatRequest`, `validate_tool_params`) |
| Guardrails: hallucinated citations, brand safety | `backend/app/guardrails/validators.py::check_output_guardrails` |
| Auth (hardcoded users/roles) | `backend/app/auth/models.py`, `security.py` |
| RBAC, enforced at tool execution | `backend/app/auth/rbac.py`, called from every agent node before a tool runs |
| Token bucket rate limiting | `backend/app/rate_limit/token_bucket.py` |
| Graceful error handling | Global exception handler in `main.py`; per-node try/except in `retrieval_agent.py`; MCP client returns structured errors instead of raising |
| Mock documents | `backend/data/sample_docs/*.md` |
| Docker Compose | `docker-compose.yml`, `Dockerfile.backend`, `Dockerfile.frontend` |

---

## 4. Assumptions & Trade-offs

These are the explicit calls made to fit the POC timebox — see spec's
instruction to "pick the best path as you see" and document it:

1. **RLM is simplified, not a literal recursive-LLM-calling-itself
   system.** It demonstrates the *pattern* (explore → generate a
   structured search plan → decompose into batches → call bounded
   sub-agent LLM calls → aggregate) using a single level of recursion.
   A production RLM would recursively re-batch any batch that's still
   too large, and could parallelize sub-agent calls.

2. **Python Analysis Tool does not `eval()` LLM-authored code.**
   Instead it exposes a small fixed set of safe operations
   (`count_by_field`, `count_by_month`, `top_keywords`) that the agent
   selects by name. Running arbitrary LLM-generated Python safely
   needs a hardened, network-isolated sandbox (e.g. gVisor/Firecracker
   microVM with a strict timeout and no filesystem/network access) —
   explicitly out of scope for a POC, and a common real-world source
   of "unsafe tool execution" incidents if done naively.

3. **MCP server is a simplified HTTP stand-in**, not a full MCP
   stdio/SSE transport server, per the spec explicitly marking this as
   "not a high priority requirement." The concept (agent calls an
   external enterprise system as a tool) is demonstrated end-to-end;
   swapping in `langchain-mcp-adapters` against a real MCP transport
   is a contained change to `tools/mcp_client.py` only.

4. **RBAC is hardcoded (Option A)**, not Keycloak/OIDC (Option B), to
   fit the timebox. The permission model (`auth/models.py`,
   `auth/rbac.py`) is deliberately decoupled from *how* a role is
   established, so swapping in Keycloak later only touches
   `auth/security.py`.

5. **Rate limiting is in-process, per-replica**, not shared across
   multiple backend instances. Production would back the token bucket
   with Redis (`INCR`+`TTL` or a Lua script for atomicity) so limits
   hold under horizontal scaling.

6. **Vector store defaults to a local in-memory numpy index** when no
   Pinecone key is supplied, and dense embeddings default to a local
   TF-IDF+SVD projection when no OpenAI key is supplied. Both are
   POC-quality substitutes purely so the system runs with zero paid
   dependencies; real deployments should always use Pinecone + a
   proper embedding model (the code path is already there — just add
   the keys).

7. **Memory persistence is in-process** (a Python dict keyed by
   session_id), not backed by Redis/Postgres, so it does not survive a
   server restart. The `MemoryStore` class is the single seam to swap
   in a persistent backend.

8. **Guardrail LLM-classifier layer is optional and best-effort.**
   If it errors, we fail open on *that specific layer* only (the
   heuristic regex layer, which requires no LLM call, always still
   runs) rather than blocking a legitimate user because a security
   classifier had a transient failure.

9. **Reranking, human-in-the-loop approval nodes, and a feedback loop**
   (bonus items) were not implemented, to prioritize the core-scope
   items (agent architecture, RAG, RLM, security, observability) given
   the time budget, per the weighting in the spec's evaluation table.

10. **Sample documents are synthetic/mocked**, generated for this POC,
    not real organizational data.

---

## 5. Security Notes (short version — see code comments for detail)

- **Authorization is enforced at the tool-call boundary**, not just
  the API route: `require_permission()` runs immediately before any
  tool executes, using the role decoded from a signed JWT — never
  from anything the LLM or the request body claims. See
  `agents/retrieval_agent.py` and `auth/rbac.py`.
- **Prompt injection**: heuristic regex layer (fast, always on) +
  optional LLM classifier layer, applied to both user input (direct
  injection) and retrieved document chunks (indirect/poisoned-document
  injection) before they enter the LLM context.
- **Output guardrails**: every `[doc:ID]` citation in a generated
  answer is checked against the IDs actually retrieved for that turn;
  unverifiable citations are stripped rather than shown.
- **Unknown tool names fail closed** in `rbac.py` — an unrecognized
  tool is treated as forbidden, never as implicitly allowed.

---

## 6. Repo layout

```
backend/
  app/
    agents/       # LangGraph nodes + graph assembly + RLM
    api/          # FastAPI routes + schemas
    auth/         # users, JWT, RBAC
    guardrails/   # prompt injection + validators
    mcp_server/   # dummy MCP server
    memory/       # conversation memory
    rate_limit/   # token bucket
    retrieval/    # embeddings, sparse, hybrid, vector store, loader
    tools/        # knowledge_search, python_analysis, mcp_client
  data/sample_docs/
  tests/
frontend/
  streamlit_app.py
scripts/
  ingest_documents.py
docs/
  ARCHITECTURE.md
docker-compose.yml
Dockerfile.backend / Dockerfile.frontend
requirements.txt
.env.example
```
