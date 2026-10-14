import json
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.domain import (
    ActionProposal,
    ActionType,
    ActorType,
    AuditEvent,
    AuditEventType,
    Customer,
    DomainModel,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProposalStatus,
    SupportTicket,
    TicketPriority,
    TicketStatus,
)
from app.schemas.domain import (
    ActionProposalRead,
    AuditEventRead,
    CustomerCreate,
    CustomerRead,
    OrderCreate,
    OrderItemRead,
    OrderRead,
    ProductRead,
    SupportTicketRead,
)


@pytest.fixture
def entities() -> dict[str, DomainModel]:
    customer = Customer(name="Demo Customer", email="demo@example.com")
    product = Product(
        sku="KEYBOARD-1", name="Keyboard", unit_price_cents=2_500, currency="USD"
    )
    order_id = uuid4()
    item = OrderItem(
        order_id=order_id,
        product_id=product.id,
        quantity=2,
        unit_price_cents=product.unit_price_cents,
    )
    order = Order(id=order_id, customer_id=customer.id, currency="USD", items=[item])
    ticket = SupportTicket(
        customer_id=customer.id,
        order_id=order.id,
        subject="Damaged item",
        description="Keyboard arrived damaged.",
    )
    proposal = ActionProposal(
        ticket_id=ticket.id,
        order_id=order.id,
        action_type=ActionType.REPLACE_ORDER,
        rationale="Request a replacement review.",
    )
    event = AuditEvent(
        event_type=AuditEventType.CREATED,
        actor_type=ActorType.SYSTEM,
        entity_type="action_proposal",
        entity_id=proposal.id,
        data={"evidence": {"sources": ["support ticket"]}},
    )
    return {
        "customer": customer,
        "product": product,
        "item": item,
        "order": order,
        "ticket": ticket,
        "proposal": proposal,
        "audit": event,
    }


def test_customer_normalizes_name_and_email() -> None:
    customer = Customer(name="  Anvesh  ", email=" SUPPORT@EXAMPLE.COM ")

    assert customer.name == "Anvesh"
    assert str(customer.email) == "support@example.com"
    assert customer.created_at.tzinfo is not None


def test_product_normalizes_currency_and_rejects_negative_price() -> None:
    product = Product(
        sku="SKU-1",
        name="Keyboard",
        unit_price_cents=2_500,
        currency="usd",
    )

    assert product.currency == "USD"
    assert product.is_active is True

    with pytest.raises(ValidationError):
        Product(
            sku="SKU-2",
            name="Mouse",
            unit_price_cents=-1,
            currency="USD",
        )


def test_order_calculates_total_from_item_price_snapshots() -> None:
    order_id = uuid4()
    order = Order(
        id=order_id,
        customer_id=uuid4(),
        currency="USD",
        items=[
            OrderItem(
                order_id=order_id,
                product_id=uuid4(),
                quantity=2,
                unit_price_cents=1_500,
            ),
            OrderItem(
                order_id=order_id,
                product_id=uuid4(),
                quantity=1,
                unit_price_cents=2_000,
            ),
        ],
    )

    assert order.total_cents == 5_000


def test_order_rejects_duplicate_products() -> None:
    order_id = uuid4()
    product_id = uuid4()
    item = {
        "order_id": order_id,
        "product_id": product_id,
        "quantity": 1,
        "unit_price_cents": 100,
    }

    with pytest.raises(ValidationError, match="unique products"):
        Order(
            id=order_id,
            customer_id=uuid4(),
            currency="USD",
            items=[OrderItem(**item), OrderItem(**item)],
        )


def test_order_rejects_item_from_another_order() -> None:
    with pytest.raises(ValidationError, match="order_id"):
        Order(
            id=uuid4(),
            customer_id=uuid4(),
            currency="USD",
            items=[
                OrderItem(
                    order_id=uuid4(),
                    product_id=uuid4(),
                    quantity=1,
                    unit_price_cents=100,
                )
            ],
        )


def test_ticket_proposal_and_audit_event_have_explicit_types() -> None:
    ticket = SupportTicket(
        customer_id=uuid4(),
        subject="Damaged item",
        description="Package arrived damaged.",
        priority=TicketPriority.HIGH,
    )
    proposal = ActionProposal(
        ticket_id=ticket.id,
        order_id=uuid4(),
        action_type=ActionType.REPLACE_ORDER,
        rationale="Replacement policy applies.",
    )
    audit_event = AuditEvent(
        event_type=AuditEventType.CREATED,
        actor_type=ActorType.SYSTEM,
        entity_type="action_proposal",
        entity_id=proposal.id,
    )

    assert ticket.priority is TicketPriority.HIGH
    assert proposal.status is ProposalStatus.PROPOSED
    assert audit_event.occurred_at.tzinfo is not None


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Customer(
            name="Anvesh",
            email="support@example.com",
            created_at=datetime(2026, 1, 1),
        )


def test_create_schemas_exclude_server_owned_fields() -> None:
    customer = CustomerCreate(
        name="Anvesh",
        email="support@example.com",
    )
    order = OrderCreate(
        customer_id=uuid4(),
        currency="usd",
        items=[{"product_id": uuid4(), "quantity": 1}],
    )

    assert customer.email == "support@example.com"
    assert order.currency == "USD"

    with pytest.raises(ValidationError):
        CustomerCreate(
            name="Anvesh",
            email="support@example.com",
            id=uuid4(),
        )


def test_mutable_defaults_are_not_shared() -> None:
    first = ActionProposal(
        ticket_id=uuid4(),
        action_type=ActionType.SEND_MESSAGE,
        rationale="Send order update.",
    )
    second = ActionProposal(
        ticket_id=uuid4(),
        action_type=ActionType.SEND_MESSAGE,
        rationale="Send order update.",
    )

    first.parameters["message"] = "Your order shipped."

    assert second.parameters == {}


def test_domain_relationships_and_defaults(entities: dict[str, DomainModel]) -> None:
    assert entities["order"].customer_id == entities["customer"].id
    assert entities["order"].status is OrderStatus.PENDING
    assert entities["order"].items[0].product_id == entities["product"].id
    assert entities["ticket"].customer_id == entities["customer"].id
    assert entities["ticket"].status is TicketStatus.OPEN
    assert entities["proposal"].ticket_id == entities["ticket"].id
    assert len({entity.id for entity in entities.values()}) == 7


@pytest.mark.parametrize(
    ("entity_name", "field", "value"),
    [
        ("customer", "name", " "),
        ("customer", "name", "x" * 201),
        ("customer", "email", "not-an-email"),
        ("customer", "email", None),
        ("customer", "email", 123),
        ("customer", "id", "not-a-uuid"),
        ("product", "sku", ""),
        ("product", "sku", "x" * 65),
        ("product", "name", " "),
        ("product", "unit_price_cents", -1),
        ("product", "unit_price_cents", 1.5),
        ("product", "unit_price_cents", True),
        ("product", "currency", "US"),
        ("product", "currency", "US1"),
        ("product", "currency", "€UR"),
        ("product", "currency", None),
        ("item", "quantity", 0),
        ("item", "quantity", -1),
        ("item", "quantity", 1.5),
        ("item", "quantity", True),
        ("item", "quantity", "2"),
        ("item", "unit_price_cents", -1),
        ("item", "unit_price_cents", 2.0),
        ("order", "customer_id", None),
        ("order", "status", "invalid"),
        ("order", "items", []),
        ("ticket", "subject", " "),
        ("ticket", "description", ""),
        ("ticket", "description", "x" * 10_001),
        ("ticket", "priority", "invalid"),
        ("ticket", "status", "invalid"),
        ("proposal", "rationale", " "),
        ("proposal", "action_type", "approve_everything"),
        ("proposal", "status", "invalid"),
        ("audit", "entity_type", " "),
        ("audit", "event_type", "invalid"),
        ("audit", "actor_type", "invalid"),
    ],
)
def test_invalid_domain_fields(
    entities: dict[str, DomainModel], entity_name: str, field: str, value: Any
) -> None:
    entity = entities[entity_name]
    payload = entity.model_dump(round_trip=True)
    payload[field] = value

    with pytest.raises(ValidationError) as error:
        type(entity).model_validate(payload)

    assert any(entry["loc"] == (field,) for entry in error.value.errors())


@pytest.mark.parametrize(
    "entity_name",
    ["customer", "product", "item", "order", "ticket", "proposal", "audit"],
)
def test_domain_json_round_trip(
    entities: dict[str, DomainModel], entity_name: str
) -> None:
    entity = entities[entity_name]
    restored = type(entity).model_validate_json(entity.model_dump_json(round_trip=True))

    assert restored == entity
    with pytest.raises(ValidationError) as error:
        type(entity).model_validate(
            {**entity.model_dump(round_trip=True), "unknown": True}
        )
    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("entity_name", "field"),
    [
        ("customer", "created_at"),
        ("customer", "updated_at"),
        ("order", "placed_at"),
        ("proposal", "reviewed_at"),
        ("proposal", "executed_at"),
        ("audit", "occurred_at"),
    ],
)
def test_all_timestamp_validators_reject_naive_values(
    entities: dict[str, DomainModel], entity_name: str, field: str
) -> None:
    entity = entities[entity_name]
    payload = entity.model_dump(round_trip=True)
    payload[field] = datetime(2026, 1, 1)

    with pytest.raises(ValidationError) as error:
        type(entity).model_validate(payload)

    assert error.value.errors()[0]["loc"] == (field,)


def test_timestamps_normalize_to_utc() -> None:
    timestamp = datetime(
        2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )
    customer = Customer(
        name="Demo",
        email="demo@example.com",
        created_at=timestamp,
        updated_at=timestamp,
    )

    assert customer.created_at == datetime(2026, 1, 1, 6, 30, tzinfo=UTC)
    assert customer.created_at.tzinfo is UTC


def test_order_snapshots_cannot_be_mutated(entities: dict[str, DomainModel]) -> None:
    order = entities["order"]
    original_total = order.total_cents

    with pytest.raises(AttributeError):
        order.items.append(order.items[0])
    with pytest.raises(TypeError):
        order.items[0] = order.items[0]
    with pytest.raises(ValidationError):
        order.items[0].quantity = 0
    with pytest.raises(ValidationError):
        order.items = ()

    assert order.total_cents == original_total


def test_audit_events_and_nested_evidence_cannot_be_mutated(
    entities: dict[str, DomainModel],
) -> None:
    event = entities["audit"]

    with pytest.raises(ValidationError):
        event.event_type = AuditEventType.UPDATED
    with pytest.raises(TypeError):
        event.data["evidence"]["sources"][0] = "changed"
    with pytest.raises(TypeError):
        event.data["evidence"]["new"] = "changed"
    with pytest.raises(TypeError):
        AuditEvent(
            event_type=AuditEventType.CREATED,
            actor_type=ActorType.SYSTEM,
            entity_type="ticket",
            entity_id=uuid4(),
        ).data["new"] = "changed"

    assert json.loads(event.model_dump_json())["data"] == {
        "evidence": {"sources": ["support ticket"]}
    }


def test_proposal_status_requires_matching_review_metadata() -> None:
    common = {
        "ticket_id": uuid4(),
        "order_id": uuid4(),
        "action_type": ActionType.REFUND_ORDER,
        "rationale": "Refund is allowed by policy.",
    }

    with pytest.raises(ValidationError, match="reviewed proposals"):
        ActionProposal(**common, status=ProposalStatus.APPROVED)
    with pytest.raises(ValidationError, match="execution time"):
        ActionProposal(
            **common,
            status=ProposalStatus.EXECUTED,
            reviewed_at=datetime.now(UTC),
            reviewed_by=uuid4(),
        )
    with pytest.raises(ValidationError, match="failure reason"):
        ActionProposal(
            **common,
            status=ProposalStatus.FAILED,
            reviewed_at=datetime.now(UTC),
            reviewed_by=uuid4(),
        )

    approved = ActionProposal(
        **common,
        status=ProposalStatus.APPROVED,
        reviewed_at=datetime.now(UTC),
        reviewed_by=uuid4(),
    )
    assert approved.status is ProposalStatus.APPROVED


def test_action_parameters_accept_only_json_values() -> None:
    with pytest.raises(ValidationError):
        ActionProposal(
            ticket_id=uuid4(),
            action_type=ActionType.SEND_MESSAGE,
            rationale="Send status update.",
            parameters={"payload": object()},
        )

    proposal = ActionProposal(
        ticket_id=uuid4(),
        action_type=ActionType.SEND_MESSAGE,
        rationale="Send status update.",
        parameters={"payload": {"priority": "high", "attempt": 1}},
    )
    assert json.loads(proposal.model_dump_json())["parameters"] == {
        "payload": {"priority": "high", "attempt": 1}
    }


READ_SCHEMAS = [
    ("customer", CustomerRead),
    ("product", ProductRead),
    ("item", OrderItemRead),
    ("order", OrderRead),
    ("ticket", SupportTicketRead),
    ("proposal", ActionProposalRead),
    ("audit", AuditEventRead),
]


@pytest.mark.parametrize(("entity_name", "schema"), READ_SCHEMAS)
def test_read_schemas_require_identity_and_load_attributes(
    entities: dict[str, DomainModel], entity_name: str, schema: type[DomainModel]
) -> None:
    payload = entities[entity_name].model_dump(round_trip=True)
    if entity_name == "order":
        payload["items"] = [SimpleNamespace(**item) for item in payload["items"]]
    response = schema.model_validate(SimpleNamespace(**payload))

    assert response.id == entities[entity_name].id
    assert json.loads(response.model_dump_json())["id"] == str(response.id)

    del payload["id"]
    with pytest.raises(ValidationError) as error:
        schema.model_validate(SimpleNamespace(**payload))
    assert error.value.errors()[0]["loc"] == ("id",)
    assert schema.model_fields["id"].is_required()


def test_order_response_serializes_derived_total(
    entities: dict[str, DomainModel],
) -> None:
    response = OrderRead.model_validate(entities["order"])

    assert response.model_dump()["total_cents"] == 5_000
    assert json.loads(response.model_dump_json())["total_cents"] == 5_000
    assert (
        OrderRead.model_json_schema(mode="serialization")["properties"]["total_cents"][
            "readOnly"
        ]
        is True
    )
