"""Schemas for deterministic resolution workflow previews."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.domain import SchemaModel
from app.schemas.policy import PolicySearchResult
from app.services.order_rules import RuleAction, RuleResult


class ResolutionPreviewRequest(SchemaModel):
    """Inputs for one deterministic resolution preview."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    action: RuleAction
    now: datetime
    delivered_at: datetime | None = None
    damage_confirmed: bool = False
    policy_query: str | None = Field(default=None, max_length=200)

    @field_validator("now", "delivered_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must include a timezone")
        return value.astimezone(UTC)


class ResolutionPreviewResponse(SchemaModel):
    """Immutable result of one deterministic resolution preview."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    ticket_id: UUID
    order_id: UUID
    action: RuleAction
    decision: RuleResult
    policy_matches: list[PolicySearchResult]
