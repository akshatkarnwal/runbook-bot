# DNIF Runbook Assistant

AI-powered chat assistant for platform engineers. Ask questions about incident runbooks and post-mortems in natural language.

## Demo

Ask: "How do I fix high CPU on DNIF?" → get step-by-step resolution from runbooks
Ask: "What is the escalation path?" → follow-up answered using conversation history
Ask: "How do I configure ingestion rules?" → honestly says it's not in the docs

## Stack

|      Component      |          Technology           |
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
Answer streamed back
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

- **On startup** — existing files in `data/` are ingested synchronously before the server starts accepting requests.
- **On demand, without a restart** — trigger a re-ingestion job via the async endpoints below. This lets you add new runbooks and pick them up live, without a redeploy.

## Async Ingestion API

| Endpoint                | Method | Description                                                        |
|--------------------------|--------|----------------------------------------------------------------------|
| `/ingest`                | POST   | Enqueues a new ingestion job onto the Redis Stream, returns immediately with a `job_id` |
| `/ingest/{job_id}`       | GET    | Returns the job's current status: `queued`, `processing`, `done` (with `documents_ingested` count), or `failed` (with `error`) |

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
Running ingestion in a separate `worker.py` process decouples slow, resource-heavy embedding work from the request/response cycle of the API. The API stays fast and responsive even while a large ingestion job is running, and the worker can be scaled or restarted independently.

**Why a web UI instead of Slack?**
A web interface is immediately accessible without OAuth setup — anyone can see a live demo by visiting a URL. Slack integration can be added as a thin wrapper around the same `/chat` API.

**Why refuse to answer outside the docs?**
Grounded answers build trust. A bot that says "I don't have that information" is more useful than one that confidently makes things up.
