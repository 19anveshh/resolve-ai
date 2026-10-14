"""Deterministic resolution-preview endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import get_settings
from app.db.repositories import CustomerRepository, OrderRepository, TicketRepository
from app.schemas.workflow import ResolutionPreviewRequest, ResolutionPreviewResponse
from app.services.policy_kb import PolicyKnowledgeBase
from app.services.resolution_workflow import ResolutionWorkflow

settings = get_settings()
router = APIRouter(prefix=settings.api_v1_prefix, tags=["workflow"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_resolution_workflow() -> ResolutionWorkflow:
    """Build a preview workflow from the configured policy corpus."""

    return ResolutionWorkflow(PolicyKnowledgeBase(get_settings().policy_dir))


ResolutionWorkflowDependency = Annotated[
    ResolutionWorkflow, Depends(get_resolution_workflow)
]


@router.post(
    "/customers/{customer_id}/tickets/{ticket_id}/resolution-preview",
    response_model=ResolutionPreviewResponse,
)
def preview_resolution(
    customer_id: UUID,
    ticket_id: UUID,
    payload: ResolutionPreviewRequest,
    db: DatabaseSession,
    workflow: ResolutionWorkflowDependency,
) -> ResolutionPreviewResponse:
    """Evaluate one proposed action without persisting or executing it."""

    if CustomerRepository(db).get(customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    ticket = TicketRepository(db).get_for_customer(ticket_id, customer_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.order_id is None:
        raise HTTPException(status_code=422, detail="Ticket must reference an order")

    order = OrderRepository(db).get_for_customer(ticket.order_id, customer_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return workflow.preview(ticket, order, payload)
