import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from confluencr.core.config import Settings
from confluencr.core.database import create_database_engine, create_session_factory
from confluencr.domain.transaction import Transaction
from confluencr.infrastructure.persistence.repositories import SqlAlchemyTransactionRepository
from confluencr.presentation.app import create_app

PAYLOAD = {
    "transaction_id": "txn_abc123",
    "source_account": "acc_user_789",
    "destination_account": "acc_merchant_456",
    "amount": 1500,
    "currency": "INR",
}


def _wait_for_status(client: TestClient, transaction_id: str, expected: str) -> dict:
    for _ in range(50):
        response = client.get(f"/v1/transactions/{transaction_id}")
        if response.status_code == 200 and response.json()[0]["status"] == expected:
            return response.json()[0]
        time.sleep(0.01)
    raise AssertionError(f"Transaction did not reach {expected}")


def test_health_check(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"
    assert response.json()["current_time"]

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"
    assert response.json()["current_time"]


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "frontend/dist/index.html").is_file(),
    reason="frontend production bundle is built separately",
)
def test_browser_root_serves_frontend(client: TestClient) -> None:
    response = client.get("/", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert "Transaction Console" in response.text


def test_webhook_is_accepted_within_500ms(client: TestClient) -> None:
    started_at = time.perf_counter()
    response = client.post(
        "/v1/webhooks/transactions",
        json={**PAYLOAD, "transaction_id": "txn_latency"},
    )
    elapsed_seconds = time.perf_counter() - started_at

    assert response.status_code == 202
    assert elapsed_seconds < 0.5


def test_webhook_is_accepted_and_processed(client: TestClient) -> None:
    response = client.post("/v1/webhooks/transactions", json=PAYLOAD)

    assert response.status_code == 202
    assert response.json() == {"status": "ACCEPTED", "transaction_id": "txn_abc123"}

    transaction = _wait_for_status(client, "txn_abc123", "PROCESSED")
    assert transaction["currency"] == "INR"
    assert transaction["processed_at"] is not None


def test_startup_recovers_persisted_unclaimed_transaction(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'recovery.sqlite3'}"
    settings = Settings(
        database_url=database_url,
        processing_delay_seconds=0,
        worker_max_workers=1,
    )
    migration_config = Config("alembic.ini")
    migration_config.attributes["database_url"] = database_url
    command.upgrade(migration_config, "head")

    engine = create_database_engine(database_url)
    repository = SqlAlchemyTransactionRepository(create_session_factory(engine)())
    repository.create_if_absent(
        Transaction.start(
            transaction_id="txn_recovered",
            source_account="source",
            destination_account="destination",
            amount=1500,
            currency="INR",
        )
    )
    repository.close()
    engine.dispose()

    app = create_app(settings)
    with TestClient(app) as recovered_client:
        transaction = _wait_for_status(recovered_client, "txn_recovered", "PROCESSED")

    assert transaction["status"] == "PROCESSED"


def test_duplicate_webhooks_are_idempotent(client: TestClient) -> None:
    first = client.post("/v1/webhooks/transactions", json=PAYLOAD)
    conflicting_payload = {**PAYLOAD, "amount": 99999, "source_account": "acc_changed"}
    second = client.post("/v1/webhooks/transactions", json=conflicting_payload)

    assert first.status_code == 202
    assert second.status_code == 202
    transaction = _wait_for_status(client, "txn_abc123", "PROCESSED")
    assert transaction["transaction_id"] == "txn_abc123"
    assert transaction["amount"] == "1500.00"
    assert transaction["source_account"] == PAYLOAD["source_account"]


def test_unknown_transaction_returns_not_found(client: TestClient) -> None:
    response = client.get("/v1/transactions/does-not-exist")

    assert response.status_code == 404


def test_invalid_webhook_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/webhooks/transactions", json={**PAYLOAD, "amount": 0})

    assert response.status_code == 422


def test_session_summary_tracks_business_api_calls(client: TestClient) -> None:
    session_id = "00000000-0000-0000-0000-000000000001"
    headers = {"X-Session-ID": session_id}

    response = client.post(
        "/v1/webhooks/transactions",
        json={**PAYLOAD, "transaction_id": "txn_session_tracking"},
        headers=headers,
    )

    assert response.status_code == 202
    summary = None
    for _ in range(50):
        summary_response = client.get("/v1/session/summary", headers=headers)
        assert summary_response.status_code == 200
        summary = summary_response.json()
        if summary["total_api_calls"] >= 1:
            break
        time.sleep(0.01)

    assert summary is not None
    assert summary["session_id"] == session_id
    assert summary["total_api_calls"] >= 1
    assert summary["recent_activity"][0]["path"] == "/v1/webhooks/transactions"


def test_session_summary_counts_concurrent_api_calls_without_lost_updates(
    client: TestClient,
) -> None:
    session_id = "00000000-0000-0000-0000-000000000002"
    headers = {"X-Session-ID": session_id}
    request_count = 12

    with ThreadPoolExecutor(max_workers=request_count) as executor:
        responses = list(
            executor.map(
                lambda index: client.get(
                    f"/v1/transactions/missing-{index}", headers=headers
                ),
                range(request_count),
            )
        )

    assert all(response.status_code == 404 for response in responses)
    summary = None
    for _ in range(100):
        summary_response = client.get("/v1/session/summary", headers=headers)
        assert summary_response.status_code == 200
        summary = summary_response.json()
        if summary["total_api_calls"] == request_count:
            break
        time.sleep(0.02)

    assert summary is not None
    assert summary["total_api_calls"] == request_count

