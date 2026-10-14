"""SQLAlchemy rows for the ResolveAI domain."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.types import UTCDateTime
from app.models.domain import (
    ActionType,
    ActorType,
    AuditEventType,
    OrderStatus,
    ProposalStatus,
    TicketPriority,
    TicketStatus,
)


def enum_column(enum_type: type[Any]) -> SAEnum[Any]:
    """Store stable enum values instead of Python enum member names."""

    return SAEnum(
        enum_type,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class CustomerRow(Base):
    """Persisted customer row."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("email", name="uq_customers_email"),)

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    orders: Mapped[list["OrderRow"]] = relationship(back_populates="customer")
    tickets: Mapped[list["TicketRow"]] = relationship(back_populates="customer")


class ProductRow(Base):
    """Persisted product row."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_products_sku"),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_products_unit_price_nonnegative"
        ),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="ck_products_currency_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    order_items: Mapped[list["OrderItemRow"]] = relationship(back_populates="product")


class OrderRow(Base):
    """Persisted order row; total is derived from order items."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="ck_orders_currency_code",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[OrderStatus] = mapped_column(
        enum_column(OrderStatus), nullable=False, default=OrderStatus.PENDING
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    placed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    customer: Mapped[CustomerRow] = relationship(back_populates="orders")
    items: Mapped[list["OrderItemRow"]] = relationship(back_populates="order")
    tickets: Mapped[list["TicketRow"]] = relationship(back_populates="order")
    action_proposals: Mapped[list["ActionProposalRow"]] = relationship(
        back_populates="order"
    )


class OrderItemRow(Base):
    """Persisted order-time product price snapshot."""

    __tablename__ = "order_items"
    __table_args__ = (
        UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),
        CheckConstraint("quantity >= 1", name="ck_order_items_quantity_positive"),
        CheckConstraint(
            "unit_price_cents >= 0", name="ck_order_items_price_nonnegative"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[OrderRow] = relationship(back_populates="items")
    product: Mapped[ProductRow] = relationship(back_populates="order_items")


class TicketRow(Base):
    """Persisted support ticket row."""

    __tablename__ = "tickets"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(10_000), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        enum_column(TicketStatus), nullable=False, default=TicketStatus.OPEN
    )
    priority: Mapped[TicketPriority] = mapped_column(
        enum_column(TicketPriority), nullable=False, default=TicketPriority.NORMAL
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    customer: Mapped[CustomerRow] = relationship(back_populates="tickets")
    order: Mapped[OrderRow | None] = relationship(back_populates="tickets")
    action_proposals: Mapped[list["ActionProposalRow"]] = relationship(
        back_populates="ticket"
    )


class ActionProposalRow(Base):
    """Persisted proposed action row."""

    __tablename__ = "action_proposals"
    __table_args__ = (
        CheckConstraint(
            "action_type = 'send_message' OR order_id IS NOT NULL",
            name="ck_action_proposals_order_for_order_action",
        ),
        CheckConstraint(
            "(reviewed_at IS NULL AND reviewed_by IS NULL) OR "
            "(reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL)",
            name="ck_action_proposals_review_pair",
        ),
        CheckConstraint(
            "status != 'executed' OR executed_at IS NOT NULL",
            name="ck_action_proposals_executed_time",
        ),
        CheckConstraint(
            "status = 'executed' OR executed_at IS NULL",
            name="ck_action_proposals_no_unexecuted_time",
        ),
        CheckConstraint(
            "status != 'failed' OR failure_reason IS NOT NULL",
            name="ck_action_proposals_failure_reason",
        ),
        CheckConstraint(
            "status != 'proposed' OR reviewed_at IS NULL",
            name="ck_action_proposals_proposed_unreviewed",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    ticket_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tickets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[ActionType] = mapped_column(
        enum_column(ActionType), nullable=False
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    rationale: Mapped[str] = mapped_column(String(5_000), nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        enum_column(ProposalStatus), nullable=False, default=ProposalStatus.PROPOSED
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(5_000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    ticket: Mapped[TicketRow] = relationship(back_populates="action_proposals")
    order: Mapped[OrderRow | None] = relationship(back_populates="action_proposals")


class AuditEventRow(Base):
    """Persisted append-only audit event row."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "actor_type = 'system' OR actor_id IS NOT NULL",
            name="ck_audit_events_actor_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        enum_column(AuditEventType), nullable=False
    )
    actor_type: Mapped[ActorType] = mapped_column(
        enum_column(ActorType), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, index=True
    )
