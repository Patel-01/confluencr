import time

from fastapi.testclient import TestClient

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
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"
    assert response.json()["current_time"]


def test_webhook_is_accepted_and_processed(client: TestClient) -> None:
    response = client.post("/v1/webhooks/transactions", json=PAYLOAD)

    assert response.status_code == 202
    assert response.json() == {"status": "ACCEPTED", "transaction_id": "txn_abc123"}

    transaction = _wait_for_status(client, "txn_abc123", "PROCESSED")
    assert transaction["currency"] == "INR"
    assert transaction["processed_at"] is not None


def test_duplicate_webhooks_are_idempotent(client: TestClient) -> None:
    first = client.post("/v1/webhooks/transactions", json=PAYLOAD)
    second = client.post("/v1/webhooks/transactions", json=PAYLOAD)

    assert first.status_code == 202
    assert second.status_code == 202
    transaction = _wait_for_status(client, "txn_abc123", "PROCESSED")
    assert transaction["transaction_id"] == "txn_abc123"


def test_unknown_transaction_returns_not_found(client: TestClient) -> None:
    response = client.get("/v1/transactions/does-not-exist")

    assert response.status_code == 404


def test_invalid_webhook_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/webhooks/transactions", json={**PAYLOAD, "amount": 0})

    assert response.status_code == 422

