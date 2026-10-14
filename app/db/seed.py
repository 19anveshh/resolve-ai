"""Deterministic local demo data for ResolveAI."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    ActionProposalRow,
    AuditEventRow,
    CustomerRow,
    OrderRow,
    ProductRow,
    TicketRow,
)
from app.db.repositories import (
    ActionProposalRepository,
    AuditEventRepository,
    CustomerRepository,
    OrderRepository,
    ProductRepository,
    TicketRepository,
)
from app.db.session import SessionLocal, engine
from app.models.domain import (
    ActionProposal,
    ActionType,
    AuditEvent,
    AuditEventType,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    SupportTicket,
    TicketPriority,
)

DEMO_CUSTOMER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEMO_PRODUCT_ID = UUID("00000000-0000-0000-0000-000000000002")
DEMO_ORDER_ID = UUID("00000000-0000-0000-0000-000000000003")
DEMO_ITEM_ID = UUID("00000000-0000-0000-0000-000000000004")
DEMO_TICKET_ID = UUID("00000000-0000-0000-0000-000000000005")
DEMO_PROPOSAL_ID = UUID("00000000-0000-0000-0000-000000000006")
DEMO_AUDIT_ID = UUID("00000000-0000-0000-0000-000000000007")
DEMO_TIMESTAMP = datetime(2026, 1, 1, 12, tzinfo=UTC)


def seed(session: Session) -> None:
    """Insert demo records once without changing existing records."""

    customer = Customer(
        id=DEMO_CUSTOMER_ID,
        name="Demo Customer",
        email="demo@example.com",
        created_at=DEMO_TIMESTAMP,
        updated_at=DEMO_TIMESTAMP,
    )
    if session.get(CustomerRow, DEMO_CUSTOMER_ID) is None:
        CustomerRepository(session).add(customer)

    product = Product(
        id=DEMO_PRODUCT_ID,
        sku="DEMO-KEYBOARD",
        name="Demo Keyboard",
        unit_price_cents=2_500,
        currency="USD",
        created_at=DEMO_TIMESTAMP,
        updated_at=DEMO_TIMESTAMP,
    )
    if session.get(ProductRow, DEMO_PRODUCT_ID) is None:
        ProductRepository(session).add(product)

    order = Order(
        id=DEMO_ORDER_ID,
        customer_id=DEMO_CUSTOMER_ID,
        status=OrderStatus.DELIVERED,
        currency="USD",
        items=[
            OrderItem(
                id=DEMO_ITEM_ID,
                order_id=DEMO_ORDER_ID,
                product_id=DEMO_PRODUCT_ID,
                quantity=1,
                unit_price_cents=2_500,
            )
        ],
        placed_at=DEMO_TIMESTAMP,
        created_at=DEMO_TIMESTAMP,
        updated_at=DEMO_TIMESTAMP,
    )
    if session.get(OrderRow, DEMO_ORDER_ID) is None:
        OrderRepository(session).add(order)

    ticket = SupportTicket(
        id=DEMO_TICKET_ID,
        customer_id=DEMO_CUSTOMER_ID,
        order_id=DEMO_ORDER_ID,
        subject="Demo replacement request",
        description="Demo ticket for local development.",
        priority=TicketPriority.HIGH,
        created_at=DEMO_TIMESTAMP,
        updated_at=DEMO_TIMESTAMP,
    )
    if session.get(TicketRow, DEMO_TICKET_ID) is None:
        TicketRepository(session).add(ticket)

    proposal = ActionProposal(
        id=DEMO_PROPOSAL_ID,
        ticket_id=DEMO_TICKET_ID,
        order_id=DEMO_ORDER_ID,
        action_type=ActionType.REPLACE_ORDER,
        rationale="Demo proposal for local development.",
        created_at=DEMO_TIMESTAMP,
        updated_at=DEMO_TIMESTAMP,
    )
    if session.get(ActionProposalRow, DEMO_PROPOSAL_ID) is None:
        ActionProposalRepository(session).add(proposal, DEMO_CUSTOMER_ID)

    audit_event = AuditEvent(
        id=DEMO_AUDIT_ID,
        event_type=AuditEventType.CREATED,
        actor_type="system",
        entity_type="action_proposal",
        entity_id=DEMO_PROPOSAL_ID,
        data={"source": "demo_seed"},
        occurred_at=DEMO_TIMESTAMP,
    )
    if session.get(AuditEventRow, DEMO_AUDIT_ID) is None:
        AuditEventRepository(session).append(audit_event)


def main() -> None:
    """Create local tables and seed deterministic records."""

    Base.metadata.create_all(bind=engine)
    with SessionLocal.begin() as session:
        seed(session)
    print("ResolveAI demo data ready.")


if __name__ == "__main__":
    main()
