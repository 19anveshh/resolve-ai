from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.domain import Order, OrderItem, OrderStatus
from app.services.order_rules import (
    DeliveryStatus,
    OrderFacts,
    RuleAction,
    RuleCode,
    evaluate_order_action,
    validate_delivery_date,
)

NOW = datetime(2026, 2, 1, 12, tzinfo=UTC)
CUSTOMER_ID = uuid4()


def make_order(
    status: OrderStatus,
    *,
    placed_at: datetime | None = datetime(2026, 1, 1, 12, tzinfo=UTC),
) -> Order:
    order_id = uuid4()
    return Order(
        id=order_id,
        customer_id=CUSTOMER_ID,
        status=status,
        currency="USD",
        placed_at=placed_at,
        items=[
            OrderItem(
                order_id=order_id,
                product_id=uuid4(),
                quantity=1,
                unit_price_cents=1_000,
            )
        ],
    )


def facts_for(
    order: Order,
    *,
    delivered_at: datetime | None = None,
    ticket_id: UUID | None = None,
    ticket_order_id: UUID | None = None,
    damage_confirmed: bool = False,
    customer_id=CUSTOMER_ID,
    prior_action_completed: bool = False,
) -> OrderFacts:
    return OrderFacts(
        order=order,
        customer_id=customer_id,
        delivered_at=delivered_at,
        ticket_id=ticket_id,
        ticket_order_id=ticket_order_id,
        damage_confirmed=damage_confirmed,
        prior_action_completed=prior_action_completed,
    )


@pytest.mark.parametrize("status", [OrderStatus.PENDING, OrderStatus.PROCESSING])
def test_cancellation_allows_pending_and_processing(status: OrderStatus) -> None:
    result = evaluate_order_action(
        facts_for(make_order(status, placed_at=NOW - timedelta(hours=1))),
        RuleAction.CANCEL,
        now=NOW,
    )

    assert result.allowed is True
    assert result.code is RuleCode.ELIGIBLE
    assert result.next_status is OrderStatus.CANCELLED


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
        OrderStatus.REFUNDED,
    ],
)
def test_cancellation_rejects_non_cancellable_statuses(status: OrderStatus) -> None:
    result = evaluate_order_action(
        facts_for(make_order(status)), RuleAction.CANCEL, now=NOW
    )

    assert result.allowed is False
    assert result.code is RuleCode.CANCEL_STATUS_NOT_ALLOWED


def test_cancellation_window_is_inclusive() -> None:
    placed_at = NOW - timedelta(hours=24)
    result = evaluate_order_action(
        facts_for(make_order(OrderStatus.PENDING, placed_at=placed_at)),
        RuleAction.CANCEL,
        now=NOW,
    )

    assert result.allowed is True

    expired = evaluate_order_action(
        facts_for(make_order(OrderStatus.PENDING, placed_at=placed_at)),
        RuleAction.CANCEL,
        now=NOW + timedelta(seconds=1),
    )
    assert expired.code is RuleCode.CANCELLATION_WINDOW_EXPIRED


@pytest.mark.parametrize("action", [RuleAction.REFUND, RuleAction.RETURN])
def test_post_delivery_actions_allow_exact_30_day_boundary(action: RuleAction) -> None:
    delivered_at = NOW - timedelta(days=30)
    result = evaluate_order_action(
        facts_for(make_order(OrderStatus.DELIVERED), delivered_at=delivered_at),
        action,
        now=NOW,
    )

    assert result.allowed is True

    expired = evaluate_order_action(
        facts_for(make_order(OrderStatus.DELIVERED), delivered_at=delivered_at),
        action,
        now=NOW + timedelta(seconds=1),
    )
    assert expired.allowed is False
    assert expired.code in {
        RuleCode.REFUND_WINDOW_EXPIRED,
        RuleCode.RETURN_WINDOW_EXPIRED,
    }


@pytest.mark.parametrize("action", [RuleAction.REFUND, RuleAction.RETURN])
def test_post_delivery_actions_require_delivered_order_and_date(
    action: RuleAction,
) -> None:
    wrong_status = evaluate_order_action(
        facts_for(make_order(OrderStatus.SHIPPED), delivered_at=NOW),
        action,
        now=NOW,
    )
    missing_date = evaluate_order_action(
        facts_for(make_order(OrderStatus.DELIVERED)), action, now=NOW
    )

    assert wrong_status.allowed is False
    assert missing_date.code is RuleCode.DELIVERED_AT_REQUIRED


def test_damaged_replacement_requires_ticket_matching_order_and_damage() -> None:
    order = make_order(OrderStatus.DELIVERED)
    delivered_at = NOW - timedelta(days=1)

    missing_ticket = evaluate_order_action(
        facts_for(order, delivered_at=delivered_at, damage_confirmed=True),
        RuleAction.DAMAGED_REPLACEMENT,
        now=NOW,
    )
    wrong_ticket = evaluate_order_action(
        facts_for(
            order,
            delivered_at=delivered_at,
            ticket_id=uuid4(),
            ticket_order_id=uuid4(),
            damage_confirmed=True,
        ),
        RuleAction.DAMAGED_REPLACEMENT,
        now=NOW,
    )
    missing_damage = evaluate_order_action(
        facts_for(
            order,
            delivered_at=delivered_at,
            ticket_id=uuid4(),
            ticket_order_id=order.id,
        ),
        RuleAction.DAMAGED_REPLACEMENT,
        now=NOW,
    )
    eligible = evaluate_order_action(
        facts_for(
            order,
            delivered_at=delivered_at,
            ticket_id=uuid4(),
            ticket_order_id=order.id,
            damage_confirmed=True,
        ),
        RuleAction.DAMAGED_REPLACEMENT,
        now=NOW,
    )

    assert missing_ticket.code is RuleCode.TICKET_REQUIRED
    assert wrong_ticket.code is RuleCode.TICKET_ORDER_MISMATCH
    assert missing_damage.code is RuleCode.DAMAGE_CONFIRMATION_REQUIRED
    assert eligible.allowed is True


def test_rules_reject_non_owner_and_duplicate_actions() -> None:
    order = make_order(OrderStatus.PENDING)
    not_owner = evaluate_order_action(
        facts_for(order, customer_id=uuid4()), RuleAction.CANCEL, now=NOW
    )
    duplicate = evaluate_order_action(
        facts_for(order, prior_action_completed=True), RuleAction.CANCEL, now=NOW
    )

    assert not_owner.code is RuleCode.CUSTOMER_NOT_OWNER
    assert duplicate.code is RuleCode.DUPLICATE_ACTION


def test_rules_reject_invalid_date_facts() -> None:
    order = make_order(OrderStatus.DELIVERED)
    with pytest.raises(ValidationError, match="timezone"):
        OrderFacts(
            order=order,
            customer_id=CUSTOMER_ID,
            delivered_at=datetime(2026, 1, 1),
        )

    invalid = evaluate_order_action(
        facts_for(order, delivered_at=NOW + timedelta(seconds=1)),
        RuleAction.REFUND,
        now=NOW,
    )
    assert invalid.code is RuleCode.DELIVERY_DATE_INVALID


def test_delivery_date_validation_covers_pending_overdue_and_late() -> None:
    expected = NOW
    assert validate_delivery_date(expected, now=NOW).status is DeliveryStatus.PENDING
    assert (
        validate_delivery_date(expected, now=NOW + timedelta(seconds=1)).status
        is DeliveryStatus.OVERDUE
    )
    assert (
        validate_delivery_date(
            expected,
            actual_at=NOW + timedelta(seconds=1),
            now=NOW + timedelta(seconds=2),
        ).status
        is DeliveryStatus.LATE
    )
    assert (
        validate_delivery_date(
            expected, actual_at=NOW - timedelta(seconds=1), now=NOW
        ).status
        is DeliveryStatus.ON_TIME
    )


def test_delivery_date_rejects_future_actual_and_naive_now() -> None:
    future = validate_delivery_date(NOW, actual_at=NOW + timedelta(seconds=1), now=NOW)

    assert future.valid is False
    assert future.status is DeliveryStatus.INVALID

    with pytest.raises(ValueError, match="timezone"):
        validate_delivery_date(NOW, now=datetime(2026, 2, 1, 12))
