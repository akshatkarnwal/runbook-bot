"""
Background worker for async document ingestion.
Save at repo root as: worker.py

Run as a SEPARATE process from the FastAPI server:
    uv run python worker.py

Consumes jobs pushed onto the "ingestion_jobs" Redis Stream by
POST /ingest, and runs the actual (slow) ingest_documents() call here —
off the request/response path entirely. Producer (the API) and consumer
(this worker) are fully decoupled, connected only through Redis.
"""
import traceback

from app.queue import (
    client, STREAM_NAME, CONSUMER_GROUP,
    ensure_consumer_group, set_job_status,
)
from app.rag import ingest_documents

CONSUMER_NAME = "worker-1"  # a real deployment would give each replica a unique name


def process_job(job_id: str, message_id: str):
    print(f"[worker] Processing job {job_id}...")
    set_job_status(job_id, status="processing")
    try:
        count = ingest_documents()
        set_job_status(job_id, status="done", documents_ingested=count)
        print(f"[worker] Job {job_id} done — {count} documents ingested")
    except Exception as e:
        set_job_status(job_id, status="failed", error=str(e))
        print(f"[worker] Job {job_id} failed: {e}")
        traceback.print_exc()
    finally:
        client.xack(STREAM_NAME, CONSUMER_GROUP, message_id)


def main():
    ensure_consumer_group()
    print(f"[worker] Listening on '{STREAM_NAME}' as '{CONSUMER_NAME}'...")
    while True:
        response = client.xreadgroup(
            CONSUMER_GROUP, CONSUMER_NAME,
            {STREAM_NAME: ">"},
            count=1,
            block=5000,  # wait up to 5s for a new job before looping again
        )
        if not response:
            continue
        for _stream_name, messages in response:
            for message_id, fields in messages:
                process_job(fields["job_id"], message_id)


if __name__ == "__main__":
    main()