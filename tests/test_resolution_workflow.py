from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.domain import Order, OrderItem, OrderStatus, SupportTicket
from app.schemas.workflow import ResolutionPreviewRequest, ResolutionPreviewResponse
from app.services.order_rules import RuleAction, RuleCode
from app.services.policy_kb import PolicyKnowledgeBase
from app.services.resolution_workflow import ResolutionWorkflow

NOW = datetime(2026, 2, 1, 12, tzinfo=UTC)
DELIVERED_AT = NOW - timedelta(days=1)
CUSTOMER_ID = UUID("00000000-0000-0000-0000-000000000001")
ORDER_ID = UUID("00000000-0000-0000-0000-000000000002")
ITEM_ID = UUID("00000000-0000-0000-0000-000000000003")
PRODUCT_ID = UUID("00000000-0000-0000-0000-000000000004")
TICKET_ID = UUID("00000000-0000-0000-0000-000000000005")


def make_order(status: OrderStatus = OrderStatus.DELIVERED) -> Order:
    return Order(
        id=ORDER_ID,
        customer_id=CUSTOMER_ID,
        status=status,
        currency="USD",
        placed_at=NOW - timedelta(days=10),
        created_at=NOW - timedelta(days=10),
        updated_at=NOW - timedelta(days=10),
        items=[
            OrderItem(
                id=ITEM_ID,
                order_id=ORDER_ID,
                product_id=PRODUCT_ID,
                quantity=1,
                unit_price_cents=1_000,
            )
        ],
    )


def make_ticket(*, subject: str, description: str) -> SupportTicket:
    return SupportTicket(
        id=TICKET_ID,
        customer_id=CUSTOMER_ID,
        order_id=ORDER_ID,
        subject=subject,
        description=description,
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(days=1),
    )


def write_policy(path: Path, *, policy_id: str, title: str, body: str) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                f"id: {policy_id}",
                f"title: {title}",
                'version: "1"',
                "---",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )


def request_for(
    *,
    action: RuleAction,
    policy_query: str | None = None,
    damage_confirmed: bool = False,
) -> ResolutionPreviewRequest:
    return ResolutionPreviewRequest(
        action=action,
        delivered_at=DELIVERED_AT,
        damage_confirmed=damage_confirmed,
        now=NOW,
        policy_query=policy_query,
    )


def test_preview_allows_refund_and_returns_policy_matches_and_citations(
    tmp_path: Path,
) -> None:
    write_policy(
        tmp_path / "refunds.md",
        policy_id="refunds",
        title="Refund Policy",
        body="Refunds are available for delivered orders within 30 days.",
    )
    workflow = ResolutionWorkflow(PolicyKnowledgeBase(tmp_path))

    response = workflow.preview(
        make_ticket(
            subject="Refund request",
            description="Please refund this delivered order within 30 days.",
        ),
        make_order(),
        request_for(action=RuleAction.REFUND),
    )

    assert isinstance(response, ResolutionPreviewResponse)
    assert response.decision.allowed is True
    assert response.decision.code is RuleCode.ELIGIBLE
    assert response.decision.proposal_action == "refund_order"
    assert [match.metadata.id for match in response.policy_matches] == ["refunds"]
    assert response.policy_matches[0].citation
    assert response.policy_matches[0].citation.endswith("refunds.md#L7")


def test_preview_denies_replacement_without_confirmed_damage(tmp_path: Path) -> None:
    write_policy(
        tmp_path / "replacements.md",
        policy_id="replacements",
        title="Replacement Policy",
        body="Replacement requests require confirmed damage and a support ticket.",
    )
    workflow = ResolutionWorkflow(PolicyKnowledgeBase(tmp_path))

    response = workflow.preview(
        make_ticket(
            subject="Replacement request",
            description="Item arrived without visible damage.",
        ),
        make_order(),
        request_for(action=RuleAction.DAMAGED_REPLACEMENT),
    )

    assert response.decision.allowed is False
    assert response.decision.code is RuleCode.DAMAGE_CONFIRMATION_REQUIRED


def test_preview_rejects_naive_now(tmp_path: Path) -> None:
    workflow = ResolutionWorkflow(PolicyKnowledgeBase(tmp_path))

    with pytest.raises((ValidationError, ValueError), match="timezone"):
        request = ResolutionPreviewRequest(
            action=RuleAction.REFUND,
            now=datetime(2026, 2, 1, 12),
            delivered_at=DELIVERED_AT,
            damage_confirmed=False,
        )
        workflow.preview(
            make_ticket(subject="Refund request", description="Refund order."),
            make_order(),
            request,
        )


def test_explicit_policy_query_changes_retrieval(tmp_path: Path) -> None:
    write_policy(
        tmp_path / "refunds.md",
        policy_id="refunds",
        title="Refund Policy",
        body="Refunds are available for delivered orders within 30 days.",
    )
    write_policy(
        tmp_path / "replacements.md",
        policy_id="replacements",
        title="Replacement Policy",
        body="Replacement requests require confirmed damage and a support ticket.",
    )
    workflow = ResolutionWorkflow(PolicyKnowledgeBase(tmp_path))
    ticket = make_ticket(
        subject="Refund request",
        description="Please refund this delivered order.",
    )

    default_response = workflow.preview(
        ticket, make_order(), request_for(action=RuleAction.REFUND)
    )
    explicit_response = workflow.preview(
        ticket,
        make_order(),
        request_for(
            action=RuleAction.REFUND,
            policy_query="replacement confirmed damage support ticket",
        ),
    )

    assert [match.metadata.id for match in default_response.policy_matches] == [
        "refunds"
    ]
    assert [match.metadata.id for match in explicit_response.policy_matches] == [
        "replacements"
    ]
    assert all(match.citation for match in explicit_response.policy_matches)


def test_preview_uses_only_in_memory_inputs_and_does_not_write(tmp_path: Path) -> None:
    policy_path = tmp_path / "refunds.md"
    write_policy(
        policy_path,
        policy_id="refunds",
        title="Refund Policy",
        body="Refunds are available for delivered orders within 30 days.",
    )
    before_files = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    before_policy = policy_path.read_bytes()

    response = ResolutionWorkflow(PolicyKnowledgeBase(tmp_path)).preview(
        make_ticket(subject="Refund request", description="Refund order."),
        make_order(),
        request_for(action=RuleAction.REFUND),
    )

    assert response.decision.allowed is True
    assert (
        sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
        == before_files
    )
    assert policy_path.read_bytes() == before_policy
