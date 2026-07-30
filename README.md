# DNIF Runbook Assistant

AI-powered chat assistant for platform engineers. Ask questions about incident runbooks and post-mortems in natural language.

## Demo

Ask: "How do I fix high CPU on DNIF?" → get step-by-step resolution from runbooks
Ask: "What is the escalation path?" → follow-up answered using conversation history
Ask: "How do I configure ingestion rules?" → honestly says it's not in the docs

## Stack

|      Component      |          Technology           |
|---------------------|-------------------------------|
| API                 | FastAPI                       |
| RAG Framework       | LlamaIndex                    |
| Vector DB           | pgvector (PostgreSQL)         |
| LLM                 | Gemini 2.5 Flash              |
| Embeddings          | Gemini Embedding 2 (3072-dim) |
| Conversation Memory | Redis                         |
| Frontend            | Vanilla HTML/CSS/JS           |

## Features

- Natural language Q&A over DNIF platform runbooks
- Conversation memory via Redis (last 10 messages, 1hr TTL)
- Grounded answers — refuses to hallucinate outside the docs
- Session-based chat with clear history option
- Latency shown per message
- LlamaIndex document ingestion with automatic chunking

## Architecture

Browser Chat UI
↓
FastAPI /chat endpoint
↓
Redis (conversation history) pgvector (runbook chunks)
↓ ↓
LlamaIndex RAG pipeline
↓
Gemini 2.5 Flash
↓
Answer streamed back

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
uv init && uv add -r requirements.txt
uv run uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001

## Adding Your Own Runbooks

Drop `.md` or `.txt` files into the `data/` folder and restart the server. The ingestion pipeline automatically loads, chunks, and embeds them on startup.

## Key Design Decisions

**Why LlamaIndex over LangChain?**
LlamaIndex has first-class support for document ingestion with `SimpleDirectoryReader` — drop files in a folder and it handles loading, chunking, and metadata automatically.

**Why Redis for conversation memory?**
Redis gives O(1) key-value access with built-in TTL. Conversation history expires after 1 hour automatically — no cleanup job needed. The last 10 messages are kept to balance context vs token cost.

**Why a web UI instead of Slack?**
A web interface is immediately accessible without OAuth setup — anyone can see a live demo by visiting a URL. Slack integration can be added as a thin wrapper around the same `/chat` API.

**Why refuse to answer outside the docs?**
Grounded answers build trust. A bot that says "I don't have that information" is more useful than one that confidently makes things up.