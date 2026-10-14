"""Validated domain entities for the ResolveAI support domain."""

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    JsonValue,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def normalize_currency(value: str) -> str:
    """Normalize and validate a three-letter currency code."""

    if not isinstance(value, str):
        raise ValueError("currency must be a string")  # noqa: TRY004
    normalized = value.strip().upper()
    # shortcut: code shape only; validate supported currencies before payment integration.
    if len(normalized) != 3 or not normalized.isascii() or not normalized.isalpha():
        raise ValueError("currency must be a three-letter ASCII code")
    return normalized


def normalize_email(value: str) -> str:
    """Normalize email input before Pydantic validates its structure."""

    if not isinstance(value, str):
        raise ValueError("email must be a string")  # noqa: TRY004
    return value.strip().lower()


def _require_timezone(value: datetime) -> datetime:
    """Reject ambiguous naive timestamps and store aware values as UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC)


class OrderStatus(str, Enum):
    """Lifecycle states for an order."""

    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TicketStatus(str, Enum):
    """Lifecycle states for a support ticket."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_CUSTOMER = "pending_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, Enum):
    """Priorities used to order support work."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ActionType(str, Enum):
    """Actions that a workflow may propose."""

    REFUND_ORDER = "refund_order"
    CANCEL_ORDER = "cancel_order"
    RETURN_ORDER = "return_order"
    REPLACE_ORDER = "replace_order"
    SEND_MESSAGE = "send_message"


class ProposalStatus(str, Enum):
    """Lifecycle states for a proposed support action."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"


class ActorType(str, Enum):
    """Sources that can create or change an audit event."""

    SYSTEM = "system"
    AGENT = "agent"
    USER = "user"
    INTEGRATION = "integration"


class AuditEventType(str, Enum):
    """Kinds of changes recorded in the audit trail."""

    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class DomainModel(BaseModel):
    """Base configuration shared by validated domain objects."""

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
    )


class TimestampedModel(DomainModel):
    """Base model for entities with server-managed timestamps."""

    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _require_timezone(value)


class Customer(TimestampedModel):
    """A customer who can own support tickets and orders."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return normalize_email(value)


class Product(TimestampedModel):
    """A product that can appear in an order."""

    id: UUID = Field(default_factory=uuid4)
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    unit_price_cents: int = Field(ge=0, strict=True)
    currency: str
    is_active: bool = True

    @field_validator("currency", mode="before")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return normalize_currency(value)


class OrderItem(DomainModel):
    """A price snapshot for one product within an order."""

    id: UUID = Field(default_factory=uuid4)
    order_id: UUID
    product_id: UUID
    quantity: int = Field(ge=1, strict=True)
    unit_price_cents: int = Field(ge=0, strict=True)

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class Order(TimestampedModel):
    """An order owned by one customer."""

    id: UUID = Field(default_factory=uuid4)
    customer_id: UUID
    status: OrderStatus = OrderStatus.PENDING
    currency: str
    items: tuple[OrderItem, ...] = Field(min_length=1)
    placed_at: datetime | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @field_validator("placed_at")
    @classmethod
    def validate_placed_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_timezone(value)

    @model_validator(mode="after")
    def validate_items(self) -> "Order":
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("order items must reference unique products")
        if any(item.order_id != self.id for item in self.items):
            raise ValueError("order item order_id must match order id")
        return self

    @computed_field
    @property
    def total_cents(self) -> int:
        """Calculate total from immutable item price snapshots."""

        return sum(item.quantity * item.unit_price_cents for item in self.items)


class SupportTicket(TimestampedModel):
    """A customer support request."""

    id: UUID = Field(default_factory=uuid4)
    customer_id: UUID
    order_id: UUID | None = None
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    status: TicketStatus = TicketStatus.OPEN
    priority: TicketPriority = TicketPriority.NORMAL


class ActionProposal(TimestampedModel):
    """A proposed action that may require human approval."""

    id: UUID = Field(default_factory=uuid4)
    ticket_id: UUID
    order_id: UUID | None = None
    action_type: ActionType
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=5_000)
    status: ProposalStatus = ProposalStatus.PROPOSED
    reviewed_at: datetime | None = None
    reviewed_by: UUID | None = None
    executed_at: datetime | None = None
    failure_reason: str | None = Field(default=None, max_length=5_000)

    @field_validator("reviewed_at", "executed_at")
    @classmethod
    def validate_action_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_timezone(value)

    @model_validator(mode="after")
    def validate_status_metadata(self) -> "ActionProposal":
        if self.action_type is not ActionType.SEND_MESSAGE and self.order_id is None:
            raise ValueError("order actions require an order_id")
        if (self.reviewed_at is None) != (self.reviewed_by is None):
            raise ValueError("reviewer and review time must be supplied together")
        if self.status in {
            ProposalStatus.APPROVED,
            ProposalStatus.REJECTED,
            ProposalStatus.EXECUTED,
            ProposalStatus.FAILED,
        } and (self.reviewed_at is None or self.reviewed_by is None):
            raise ValueError("reviewed proposals require reviewer and review time")
        if self.status is ProposalStatus.PROPOSED and self.reviewed_at is not None:
            raise ValueError("proposed actions cannot already be reviewed")
        if self.status is ProposalStatus.EXECUTED and self.executed_at is None:
            raise ValueError("executed proposals require execution time")
        if self.executed_at is not None and self.status is not ProposalStatus.EXECUTED:
            raise ValueError("execution time is only valid for executed proposals")
        if self.status is ProposalStatus.FAILED and not self.failure_reason:
            raise ValueError("failed proposals require a failure reason")
        return self


class AuditEvent(DomainModel):
    """An append-only event describing a meaningful system change."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    id: UUID = Field(default_factory=uuid4)
    event_type: AuditEventType
    actor_type: ActorType
    actor_id: UUID | None = None
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: UUID
    data: Mapping[str, JsonValue] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=_utc_now)

    @field_validator("data", mode="before")
    @classmethod
    def read_data(cls, value: Any) -> Any:
        return _thaw_json(value)

    @field_validator("data", mode="after")
    @classmethod
    def freeze_data(cls, value: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return _freeze_json(value)

    @field_serializer("data")
    def serialize_data(self, value: Mapping[str, JsonValue]) -> dict[str, Any]:
        return _thaw_json(value)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        return _require_timezone(value)

    @model_validator(mode="after")
    def validate_actor(self) -> "AuditEvent":
        if self.actor_type is not ActorType.SYSTEM and self.actor_id is None:
            raise ValueError("non-system audit events require an actor_id")
        return self


def _freeze_json(value: Any) -> Any:
    """Make nested JSON data immutable for append-only audit events."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    """Convert immutable audit data back to JSON-shaped values."""

    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value
