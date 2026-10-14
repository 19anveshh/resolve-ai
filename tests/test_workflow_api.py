from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.base import Base
from app.db.seed import DEMO_CUSTOMER_ID, DEMO_ORDER_ID, DEMO_TICKET_ID, seed
from app.db.session import create_database_engine
from app.main import app


@pytest.fixture
def workflow_client(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'workflow.sqlite3'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        seed(session)

    def override_db():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def _preview_payload(action: str, *, damage_confirmed: bool = False) -> dict:
    return {
        "action": action,
        "now": datetime(2026, 2, 1, 12, tzinfo=UTC).isoformat(),
        "delivered_at": datetime(2026, 1, 15, 12, tzinfo=UTC).isoformat(),
        "damage_confirmed": damage_confirmed,
    }


def test_resolution_preview_returns_eligible_decision_and_policy_citations(
    workflow_client,
) -> None:
    client, _ = workflow_client

    response = client.post(
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets/{DEMO_TICKET_ID}/resolution-preview",
        json=_preview_payload("refund"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == str(DEMO_TICKET_ID)
    assert body["order_id"] == str(DEMO_ORDER_ID)
    assert body["decision"]["allowed"] is True
    assert body["decision"]["code"] == "eligible"
    assert body["policy_matches"]
    assert body["policy_matches"][0]["citation"].startswith("policies/")


def test_resolution_preview_denies_unconfirmed_replacement(workflow_client) -> None:
    response = workflow_client[0].post(
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets/{DEMO_TICKET_ID}/resolution-preview",
        json=_preview_payload("damaged_replacement"),
    )

    assert response.status_code == 200
    assert response.json()["decision"]["code"] == "damage_confirmation_required"


def test_resolution_preview_does_not_write_proposals(workflow_client) -> None:
    client, engine = workflow_client

    response = client.post(
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets/{DEMO_TICKET_ID}/resolution-preview",
        json=_preview_payload("refund"),
    )

    assert response.status_code == 200
    with Session(engine) as session:
        assert session.query(Base.metadata.tables["action_proposals"]).count() == 1
