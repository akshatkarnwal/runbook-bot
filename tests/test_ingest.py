"""
Tests for the async ingestion endpoints (POST /ingest, GET /ingest/{job_id}).

The `client` fixture (see conftest.py) already has ensure_consumer_group,
ingest_documents, enqueue_ingestion_job, and get_job_status mocked at the
app.main boundary, and lifespan has already run by the time each test body
executes.
"""


# ---------------------------------------------------------------------------
# POST /ingest
# ---------------------------------------------------------------------------


def test_trigger_ingestion_returns_202_and_job_id(client):
    client.mock_enqueue.return_value = "job-abc123"

    response = client.post("/ingest")

    assert response.status_code == 202
    assert response.json() == {"job_id": "job-abc123", "status": "queued"}
    client.mock_enqueue.assert_called_once_with()


def test_trigger_ingestion_calls_enqueue_exactly_once_per_request(client):
    client.mock_enqueue.return_value = "job-xyz789"

    client.post("/ingest")
    client.post("/ingest")

    assert client.mock_enqueue.call_count == 2


def test_trigger_ingestion_propagates_distinct_job_ids(client):
    client.mock_enqueue.side_effect = ["job-1", "job-2"]

    first = client.post("/ingest")
    second = client.post("/ingest")

    assert first.json()["job_id"] == "job-1"
    assert second.json()["job_id"] == "job-2"


# ---------------------------------------------------------------------------
# GET /ingest/{job_id}
# ---------------------------------------------------------------------------


def test_ingestion_status_queued(client):
    client.mock_get_status.return_value = {"status": "queued"}

    response = client.get("/ingest/job-abc123")

    assert response.status_code == 200
    assert response.json() == {"status": "queued"}
    client.mock_get_status.assert_called_once_with("job-abc123")


def test_ingestion_status_processing(client):
    client.mock_get_status.return_value = {"status": "processing"}

    response = client.get("/ingest/job-abc123")

    assert response.status_code == 200
    assert response.json()["status"] == "processing"


def test_ingestion_status_done_includes_document_count(client):
    client.mock_get_status.return_value = {
        "status": "done",
        "documents_ingested": 42,
    }

    response = client.get("/ingest/job-abc123")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["documents_ingested"] == 42


def test_ingestion_status_failed_includes_error(client):
    client.mock_get_status.return_value = {
        "status": "failed",
        "error": "connection refused",
    }

    response = client.get("/ingest/job-abc123")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == "connection refused"


def test_ingestion_status_not_found_returns_404(client):
    client.mock_get_status.return_value = None

    response = client.get("/ingest/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_ingestion_status_looks_up_the_requested_job_id(client):
    """Make sure the path param actually flows through to get_job_status,
    rather than e.g. a hardcoded/stale id."""
    client.mock_get_status.return_value = {"status": "queued"}

    client.get("/ingest/some-specific-uuid")

    client.mock_get_status.assert_called_once_with("some-specific-uuid")


# ---------------------------------------------------------------------------
# lifespan wiring
# ---------------------------------------------------------------------------


def test_lifespan_calls_ensure_consumer_group_on_startup(client):
    # The `with TestClient(app) as client:` in the fixture already triggered
    # startup by the time we get here, so this just asserts it happened.
    client.mock_ensure_group.assert_called_once_with()


def test_lifespan_still_calls_existing_ingest_documents_on_startup(client):
    # Guards against a regression where adding ensure_consumer_group()
    # accidentally clobbers or reorders the pre-existing sync ingest call.
    client.mock_ingest_documents.assert_called_once()
