"""Schemas for policy knowledge-base documents and search results."""

from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PolicySchemaModel(BaseModel):
    """Shared strict configuration for policy contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class PolicyFrontMatter(PolicySchemaModel):
    """Validated metadata read from a Markdown document's front matter."""

    id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    version: str | None = Field(default=None, max_length=100)
    effective_date: str | None = Field(default=None, max_length=100)

    @field_validator("id", "title")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("policy metadata cannot contain control characters")
        return value


class PolicyMetadata(PolicySchemaModel):
    """Metadata attached to one searchable policy chunk."""

    id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    version: str | None = Field(default=None, max_length=100)
    effective_date: str | None = Field(default=None, max_length=100)
    source: str = Field(min_length=1, max_length=1_000)
    section: str | None = Field(default=None, max_length=500)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    chunk_id: str = Field(min_length=1, max_length=500)

    @field_validator("source")
    @classmethod
    def require_relative_posix_source(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            value.startswith("/")
            or "\\" in value
            or ".." in path.parts
            or not path.parts
        ):
            raise ValueError("policy source must be a relative POSIX path")
        return value

    @model_validator(mode="after")
    def validate_line_range(self) -> "PolicyMetadata":
        if self.line_end < self.line_start:
            raise ValueError("policy line_end must be at least line_start")
        return self

    @property
    def policy_id(self) -> str:
        """Compatibility name for callers that use policy_id terminology."""

        return self.id

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class PolicyChunk(PolicySchemaModel):
    """One heading-aware, bounded piece of policy text."""

    text: str = Field(min_length=1, max_length=1_200)
    metadata: PolicyMetadata

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def policy_id(self) -> str:
        return self.metadata.id

    @property
    def chunk_id(self) -> str:
        return self.metadata.chunk_id

    @property
    def source(self) -> str:
        return self.metadata.source

    @property
    def citation_text(self) -> str:
        line_range = f"L{self.metadata.line_start}"
        if self.metadata.line_end != self.metadata.line_start:
            line_range += f"-L{self.metadata.line_end}"
        return f"{self.metadata.source}#{line_range}"


class PolicySearchResult(PolicyChunk):
    """A policy chunk with deterministic keyword relevance score."""

    score: int = Field(ge=1)
    citation: str = Field(min_length=1, max_length=1_200)


class PolicySearchResponse(PolicySchemaModel):
    """Bounded deterministic search response."""

    results: list[PolicySearchResult] = Field(default_factory=list)


# Explicit name for code that wants to distinguish chunk metadata from document
# front matter while retaining the shorter public name used by the service.
PolicyChunkMetadata = PolicyMetadata


__all__ = [
    "PolicyChunk",
    "PolicyChunkMetadata",
    "PolicyFrontMatter",
    "PolicyMetadata",
    "PolicySchemaModel",
    "PolicySearchResponse",
    "PolicySearchResult",
]
