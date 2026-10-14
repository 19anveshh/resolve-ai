"""Customer, order, and support-ticket endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import get_settings
from app.db.repositories import (
    CustomerRepository,
    OrderRepository,
    TicketRepository,
)
from app.models.domain import SupportTicket
from app.schemas.domain import (
    CustomerRead,
    OrderRead,
    SupportTicketCreateBody,
    SupportTicketRead,
)

settings = get_settings()
router = APIRouter(prefix=settings.api_v1_prefix, tags=["support"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _require_customer(db: Session, customer_id: UUID):
    customer = CustomerRepository(db).get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _ticket_error(error: ValueError) -> HTTPException:
    message = str(error)
    if message in {"ticket customer does not exist", "ticket order does not exist"}:
        return HTTPException(status_code=404, detail=message)
    if message == "ticket and order customers must match":
        return HTTPException(status_code=422, detail=message)
    return HTTPException(status_code=422, detail=message)


@router.get("/customers/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: UUID, db: DatabaseSession):
    """Return one customer by ID."""

    return _require_customer(db, customer_id)


@router.get("/customers/{customer_id}/orders", response_model=list[OrderRead])
def list_customer_orders(customer_id: UUID, db: DatabaseSession):
    """Return orders owned by one customer."""

    _require_customer(db, customer_id)
    return OrderRepository(db).list_for_customer(customer_id)


@router.get("/customers/{customer_id}/orders/{order_id}", response_model=OrderRead)
def get_customer_order(customer_id: UUID, order_id: UUID, db: DatabaseSession):
    """Return one order only when it belongs to the customer."""

    _require_customer(db, customer_id)
    order = OrderRepository(db).get_for_customer(order_id, customer_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post(
    "/customers/{customer_id}/tickets",
    response_model=SupportTicketRead,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_ticket(
    customer_id: UUID,
    payload: SupportTicketCreateBody,
    db: DatabaseSession,
):
    """Create a support ticket owned by the path customer."""

    try:
        with db.begin():
            _require_customer(db, customer_id)
            ticket = TicketRepository(db).add(
                SupportTicket(customer_id=customer_id, **payload.model_dump())
            )
        return ticket
    except HTTPException:
        raise
    except ValueError as error:
        raise _ticket_error(error) from error


@router.get("/customers/{customer_id}/tickets", response_model=list[SupportTicketRead])
def list_customer_tickets(customer_id: UUID, db: DatabaseSession):
    """Return tickets owned by one customer."""

    _require_customer(db, customer_id)
    return TicketRepository(db).list_for_customer(customer_id)


@router.get(
    "/customers/{customer_id}/tickets/{ticket_id}",
    response_model=SupportTicketRead,
)
def get_customer_ticket(customer_id: UUID, ticket_id: UUID, db: DatabaseSession):
    """Return one ticket only when it belongs to the customer."""

    _require_customer(db, customer_id)
    ticket = TicketRepository(db).get_for_customer(ticket_id, customer_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
