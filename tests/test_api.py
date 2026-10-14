from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.db.base import Base
from app.db.models import TicketRow
from app.db.repositories import CustomerRepository
from app.db.seed import (
    DEMO_CUSTOMER_ID,
    DEMO_ORDER_ID,
    DEMO_TICKET_ID,
    seed,
)
from app.db.session import create_database_engine
from app.main import app
from app.models.domain import Customer


@pytest.fixture
def api_client(tmp_path):
    engine = create_database_engine(f"sqlite:///{tmp_path / 'api.sqlite3'}")
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


def test_customer_lookup(api_client) -> None:
    client, _ = api_client

    response = client.get(f"/api/v1/customers/{DEMO_CUSTOMER_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(DEMO_CUSTOMER_ID)
    assert response.json()["email"] == "demo@example.com"


def test_customer_orders_include_snapshot_total(api_client) -> None:
    client, _ = api_client

    response = client.get(f"/api/v1/customers/{DEMO_CUSTOMER_ID}/orders")

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(DEMO_ORDER_ID)
    assert response.json()[0]["total_cents"] == 2_500
    assert response.json()[0]["items"][0]["unit_price_cents"] == 2_500


def test_order_detail_is_scoped_to_customer(api_client) -> None:
    client, engine = api_client
    other_customer_id = uuid4()
    with Session(engine) as session, session.begin():
        CustomerRepository(session).add(
            Customer(
                name="Other Customer",
                email="other-api@example.com",
                id=other_customer_id,
            )
        )

    response = client.get(
        f"/api/v1/customers/{other_customer_id}/orders/{DEMO_ORDER_ID}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"


def test_ticket_list_and_detail_are_scoped(api_client) -> None:
    client, _ = api_client

    response = client.get(f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets")
    detail = client.get(
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets/{DEMO_TICKET_ID}"
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(DEMO_TICKET_ID)
    assert detail.status_code == 200
    assert detail.json()["order_id"] == str(DEMO_ORDER_ID)


def test_create_ticket_commits_and_returns_201(api_client) -> None:
    client, engine = api_client
    payload = {
        "order_id": str(DEMO_ORDER_ID),
        "subject": "Package arrived damaged",
        "description": "Please review replacement eligibility.",
        "priority": "high",
    }

    response = client.post(
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets", json=payload
    )

    assert response.status_code == 201
    created_id = UUID(response.json()["id"])
    assert response.json()["status"] == "open"
    assert response.json()["priority"] == "high"

    with Session(engine) as session:
        row = session.get(TicketRow, created_id)
        assert row is not None
        assert row.customer_id == DEMO_CUSTOMER_ID


def test_create_ticket_rejects_server_owned_or_path_owned_fields(api_client) -> None:
    client, engine = api_client
    with Session(engine) as session:
        before = session.scalar(select(func.count()).select_from(TicketRow))

    response = client.post(
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets",
        json={
            "customer_id": str(DEMO_CUSTOMER_ID),
            "subject": "Invalid body",
            "description": "Customer must come from path.",
        },
    )

    with Session(engine) as session:
        after = session.scalar(select(func.count()).select_from(TicketRow))
    assert response.status_code == 422
    assert before == after


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/customers/{uuid4()}",
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/orders/{uuid4()}",
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets/{uuid4()}",
    ],
)
def test_unknown_resources_return_404(api_client, path: str) -> None:
    response = api_client[0].get(path)

    assert response.status_code == 404


def test_invalid_uuid_returns_422(api_client) -> None:
    response = api_client[0].get("/api/v1/customers/not-a-uuid")

    assert response.status_code == 422


def test_ticket_with_unknown_order_returns_404_and_does_not_write(api_client) -> None:
    client, engine = api_client
    before = _ticket_count(engine)
    response = client.post(
        f"/api/v1/customers/{DEMO_CUSTOMER_ID}/tickets",
        json={
            "order_id": str(uuid4()),
            "subject": "Unknown order",
            "description": "This order does not exist.",
        },
    )

    assert response.status_code == 404
    assert _ticket_count(engine) == before


def _ticket_count(engine) -> int:
    with Session(engine) as session:
        return session.query(TicketRow).count()
