"""Deterministic resolution preview workflow."""

from app.models.domain import Order, SupportTicket
from app.schemas.workflow import ResolutionPreviewRequest, ResolutionPreviewResponse
from app.services.order_rules import OrderFacts, evaluate_order_action
from app.services.policy_kb import PolicyKnowledgeBase


class ResolutionWorkflow:
    """Build a resolution preview without persistence or clock access."""

    def __init__(self, policy_kb: PolicyKnowledgeBase) -> None:
        self.policy_kb = policy_kb

    def preview(
        self,
        ticket: SupportTicket,
        order: Order,
        request: ResolutionPreviewRequest,
    ) -> ResolutionPreviewResponse:
        """Evaluate requested action and return matching policy context."""

        facts = OrderFacts(
            order=order,
            customer_id=ticket.customer_id,
            delivered_at=request.delivered_at,
            ticket_id=ticket.id,
            ticket_order_id=ticket.order_id,
            damage_confirmed=request.damage_confirmed,
        )
        decision = evaluate_order_action(
            facts,
            request.action,
            now=request.now,
        )
        policy_query = (
            request.policy_query
            or {
                "cancel": "cancel",
                "refund": "refunds",
                "return": "returns",
                "damaged_replacement": "replacement damage",
            }[request.action.value]
        )
        policy_matches = self.policy_kb.search(policy_query, limit=3).results

        return ResolutionPreviewResponse(
            ticket_id=ticket.id,
            order_id=order.id,
            action=request.action,
            decision=decision,
            policy_matches=policy_matches,
        )
