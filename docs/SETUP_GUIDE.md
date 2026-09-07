# Setup & Run Guide — Enterprise AI Assistant (Groq edition)

This guide walks through setting up and running the project end to end,
using **Groq** as the default LLM provider (fast, free-tier-friendly
inference for open-weight models like Llama 3.3).

---

## 0. What changed for Groq

- `requirements.txt` — added `langchain-groq==0.2.1`
- `backend/app/config.py` — added `groq_api_key` setting
- `backend/app/agents/llm.py` — `get_llm()` now supports `LLM_PROVIDER=groq`
  (default `llama-3.3-70b-versatile`), with automatic fallback order
  `groq → openai → anthropic → offline stub` if the configured
  provider's key is missing
- `.env` / `.env.example` — `GROQ_API_KEY` added, `LLM_PROVIDER` and
  `LLM_MODEL` defaulted to Groq
- `README.md` — model rationale and requirement-mapping table updated

No other part of the system (LangGraph nodes, RAG, RBAC, guardrails,
tests) needed to change — every agent node only calls `get_llm()`, never
a provider SDK directly, so swapping providers is contained to those
three files.

---

## 1. Prerequisites

- Python 3.11+
- Docker + Docker Compose (recommended path), **or** just Python if
  running locally without Docker
- A free [Groq API key](https://console.groq.com/keys) — sign up, then
  create a key under "API Keys". Groq's free tier is generous and has
  no cost for this POC.

Optional (for full spec coverage, not required to run):
- A [Pinecone](https://www.pinecone.io/) API key (free tier) — without
  it the app falls back to an in-memory numpy vector store
- A [LangSmith](https://smith.langchain.com/) API key — without it the
  app simply skips tracing (LangSmith is marked mandatory in the spec,
  so set this before recording your demo video)

---

## 2. Configure environment variables

```bash
cd Enterprise-AI-Assistant
cp .env.example .env
```

Open `.env` and set at minimum:

```ini
GROQ_API_KEY=gsk_your_key_here
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
```

Recommended additions before your demo recording:

```ini
PINECONE_API_KEY=your_pinecone_key
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=enterprise-ai-assistant
```

Also change the placeholder secret:

```ini
JWT_SECRET_KEY=<any random string>
```

Everything else can be left at its default.

> **Zero-key mode:** if you skip all of the above, the app still boots
> and the full pipeline (routing, hybrid retrieval, RLM batching,
> RBAC, guardrails, streaming activity panel) still runs — with a
> deterministic offline stub LLM instead of real generated answers.
> Useful for a first smoke test before spending anything on API calls.

---

## 3. Run it — Option A: Docker Compose (recommended)

```bash
docker compose up --build
```

This starts three containers:

| Service      | Port | Purpose                          |
|--------------|------|-----------------------------------|
| `backend`    | 8000 | FastAPI + LangGraph orchestration |
| `mcp_server` | 8100 | Dummy MCP server (employee dir, service catalog, incidents) |
| `frontend`   | 8501 | Streamlit chat UI                 |

Wait for the backend healthcheck to pass, then open **http://localhost:8501**.

Stop everything with:

```bash
docker compose down          # add -v to also wipe volumes
```

---

## 4. Run it — Option B: locally without Docker

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Open three terminals (all with the venv activated):

```bash
# Terminal 1 — backend
uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — dummy MCP server
uvicorn backend.app.mcp_server.server:app --reload --port 8100

# Terminal 3 — frontend
streamlit run frontend/streamlit_app.py
```

---

## 5. Ingest the sample documents

In a new terminal (venv activated if running locally):

```bash
python -m scripts.ingest_documents
```

This loads the markdown files in `backend/data/sample_docs/` (incident
reports, runbooks, architecture docs, etc.) and indexes them into
Pinecone if configured, or the in-memory store otherwise. Run this
once after first startup, and again any time you add new documents.

---

## 6. Log in and chat

Open **http://localhost:8501**. Demo accounts (hardcoded RBAC):

| Username  | Password    | Role          | Can use                          |
|-----------|-------------|---------------|-----------------------------------|
| viewer1   | viewer123   | viewer        | Chat, search                      |
| analyst1  | analyst123  | analyst       | + analytics tools, MCP tools      |
| admin1    | admin123    | administrator | Everything                        |

Try, for example:

> "What caused the payment gateway outage in March 2025?"

Watch the **Agent Activity Panel** update live as the request moves
through Supervisor → Retrieval → Research (RLM) → Response, including
tool calls, retrieval status, and guardrail checks.

---

## 7. Verify everything

```bash
pytest backend/tests -v
```

All 12 tests should pass (hybrid search, RBAC enforcement, rate
limiting, prompt-injection heuristics).

Also check:

- **http://localhost:8000/docs** — interactive FastAPI reference
- **http://localhost:8000/health** — should return `{"status": "ok"}`
- **https://smith.langchain.com** — if you set `LANGCHAIN_API_KEY`,
  confirm traces are appearing under the `enterprise-ai-assistant`
  project. This is what you'll show in the demo video.

---

## 8. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Answers say `[OFFLINE MODE]` | No valid LLM key detected — check `GROQ_API_KEY` is set and `LLM_PROVIDER=groq` in `.env` |
| `ImportError: langchain_groq` | Re-run `pip install -r requirements.txt` inside the active venv |
| Port already in use | Another process is using 8000/8100/8501 — stop it or change the port in the run command / `docker-compose.yml` |
| Docker build fails on `pip install` | Check your network/proxy allows PyPI access; retry `docker compose build --no-cache` |
| No LangSmith traces appear | Confirm `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` are both set, then restart the backend (env is read at startup) |
| 403 on an admin tool as `analyst1` | Expected — RBAC is working as designed |

---

## 9. Next steps for submission

1. Push the repo publicly and confirm the remote is reachable.
2. Record the demo video with real Groq (+ optionally Pinecone/LangSmith)
   keys active so the traces and answers are real, not the offline stub.
3. Narrate the assumptions/trade-offs already documented in `README.md`
   section 4 — the spec explicitly asks for this.
4. Show a LangSmith trace on screen during the video (mandatory per spec).
