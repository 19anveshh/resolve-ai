"""Deterministic order eligibility and delivery-date rules."""

from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.domain import ActionType, Order, OrderStatus


class RuleAction(str, Enum):
    """Customer-support actions evaluated by this ruleset."""

    CANCEL = "cancel"
    REFUND = "refund"
    RETURN = "return"
    DAMAGED_REPLACEMENT = "damaged_replacement"


class RuleCode(str, Enum):
    """Stable machine-readable eligibility outcomes."""

    ELIGIBLE = "eligible"
    CUSTOMER_NOT_OWNER = "customer_not_owner"
    TICKET_REQUIRED = "ticket_required"
    TICKET_ORDER_MISMATCH = "ticket_order_mismatch"
    CANCEL_STATUS_NOT_ALLOWED = "cancel_status_not_allowed"
    REFUND_STATUS_NOT_ALLOWED = "refund_status_not_allowed"
    RETURN_STATUS_NOT_ALLOWED = "return_status_not_allowed"
    REPLACEMENT_STATUS_NOT_ALLOWED = "replacement_status_not_allowed"
    PLACED_AT_REQUIRED = "placed_at_required"
    DELIVERED_AT_REQUIRED = "delivered_at_required"
    DELIVERY_DATE_INVALID = "delivery_date_invalid"
    CANCELLATION_WINDOW_EXPIRED = "cancellation_window_expired"
    REFUND_WINDOW_EXPIRED = "refund_window_expired"
    RETURN_WINDOW_EXPIRED = "return_window_expired"
    REPLACEMENT_WINDOW_EXPIRED = "replacement_window_expired"
    DAMAGE_CONFIRMATION_REQUIRED = "damage_confirmation_required"
    DUPLICATE_ACTION = "duplicate_action"


class DeliveryStatus(str, Enum):
    """Outcome of comparing promised and actual/current delivery dates."""

    ON_TIME = "on_time"
    LATE = "late"
    PENDING = "pending"
    OVERDUE = "overdue"
    INVALID = "invalid"


class RulePolicy(BaseModel):
    """Demo policy values used by deterministic rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cancellation_window: timedelta = timedelta(hours=24)
    post_delivery_window: timedelta = timedelta(days=30)


DEFAULT_POLICY = RulePolicy()


class OrderFacts(BaseModel):
    """Facts required to evaluate an order action."""

    model_config = ConfigDict(extra="forbid")

    order: Order
    customer_id: UUID
    delivered_at: datetime | None = None
    promised_delivery_at: datetime | None = None
    ticket_id: UUID | None = None
    ticket_order_id: UUID | None = None
    damage_confirmed: bool = False
    prior_action_completed: bool = False

    @field_validator("delivered_at", "promised_delivery_at")
    @classmethod
    def normalize_dates(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value)


class RuleResult(BaseModel):
    """Deterministic outcome consumed by APIs and future workflows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    code: RuleCode
    action: RuleAction
    reason: str
    proposal_action: ActionType | None = None
    next_status: OrderStatus | None = None
    requires_approval: bool = True


class DeliveryDateResult(BaseModel):
    """Result of delivery-date comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: DeliveryStatus
    valid: bool
    reason: str
    expected_at: datetime
    actual_at: datetime | None = None


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC)


def _deny(action: RuleAction, code: RuleCode, reason: str) -> RuleResult:
    return RuleResult(allowed=False, action=action, code=code, reason=reason)


def _allowed(
    action: RuleAction,
    proposal_action: ActionType,
    next_status: OrderStatus | None = None,
) -> RuleResult:
    return RuleResult(
        allowed=True,
        action=action,
        code=RuleCode.ELIGIBLE,
        reason="Action is eligible under current policy.",
        proposal_action=proposal_action,
        next_status=next_status,
    )


def _validate_facts(facts: OrderFacts, now: datetime) -> RuleResult | None:
    if facts.customer_id != facts.order.customer_id:
        return _deny(
            RuleAction.CANCEL,
            RuleCode.CUSTOMER_NOT_OWNER,
            "Customer does not own order.",
        )
    if facts.ticket_id is not None and facts.ticket_order_id != facts.order.id:
        return _deny(
            RuleAction.CANCEL,
            RuleCode.TICKET_ORDER_MISMATCH,
            "Ticket does not reference evaluated order.",
        )
    if facts.prior_action_completed:
        return _deny(
            RuleAction.CANCEL,
            RuleCode.DUPLICATE_ACTION,
            "Equivalent action was already completed.",
        )
    placed_at = facts.order.placed_at
    if placed_at is not None and placed_at > now:
        return _deny(
            RuleAction.CANCEL,
            RuleCode.DELIVERY_DATE_INVALID,
            "Order placement cannot be in the future.",
        )
    if (
        facts.promised_delivery_at is not None
        and placed_at is not None
        and facts.promised_delivery_at < placed_at
    ):
        return _deny(
            RuleAction.CANCEL,
            RuleCode.DELIVERY_DATE_INVALID,
            "Promised delivery cannot precede order placement.",
        )
    if facts.delivered_at is not None:
        if placed_at is not None and facts.delivered_at < placed_at:
            return _deny(
                RuleAction.CANCEL,
                RuleCode.DELIVERY_DATE_INVALID,
                "Delivery cannot precede order placement.",
            )
        if facts.delivered_at > now:
            return _deny(
                RuleAction.CANCEL,
                RuleCode.DELIVERY_DATE_INVALID,
                "Delivery cannot be in the future.",
            )
    return None


def evaluate_order_action(
    facts: OrderFacts,
    action: RuleAction,
    *,
    now: datetime,
    policy: RulePolicy | None = None,
) -> RuleResult:
    """Evaluate one action without database, clock, or side effects."""

    current_time = _as_utc(now)
    if current_time is None:
        raise ValueError("now must include a timezone")
    policy = policy or DEFAULT_POLICY
    invalid_facts = _validate_facts(facts, current_time)
    if invalid_facts is not None:
        return invalid_facts.model_copy(update={"action": action})

    order = facts.order
    if action is RuleAction.CANCEL:
        if order.status not in {OrderStatus.PENDING, OrderStatus.PROCESSING}:
            return _deny(
                action,
                RuleCode.CANCEL_STATUS_NOT_ALLOWED,
                "Only pending or processing orders can be cancelled.",
            )
        if order.placed_at is None:
            return _deny(
                action, RuleCode.PLACED_AT_REQUIRED, "Order placement date is required."
            )
        if current_time > order.placed_at + policy.cancellation_window:
            return _deny(
                action,
                RuleCode.CANCELLATION_WINDOW_EXPIRED,
                "Cancellation window has expired.",
            )
        return _allowed(action, ActionType.CANCEL_ORDER, OrderStatus.CANCELLED)

    if action is RuleAction.REFUND:
        if order.status is not OrderStatus.DELIVERED:
            return _deny(
                action,
                RuleCode.REFUND_STATUS_NOT_ALLOWED,
                "Only delivered orders can be refunded.",
            )
        if facts.delivered_at is None:
            return _deny(
                action, RuleCode.DELIVERED_AT_REQUIRED, "Delivery date is required."
            )
        if current_time > facts.delivered_at + policy.post_delivery_window:
            return _deny(
                action, RuleCode.REFUND_WINDOW_EXPIRED, "Refund window has expired."
            )
        return _allowed(action, ActionType.REFUND_ORDER, OrderStatus.REFUNDED)

    if action is RuleAction.RETURN:
        if order.status is not OrderStatus.DELIVERED:
            return _deny(
                action,
                RuleCode.RETURN_STATUS_NOT_ALLOWED,
                "Only delivered orders can be returned.",
            )
        if facts.delivered_at is None:
            return _deny(
                action, RuleCode.DELIVERED_AT_REQUIRED, "Delivery date is required."
            )
        if current_time > facts.delivered_at + policy.post_delivery_window:
            return _deny(
                action, RuleCode.RETURN_WINDOW_EXPIRED, "Return window has expired."
            )
        return _allowed(action, ActionType.RETURN_ORDER)

    if order.status is not OrderStatus.DELIVERED:
        return _deny(
            action,
            RuleCode.REPLACEMENT_STATUS_NOT_ALLOWED,
            "Only delivered orders can receive damaged-item replacements.",
        )
    if facts.ticket_id is None:
        return _deny(action, RuleCode.TICKET_REQUIRED, "A support ticket is required.")
    if not facts.damage_confirmed:
        return _deny(
            action,
            RuleCode.DAMAGE_CONFIRMATION_REQUIRED,
            "Confirmed damage evidence is required.",
        )
    if facts.delivered_at is None:
        return _deny(
            action, RuleCode.DELIVERED_AT_REQUIRED, "Delivery date is required."
        )
    if current_time > facts.delivered_at + policy.post_delivery_window:
        return _deny(
            action,
            RuleCode.REPLACEMENT_WINDOW_EXPIRED,
            "Replacement window has expired.",
        )
    return _allowed(action, ActionType.REPLACE_ORDER)


def validate_delivery_date(
    expected_at: datetime,
    *,
    actual_at: datetime | None = None,
    now: datetime,
) -> DeliveryDateResult:
    """Classify delivery timing using explicit, timezone-aware timestamps."""

    expected = _as_utc(expected_at)
    actual = _as_utc(actual_at)
    current_time = _as_utc(now)
    if expected is None or current_time is None:
        raise ValueError("expected_at and now must include a timezone")
    if actual is not None and actual > current_time:
        return DeliveryDateResult(
            status=DeliveryStatus.INVALID,
            valid=False,
            reason="Actual delivery cannot be in the future.",
            expected_at=expected,
            actual_at=actual,
        )
    if actual is not None:
        on_time = actual <= expected
        return DeliveryDateResult(
            status=DeliveryStatus.ON_TIME if on_time else DeliveryStatus.LATE,
            valid=True,
            reason="Delivery met promised date."
            if on_time
            else "Delivery missed promised date.",
            expected_at=expected,
            actual_at=actual,
        )
    overdue = current_time > expected
    return DeliveryDateResult(
        status=DeliveryStatus.OVERDUE if overdue else DeliveryStatus.PENDING,
        valid=True,
        reason="Promised date has passed."
        if overdue
        else "Delivery is still within promise.",
        expected_at=expected,
    )
