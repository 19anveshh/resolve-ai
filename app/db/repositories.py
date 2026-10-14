"""Explicit repositories and mappers for the ResolveAI database."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    ActionProposalRow,
    AuditEventRow,
    CustomerRow,
    OrderItemRow,
    OrderRow,
    ProductRow,
    TicketRow,
)
from app.models.domain import (
    ActionProposal,
    AuditEvent,
    Customer,
    Order,
    OrderItem,
    Product,
    SupportTicket,
)


def _customer_from_row(row: CustomerRow) -> Customer:
    return Customer(
        id=row.id,
        name=row.name,
        email=row.email,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _product_from_row(row: ProductRow) -> Product:
    return Product(
        id=row.id,
        sku=row.sku,
        name=row.name,
        unit_price_cents=row.unit_price_cents,
        currency=row.currency,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _order_item_from_row(row: OrderItemRow) -> OrderItem:
    return OrderItem(
        id=row.id,
        order_id=row.order_id,
        product_id=row.product_id,
        quantity=row.quantity,
        unit_price_cents=row.unit_price_cents,
    )


def _order_from_row(row: OrderRow) -> Order:
    return Order(
        id=row.id,
        customer_id=row.customer_id,
        status=row.status,
        currency=row.currency,
        items=tuple(_order_item_from_row(item) for item in row.items),
        placed_at=row.placed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _ticket_from_row(row: TicketRow) -> SupportTicket:
    return SupportTicket(
        id=row.id,
        customer_id=row.customer_id,
        order_id=row.order_id,
        subject=row.subject,
        description=row.description,
        status=row.status,
        priority=row.priority,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _proposal_from_row(row: ActionProposalRow) -> ActionProposal:
    return ActionProposal(
        id=row.id,
        ticket_id=row.ticket_id,
        order_id=row.order_id,
        action_type=row.action_type,
        parameters=row.parameters,
        rationale=row.rationale,
        status=row.status,
        reviewed_at=row.reviewed_at,
        reviewed_by=row.reviewed_by,
        executed_at=row.executed_at,
        failure_reason=row.failure_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _audit_event_from_row(row: AuditEventRow) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        event_type=row.event_type,
        actor_type=row.actor_type,
        actor_id=row.actor_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        data=row.data,
        occurred_at=row.occurred_at,
    )


class CustomerRepository:
    """Persistence operations for customers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, customer: Customer) -> Customer:
        row = CustomerRow(
            id=customer.id,
            name=customer.name,
            email=str(customer.email),
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )
        self.session.add(row)
        self.session.flush()
        return _customer_from_row(row)

    def get(self, customer_id):
        row = self.session.get(CustomerRow, customer_id)
        return _customer_from_row(row) if row is not None else None


class ProductRepository:
    """Persistence operations for products."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, product: Product) -> Product:
        row = ProductRow(
            id=product.id,
            sku=product.sku,
            name=product.name,
            unit_price_cents=product.unit_price_cents,
            currency=product.currency,
            is_active=product.is_active,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
        self.session.add(row)
        self.session.flush()
        return _product_from_row(row)

    def get(self, product_id):
        row = self.session.get(ProductRow, product_id)
        return _product_from_row(row) if row is not None else None


class OrderRepository:
    """Persistence operations for orders and immutable item snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, order: Order) -> Order:
        if self.session.get(CustomerRow, order.customer_id) is None:
            raise ValueError("order customer does not exist")

        product_rows = {
            item.product_id: self.session.get(ProductRow, item.product_id)
            for item in order.items
        }
        for item in order.items:
            product = product_rows[item.product_id]
            if product is None:
                raise ValueError("order product does not exist")
            if not product.is_active:
                raise ValueError("order product is inactive")
            if product.currency != order.currency:
                raise ValueError("order and product currencies must match")

        row = OrderRow(
            id=order.id,
            customer_id=order.customer_id,
            status=order.status,
            currency=order.currency,
            placed_at=order.placed_at,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[
                OrderItemRow(
                    id=item.id,
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price_cents=item.unit_price_cents,
                )
                for item in order.items
            ],
        )
        self.session.add(row)
        self.session.flush()
        return _order_from_row(row)

    def get(self, order_id):
        row = self.session.scalar(
            select(OrderRow)
            .options(selectinload(OrderRow.items))
            .where(OrderRow.id == order_id)
        )
        return _order_from_row(row) if row is not None else None

    def get_for_customer(self, order_id, customer_id):
        row = self.session.scalar(
            select(OrderRow)
            .options(selectinload(OrderRow.items))
            .where(OrderRow.id == order_id, OrderRow.customer_id == customer_id)
        )
        return _order_from_row(row) if row is not None else None

    def list_for_customer(self, customer_id) -> list[Order]:
        rows = self.session.scalars(
            select(OrderRow)
            .options(selectinload(OrderRow.items))
            .where(OrderRow.customer_id == customer_id)
            .order_by(OrderRow.created_at.desc(), OrderRow.id.desc())
        ).all()
        return [_order_from_row(row) for row in rows]


class TicketRepository:
    """Persistence operations for customer support tickets."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, ticket: SupportTicket) -> SupportTicket:
        if self.session.get(CustomerRow, ticket.customer_id) is None:
            raise ValueError("ticket customer does not exist")
        if ticket.order_id is not None:
            order = self.session.get(OrderRow, ticket.order_id)
            if order is None:
                raise ValueError("ticket order does not exist")
            if order.customer_id != ticket.customer_id:
                raise ValueError("ticket and order customers must match")

        row = TicketRow(
            id=ticket.id,
            customer_id=ticket.customer_id,
            order_id=ticket.order_id,
            subject=ticket.subject,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )
        self.session.add(row)
        self.session.flush()
        return _ticket_from_row(row)

    def get_for_customer(self, ticket_id, customer_id):
        row = self.session.scalar(
            select(TicketRow).where(
                TicketRow.id == ticket_id,
                TicketRow.customer_id == customer_id,
            )
        )
        return _ticket_from_row(row) if row is not None else None

    def list_for_customer(self, customer_id) -> list[SupportTicket]:
        rows = self.session.scalars(
            select(TicketRow)
            .where(TicketRow.customer_id == customer_id)
            .order_by(TicketRow.created_at.desc(), TicketRow.id.desc())
        ).all()
        return [_ticket_from_row(row) for row in rows]


class ActionProposalRepository:
    """Persistence operations for proposed support actions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, proposal: ActionProposal, customer_id) -> ActionProposal:
        ticket = self.session.get(TicketRow, proposal.ticket_id)
        if ticket is None:
            raise ValueError("proposal ticket does not exist")
        if ticket.customer_id != customer_id:
            raise ValueError("proposal ticket belongs to another customer")
        if proposal.order_id is not None:
            order = self.session.get(OrderRow, proposal.order_id)
            if order is None:
                raise ValueError("proposal order does not exist")
            if order.customer_id != customer_id:
                raise ValueError("proposal order belongs to another customer")
            if ticket.order_id is not None and ticket.order_id != proposal.order_id:
                raise ValueError("proposal order must match ticket order")

        parameters = proposal.model_dump(mode="json")["parameters"]
        row = ActionProposalRow(
            id=proposal.id,
            ticket_id=proposal.ticket_id,
            order_id=proposal.order_id,
            action_type=proposal.action_type,
            parameters=parameters,
            rationale=proposal.rationale,
            status=proposal.status,
            reviewed_at=proposal.reviewed_at,
            reviewed_by=proposal.reviewed_by,
            executed_at=proposal.executed_at,
            failure_reason=proposal.failure_reason,
            created_at=proposal.created_at,
            updated_at=proposal.updated_at,
        )
        self.session.add(row)
        self.session.flush()
        return _proposal_from_row(row)

    def get_for_customer(self, proposal_id, customer_id):
        row = self.session.scalar(
            select(ActionProposalRow)
            .join(ActionProposalRow.ticket)
            .where(
                ActionProposalRow.id == proposal_id,
                TicketRow.customer_id == customer_id,
            )
        )
        return _proposal_from_row(row) if row is not None else None


class AuditEventRepository:
    """Append-only persistence operations for audit events."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, event: AuditEvent) -> AuditEvent:
        data = event.model_dump(mode="json")["data"]
        row = AuditEventRow(
            id=event.id,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            data=data,
            occurred_at=event.occurred_at,
        )
        self.session.add(row)
        self.session.flush()
        return _audit_event_from_row(row)
