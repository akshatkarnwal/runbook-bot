# DNIF Runbook Assistant

AI-powered chat assistant for platform engineers. Ask questions about incident runbooks and post-mortems in natural language.

## Demo

Ask: "How do I fix high CPU on DNIF?" → get step-by-step resolution from runbooks
Ask: "What is the escalation path?" → follow-up answered using conversation history
Ask: "How do I configure ingestion rules?" → honestly says it's not in the docs

## Stack

|      Component      |          Technology            |
|---------------------|--------------------------------|
| API                 | FastAPI                        |
| RAG Framework       | LlamaIndex                     |
| Vector DB           | pgvector (PostgreSQL)          |
| LLM                 | Gemini 2.5 Flash               |
| Embeddings          | Gemini Embedding 2 (3072-dim)  |
| Conversation Memory | Redis                          |
| Job Queue           | Redis Streams                  |
| Frontend            | Vanilla HTML/CSS/JS            |
| Testing             | pytest                         |
| CI                  | GitHub Actions                 |

## Features

- Natural language Q&A over DNIF platform runbooks
- Conversation memory via Redis (last 10 messages, 1hr TTL)
- Grounded answers — refuses to hallucinate outside the docs
- Session-based chat with clear history option
- Latency shown per message
- LlamaIndex document ingestion with automatic chunking
- Async document ingestion via Redis Streams — kick off a re-ingestion job without blocking the API, poll for status
- Dedicated background worker process for consuming ingestion jobs, decoupled from the API process
- Idempotent ingestion: re-ingesting replaces the vector data instead of appending duplicates
- Crash recovery: on startup the worker reclaims and re-runs jobs a previous instance never acknowledged
- pytest suite covering the ingestion endpoints, run automatically in CI on every push and PR

## Architecture

```
Browser Chat UI
      ↓
FastAPI /chat, /ingest, /ingest/{job_id} endpoints
      ↓                              ↓
Redis (conversation history)   Redis Streams (ingestion job queue)
      ↓                              ↓
pgvector (runbook chunks)      worker.py (standalone consumer)
      ↓                              ↓
LlamaIndex RAG pipeline  ⟵  ingest_documents()
      ↓
Gemini 2.5 Flash
      ↓
Answer returned
```

The chat path (`/chat`) and the ingestion path (`/ingest`) share the same Redis instance but use it differently: conversation memory uses plain keys with TTLs, while ingestion jobs use a Redis Stream so the API can enqueue work and return immediately, with `worker.py` processing jobs independently in the background.

## Quick Start

```bash
git clone https://github.com/akshatkarnwal/runbook-bot
cd runbook-bot
cp .env.example .env  # add your GEMINI_API_KEY

# start dependencies
docker run -d --name pgvector \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=vectordb \
  -p 5432:5432 pgvector/pgvector:pg16

docker run -d --name redis \
  -p 6379:6379 redis:7-alpine

# install and run
uv sync
uv run uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001

In a separate terminal, start the background worker to process async ingestion jobs:

```bash
uv run python worker.py
```

## Adding Your Own Runbooks

Drop `.md` or `.txt` files into the `data/` folder. The ingestion pipeline automatically loads, chunks, and embeds them:

- **On startup** — existing files in `data/` are ingested synchronously before the server starts accepting requests. Ingestion replaces the existing data, so restarting never creates duplicates.
- **On demand, without a restart** — trigger a re-ingestion job via the async endpoints below. This lets you add new runbooks and pick them up live, without a redeploy.

## Async Ingestion API

| Endpoint             | Method | Description                                  |
|----------------------|--------|----------------------------------------------|
| `/ingest`            | POST   | Enqueue an ingestion job, returns a `job_id` |
| `/ingest/{job_id}`   | GET    | Job status (see below)                       |

Job status is one of `queued`, `processing`, `done` (with `documents_ingested` count) or `failed` (with `error`).

```bash
# kick off an ingestion job
curl -X POST http://localhost:8001/ingest
# → {"job_id": "…", "status": "queued"}

# poll for status
curl http://localhost:8001/ingest/<job_id>
# → {"status": "done", "documents_ingested": 12}
```

`worker.py` must be running for jobs to actually get processed — the API only enqueues them.

## Testing & CI

```bash
uv run pytest tests/ -v
```

Tests mock Redis and the RAG pipeline at the `app.main` import boundary, so the suite runs without any real Redis or vector-store dependency. GitHub Actions runs the same suite via `uv` on every push and pull request against `master`.

## Key Design Decisions

**Why LlamaIndex over LangChain?**
LlamaIndex has first-class support for document ingestion with `SimpleDirectoryReader` — drop files in a folder and it handles loading, chunking, and metadata automatically.

**Why Redis for conversation memory?**
Redis gives O(1) key-value access with built-in TTL. Conversation history expires after 1 hour automatically — no cleanup job needed. The last 10 messages are kept to balance context vs token cost.

**Why Redis Streams for async ingestion, instead of a separate message broker?**
The project already runs Redis for conversation memory, so Redis Streams gives consumer groups, per-message acknowledgment, and job status tracking without adding new infrastructure. A dedicated broker (RabbitMQ, Kafka) would be overkill for a single-worker ingestion pipeline at this scale.

**Why a standalone worker process instead of a background task in the API process?**
Running ingestion in a separate `worker.py` process decouples slow, resource-heavy embedding work from the request/response cycle of the API. The API stays fast and responsive even while a large ingestion job is running, and the worker can be restarted independently; jobs it had claimed but not finished are recovered on startup.

**Why clear the vector table on every ingestion?**
Early on, every startup and every `/ingest` job appended another copy of each chunk (24 → 28 rows for 4 unique chunks), which filled `top_k` with identical results. `ingest_documents()` now clears the table after the documents load successfully, so a failed read can't leave it empty. At this scale a full reload is simpler and safer than diffing documents.

**Why reclaim pending messages on worker startup?**
A job read by a worker that dies before `XACK` stays in the stream's pending list and is never redelivered, because the worker only reads new messages. On startup the worker runs `XAUTOCLAIM` and re-runs anything left pending. Re-running is safe because ingestion is idempotent.

**Why a web UI instead of Slack?**
A web interface is immediately accessible without OAuth setup — anyone can see a live demo by visiting a URL. Slack integration can be added as a thin wrapper around the same `/chat` API.

**Why refuse to answer outside the docs?**
Grounded answers build trust. A bot that says "I don't have that information" is more useful than one that confidently makes things up.

## Known Limitations

- Out-of-scope refusal comes from the system prompt; there is no similarity threshold on retrieval.
- Single worker only: the consumer name is fixed (`worker-1`) and `XAUTOCLAIM` uses `min_idle_time=0`. Running several workers needs unique consumer names and an idle threshold so one worker doesn't take over a job another is still running.
- The vector table is empty for the few seconds a re-ingestion runs, so queries in that window get no context.
- No authentication on `/chat` or `/ingest`.
- Tests cover the ingestion endpoints only, not chat or conversation memory.
- Startup ingestion is synchronous, so a large `data/` folder delays readiness.
- Responses are returned whole, not streamed.