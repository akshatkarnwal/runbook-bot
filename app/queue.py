"""
Redis Streams-based job queue for async document ingestion.
Save as: app/queue.py
"""
import json
import time
import uuid
import redis
from app.config import settings

STREAM_NAME = "ingestion_jobs"
CONSUMER_GROUP = "ingestion_workers"

# Same connection pattern as app/memory.py, on purpose — this project
# already runs Redis, so the queue reuses it rather than adding new infra.
client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    decode_responses=True,
    socket_timeout=30,
)


def ensure_consumer_group():
    """Create the consumer group if it doesn't exist yet. Safe to call
    every startup — XGROUP CREATE errors harmlessly if it already
    exists (BUSYGROUP), which we catch and ignore."""
    try:
        client.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def enqueue_ingestion_job() -> str:
    """Push a new ingestion job onto the stream and return its job_id
    immediately. The actual (slow) ingestion happens later, in the
    worker process — not on this request's thread."""
    job_id = str(uuid.uuid4())
    client.xadd(STREAM_NAME, {"job_id": job_id})
    client.setex(
        f"ingestion:job:{job_id}",
        3600,
        json.dumps({"status": "queued", "requested_at": time.time()}),
    )
    return job_id


def get_job_status(job_id: str) -> dict | None:
    raw = client.get(f"ingestion:job:{job_id}")
    return json.loads(raw) if raw else None


def set_job_status(job_id: str, **fields):
    status = get_job_status(job_id) or {}
    status.update(fields)
    client.setex(f"ingestion:job:{job_id}", 3600, json.dumps(status))