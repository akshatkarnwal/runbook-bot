"""
Shared fixtures for the runbook-bot test suite.

Mocking strategy: patch the queue functions and the existing sync
ingest_documents() call where they're *imported into app.main*, not
where they're defined in app.queue / app.rag. main.py does:

    from app.rag import ingest_documents, query
    from app.queue import enqueue_ingestion_job, get_job_status, ensure_consumer_group

so each name is a separate reference living in app.main's own module
namespace. Patching app.queue.X or app.rag.X would NOT affect app.main's
already-bound reference to X — you have to patch "app.main.X" instead.

We also patch these because TestClient(app) triggers FastAPI's lifespan
on startup, and lifespan() calls ingest_documents() then
ensure_consumer_group() before yielding. Without mocking both, every
test in the suite would try to hit a real vector store and real Redis
just from instantiating the client.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """
    TestClient with lifespan startup made safe for unit tests.

    Exposes the four mocks as attributes on the returned client so
    individual tests can set return_value / side_effect and make
    assertions without re-entering the patch context themselves:

        def test_something(client):
            client.mock_enqueue.return_value = "job-123"
            ...
    """
    with (
        patch("app.main.ensure_consumer_group") as mock_ensure_group,
        patch("app.main.ingest_documents") as mock_ingest_documents,
        patch("app.main.enqueue_ingestion_job") as mock_enqueue,
        patch("app.main.get_job_status") as mock_get_status,
    ):
        from app.main import app  # import after patches are active

        with TestClient(app) as test_client:
            test_client.mock_ensure_group = mock_ensure_group
            test_client.mock_ingest_documents = mock_ingest_documents
            test_client.mock_enqueue = mock_enqueue
            test_client.mock_get_status = mock_get_status
            yield test_client
