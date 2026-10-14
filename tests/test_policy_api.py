from fastapi.testclient import TestClient

from app.main import app


def test_policy_search_returns_citations() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/policies/search",
            params={"q": "delivered 30 days", "limit": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["results"]
    assert body["results"][0]["citation"].startswith("policies/")
    assert "#L" in body["results"][0]["citation"]


def test_policy_search_blank_query_returns_empty() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/policies/search", params={"q": "   "})

    assert response.status_code == 200
    assert response.json() == {"results": []}


def test_policy_search_rejects_invalid_limit() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/policies/search", params={"q": "refund", "limit": 0}
        )

    assert response.status_code == 422
