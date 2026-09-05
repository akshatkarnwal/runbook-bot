import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.rag import ingest_documents, query
from app.memory import add_message, format_history_for_prompt, clear_history
from app.config import settings
from app.queue import enqueue_ingestion_job, get_job_status, ensure_consumer_group


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Ingesting runbooks...")
    ingest_documents()
    ensure_consumer_group()
    print("Ready")
    yield


app = FastAPI(
    title="DNIF Runbook Assistant",
    description="AI assistant for platform engineers",
    version="1.0.0",
    lifespan=lifespan,
)

# serve frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")


class ChatRequest(BaseModel):
    question: str
    session_id: str = ""


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    latency_ms: float


class ClearRequest(BaseModel):
    session_id: str


@app.get("/")
def root():
    return FileResponse("frontend/index.html")


@app.get("/health")
def health():
    return {"status": "ok", "collection": settings.collection_name}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # generate session if not provided
    session_id = request.session_id or str(uuid.uuid4())

    start = time.time()

    # get conversation history from Redis
    history = format_history_for_prompt(session_id)

    # query RAG
    answer = query(request.question, history)

    latency_ms = round((time.time() - start) * 1000, 2)

    # save to Redis
    add_message(session_id, "user", request.question)
    add_message(session_id, "assistant", answer)

    return ChatResponse(answer=answer, session_id=session_id, latency_ms=latency_ms)


@app.post("/clear")
def clear(request: ClearRequest):
    clear_history(request.session_id)
    return {"status": "cleared", "session_id": request.session_id}

        
        
@app.post("/ingest", status_code=202)
def trigger_ingestion():
        job_id = enqueue_ingestion_job()
        return {"job_id": job_id, "status": "queued"}

@app.get("/ingest/{job_id}")
def ingestion_status(job_id: str):
    status = get_job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return status
