"""API-facing schemas for ResolveAI domain entities."""

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from app.models.domain import (
    ActionProposal,
    AuditEvent,
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProposalStatus,
    SupportTicket,
    TicketPriority,
    TicketStatus,
    normalize_currency,
    normalize_email,
)


class SchemaModel(BaseModel):
    """Base configuration for request and response contracts."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class CustomerCreate(SchemaModel):
    """Client fields accepted when creating a customer."""

    name: str = Field(min_length=1, max_length=200)
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return normalize_email(value)


class CustomerRead(Customer):
    """Customer response including server-owned fields."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProductCreate(SchemaModel):
    """Client fields accepted when creating a product."""

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    unit_price_cents: int = Field(ge=0, strict=True)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    is_active: bool = True

    @field_validator("currency", mode="before")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return normalize_currency(value)


class ProductRead(Product):
    """Product response including server-owned fields."""

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrderItemCreate(SchemaModel):
    """Client fields for an order item.

    Product price is looked up by the service and stored as an order-time
    snapshot. Clients cannot choose it.
    """

    product_id: UUID
    quantity: int = Field(ge=1, strict=True)


class OrderCreate(SchemaModel):
    """Client fields accepted when creating an order."""

    customer_id: UUID
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    items: list[OrderItemCreate] = Field(min_length=1)

    @field_validator("currency", mode="before")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return normalize_currency(value)

    @model_validator(mode="after")
    def validate_unique_products(self) -> "OrderCreate":
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("order items must reference unique products")
        return self


class OrderItemRead(OrderItem):
    """Order-item response that can read ORM attributes."""

    id: UUID
    model_config = ConfigDict(from_attributes=True)


class OrderRead(Order):
    """Order response including server-owned fields and derived total."""

    id: UUID
    customer_id: UUID
    status: OrderStatus
    currency: str
    items: tuple[OrderItemRead, ...] = Field(min_length=1)
    placed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupportTicketCreate(SchemaModel):
    """Client fields accepted when creating a support ticket."""

    customer_id: UUID
    order_id: UUID | None = None
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    priority: TicketPriority = TicketPriority.NORMAL


class SupportTicketCreateBody(SchemaModel):
    """Client fields for creating a ticket under a customer path."""

    order_id: UUID | None = None
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    priority: TicketPriority = TicketPriority.NORMAL


class SupportTicketRead(SupportTicket):
    """Support ticket response including lifecycle fields."""

    id: UUID
    customer_id: UUID
    order_id: UUID | None
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ActionProposalRead(ActionProposal):
    """Action proposal response including approval state."""

    id: UUID
    order_id: UUID | None
    parameters: dict[str, JsonValue]
    status: ProposalStatus
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None
    reviewed_by: UUID | None
    executed_at: datetime | None
    failure_reason: str | None
    model_config = ConfigDict(from_attributes=True)


class AuditEventRead(AuditEvent):
    """Audit event response."""

    id: UUID
    actor_id: UUID | None
    data: Mapping[str, JsonValue]
    occurred_at: datetime
    model_config = ConfigDict(from_attributes=True)
