from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    ActionProposalRow,
    AuditEventRow,
    CustomerRow,
    OrderItemRow,
    OrderRow,
    ProductRow,
    TicketRow,
)
from app.db.repositories import (
    ActionProposalRepository,
    AuditEventRepository,
    CustomerRepository,
    OrderRepository,
    TicketRepository,
)
from app.db.seed import DEMO_CUSTOMER_ID, DEMO_ORDER_ID, seed
from app.db.session import create_database_engine
from app.models.domain import (
    ActionProposal,
    ActionType,
    AuditEvent,
    AuditEventType,
    Customer,
    Order,
    OrderItem,
    SupportTicket,
)


@pytest.fixture
def engine():
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine, expire_on_commit=False) as session:
        yield session
        session.rollback()


def test_schema_has_all_domain_tables(engine) -> None:
    assert set(Base.metadata.tables) == {
        "customers",
        "products",
        "orders",
        "order_items",
        "tickets",
        "action_proposals",
        "audit_events",
    }
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1


def test_seed_round_trips_and_is_idempotent(engine) -> None:
    with Session(engine) as session, session.begin():
        seed(session)
    with Session(engine) as session, session.begin():
        seed(session)

    with Session(engine) as session:
        customer = CustomerRepository(session).get(DEMO_CUSTOMER_ID)
        order = OrderRepository(session).get(DEMO_ORDER_ID)
        assert customer is not None
        assert customer.email == "demo@example.com"
        assert customer.created_at.tzinfo is UTC
        assert order is not None
        assert order.total_cents == 2_500
        assert order.items[0].unit_price_cents == 2_500
        assert order.placed_at.tzinfo is UTC
        for model in (
            CustomerRow,
            ProductRow,
            OrderRow,
            OrderItemRow,
            TicketRow,
            ActionProposalRow,
            AuditEventRow,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 1


def test_order_lookup_is_scoped_to_customer(session) -> None:
    seed(session)
    repository = OrderRepository(session)

    assert repository.get_for_customer(DEMO_ORDER_ID, DEMO_CUSTOMER_ID) is not None
    assert repository.get_for_customer(DEMO_ORDER_ID, uuid4()) is None


def test_ticket_rejects_another_customers_order(session) -> None:
    seed(session)
    other_customer = Customer(name="Other", email="other@example.com")
    CustomerRepository(session).add(other_customer)
    ticket = SupportTicket(
        customer_id=other_customer.id,
        order_id=DEMO_ORDER_ID,
        subject="Wrong owner",
        description="Must not link to another customer's order.",
    )

    with pytest.raises(ValueError, match="customers must match"):
        TicketRepository(session).add(ticket)


def test_proposal_rejects_another_customers_ticket(session) -> None:
    seed(session)
    ticket = session.scalar(select(TicketRow))
    proposal = ActionProposal(
        ticket_id=ticket.id,
        order_id=DEMO_ORDER_ID,
        action_type=ActionType.REFUND_ORDER,
        rationale="Wrong owner must be rejected.",
    )

    with pytest.raises(ValueError, match="another customer"):
        ActionProposalRepository(session).add(proposal, uuid4())


def test_audit_nested_json_round_trips(session) -> None:
    event = AuditEvent(
        event_type=AuditEventType.CREATED,
        actor_type="system",
        entity_type="ticket",
        entity_id=uuid4(),
        data={"evidence": {"sources": ["support ticket"]}},
    )
    restored = AuditEventRepository(session).append(event)
    session.expire_all()
    row = session.get(AuditEventRow, event.id)

    assert row.data == {"evidence": {"sources": ["support ticket"]}}
    assert restored.data["evidence"]["sources"] == ("support ticket",)


def test_product_price_changes_do_not_change_order_snapshot(session) -> None:
    seed(session)
    product = session.scalar(select(ProductRow))
    product.unit_price_cents = 9_999
    session.flush()

    order = OrderRepository(session).get(DEMO_ORDER_ID)
    assert order.total_cents == 2_500


def test_database_rejects_invalid_foreign_key(session) -> None:
    now = datetime.now(UTC)
    session.add(
        OrderRow(
            id=uuid4(),
            customer_id=uuid4(),
            currency="USD",
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()


def test_database_rejects_nonpositive_quantity(session) -> None:
    seed(session)
    item = session.scalar(select(OrderItemRow))
    item.quantity = 0

    with pytest.raises(IntegrityError):
        session.flush()


def test_failed_transaction_rolls_back(engine) -> None:
    customer = Customer(name="Demo", email="rollback@example.com")
    with (
        pytest.raises(ValueError, match="product does not exist"),
        Session(engine) as session,
        session.begin(),
    ):
        CustomerRepository(session).add(customer)
        order_id = uuid4()
        order = Order(
            id=order_id,
            customer_id=customer.id,
            currency="USD",
            items=[
                OrderItem(
                    order_id=order_id,
                    product_id=uuid4(),
                    quantity=1,
                    unit_price_cents=100,
                )
            ],
        )
        OrderRepository(session).add(order)

    with Session(engine) as session:
        assert session.get(CustomerRow, customer.id) is None
