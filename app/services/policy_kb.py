"""Dependency-free Markdown policy knowledge base."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Final

from app.schemas.policy import (
    PolicyChunk,
    PolicyFrontMatter,
    PolicyMetadata,
    PolicySearchResponse,
    PolicySearchResult,
)

MAX_CHUNK_CHARS: Final = 1_200
MAX_SEARCH_RESULTS: Final = 1_200
_FRONT_MATTER_KEYS: Final = frozenset({"id", "title", "version", "effective_date"})
_HEADING_RE: Final = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_TOKEN_RE: Final = re.compile(r"\w+", re.UNICODE)
_SECRET_ASSIGNMENT_RE: Final = re.compile(
    r"^\s*(?:[-*+>]\s+|#{1,6}\s+)?(?:[A-Za-z_][A-Za-z0-9-]*[_-])?"
    r"(?:api[_-]?key|access[_-]?token|auth[_-]?token|authorization|"
    r"client[_-]?secret|credential|password|passwd|private[_-]?key|"
    r"secret(?:[_-]?key)?|token)(?:[_-][A-Za-z0-9_-]*)?\s*[:=]\s*.+$",
    re.IGNORECASE,
)
_REDACTED: Final = "[REDACTED]"


class PolicyCorpusError(ValueError):
    """Raised when a corpus document cannot satisfy its policy contract."""


class PolicyKnowledgeBase:
    """Load and search Markdown policies from one configurable directory."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def load(self) -> list[PolicyChunk]:
        """Return deterministic chunks from every safe Markdown file."""

        return load_policy_corpus(self.directory)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> PolicySearchResponse:
        """Search current corpus contents using case-insensitive whole tokens."""

        return PolicySearchResponse(
            results=search_policy_corpus(self.directory, query, limit=limit)
        )


def load_policy_corpus(directory: str | Path) -> list[PolicyChunk]:
    """Load sorted Markdown policy files beneath ``directory``.

    Missing or non-directory roots are valid empty corpora. Invalid documents
    fail closed instead of becoming partially searchable.
    """

    root = Path(directory)
    if not root.is_dir():
        return []
    root = root.resolve()

    files: list[tuple[str, Path]] = []
    for candidate in root.rglob("*.md"):
        try:
            resolved = candidate.resolve()
            relative = candidate.relative_to(root)
            resolved.relative_to(root)
        except (OSError, RuntimeError, ValueError):
            continue
        source = (Path(root.name) / relative).as_posix()
        if not source or source.startswith("/") or ".." in Path(source).parts:
            continue
        if candidate.is_file():
            files.append((source, resolved))

    files.sort(key=lambda item: item[0])
    chunks: list[PolicyChunk] = []
    seen_ids: dict[str, str] = {}
    for source, path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue

        try:
            front_matter, body = _parse_front_matter(text, source)
        except PolicyCorpusError:
            continue
        previous_source = seen_ids.get(front_matter.id)
        if previous_source is not None:
            continue
        seen_ids[front_matter.id] = source
        chunks.extend(_chunk_document(front_matter, source, body))
    return chunks


def search_policy_corpus(
    directory: str | Path,
    query: str,
    *,
    limit: int = 10,
) -> list[PolicySearchResult]:
    """Search corpus chunks, ranking relevance then source and chunk ID."""

    if not query or not query.strip():
        return []
    if limit < 0:
        raise ValueError("limit must be non-negative")
    limit = min(limit, MAX_SEARCH_RESULTS)

    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    results: list[PolicySearchResult] = []
    for chunk in load_policy_corpus(directory):
        searchable = " ".join(
            value
            for value in (chunk.text, chunk.metadata.title, chunk.metadata.section)
            if value
        )
        counts = Counter(_tokens(searchable))
        score = sum(counts[token] for token in query_tokens)
        if score:
            results.append(
                PolicySearchResult(
                    text=chunk.text,
                    metadata=chunk.metadata,
                    score=score,
                    citation=chunk.citation_text,
                )
            )

    results.sort(
        key=lambda result: (-result.score, result.metadata.source, result.chunk_id)
    )
    return results[:limit]


def _parse_front_matter(
    text: str,
    source: str,
) -> tuple[PolicyFrontMatter, list[tuple[int, str]]]:
    lines = text.splitlines()
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        raise PolicyCorpusError(f"policy {source} must start with front matter")

    closing_line = next(
        (
            index
            for index in range(1, len(lines))
            if lines[index].strip() in {"---", "..."}
        ),
        None,
    )
    if closing_line is None:
        raise PolicyCorpusError(f"policy {source} has unterminated front matter")

    values: dict[str, str | None] = {}
    for line_number, line in enumerate(lines[1:closing_line], start=2):
        if not line.strip():
            continue
        if ":" not in line:
            raise PolicyCorpusError(
                f"policy {source} has malformed front matter at line {line_number}"
            )
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in values:
            raise PolicyCorpusError(
                f"policy {source} has invalid front matter key at line {line_number}"
            )
        if key not in _FRONT_MATTER_KEYS:
            continue
        if value[:1] in {"'", '"'}:
            if len(value) < 2 or value[-1] != value[0]:
                raise PolicyCorpusError(
                    f"policy {source} has malformed front matter at line {line_number}"
                )
            value = value[1:-1]
        values[key] = value or None

    if values.get("id") is None or values.get("title") is None:
        raise PolicyCorpusError(f"policy {source} requires id and title front matter")

    try:
        front_matter = PolicyFrontMatter.model_validate(values)
    except ValueError as error:
        raise PolicyCorpusError(f"policy {source} has invalid front matter") from error

    body = [
        (index + 1, line)
        for index, line in enumerate(lines[closing_line + 1 :], start=closing_line + 1)
    ]
    return front_matter, body


def _chunk_document(
    front_matter: PolicyFrontMatter,
    source: str,
    body: list[tuple[int, str]],
) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    paragraph: list[tuple[int, str]] = []
    section: str | None = None

    def flush() -> None:
        if not paragraph:
            return
        text = "\n".join(line.strip() for _, line in paragraph).strip()
        if not text:
            paragraph.clear()
            return
        spans = _line_spans(paragraph)
        pieces = _split_text(text)
        for part_number, (piece, start, end) in enumerate(pieces, start=1):
            line_start = _offset_to_line(spans, start, first=True)
            line_end = _offset_to_line(spans, end, first=False)
            base_id = f"{front_matter.id}:{line_start}-{line_end}"
            chunk_id = base_id if len(pieces) == 1 else f"{base_id}:part-{part_number}"
            metadata = PolicyMetadata(
                id=front_matter.id,
                title=front_matter.title,
                version=front_matter.version,
                effective_date=front_matter.effective_date,
                source=source,
                section=section,
                line_start=line_start,
                line_end=line_end,
                chunk_id=chunk_id,
            )
            chunks.append(PolicyChunk(text=piece, metadata=metadata))
        paragraph.clear()

    for line_number, raw_line in body:
        line = _REDACTED if _SECRET_ASSIGNMENT_RE.match(raw_line) else raw_line
        heading = _HEADING_RE.match(line)
        if heading:
            flush()
            section = re.sub(r"\s+#+\s*$", "", heading.group(1)).strip() or None
        elif not line.strip():
            flush()
        else:
            paragraph.append((line_number, line))
    flush()
    return chunks


def _line_spans(paragraph: list[tuple[int, str]]) -> list[tuple[int, int, int]]:
    spans: list[tuple[int, int, int]] = []
    offset = 0
    for line_number, raw_line in paragraph:
        line = raw_line.strip()
        start = offset
        end = start + len(line)
        spans.append((start, end, line_number))
        offset = end + 1
    return spans


def _split_text(text: str) -> list[tuple[str, int, int]]:
    pieces: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        end = min(start + MAX_CHUNK_CHARS, len(text))
        if end < len(text):
            boundary = max(
                text.rfind(" ", start + MAX_CHUNK_CHARS // 2, end),
                text.rfind("\n", start + MAX_CHUNK_CHARS // 2, end),
            )
            if boundary > start:
                end = boundary
        piece_start = start
        while piece_start < end and text[piece_start].isspace():
            piece_start += 1
        piece_end = end
        while piece_end > piece_start and text[piece_end - 1].isspace():
            piece_end -= 1
        if piece_start < piece_end:
            pieces.append((text[piece_start:piece_end], piece_start, piece_end))
        start = end
        while start < len(text) and text[start].isspace():
            start += 1
    return pieces


def _offset_to_line(
    spans: list[tuple[int, int, int]],
    offset: int,
    *,
    first: bool,
) -> int:
    if first:
        for start, end, line_number in spans:
            if start <= offset < end or (start == end == offset):
                return line_number
    else:
        for start, end, line_number in reversed(spans):
            if start < offset <= end or (start == end == offset):
                return line_number
    return spans[0 if first else -1][2]


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(value.casefold()))


__all__ = [
    "MAX_CHUNK_CHARS",
    "PolicyCorpusError",
    "PolicyKnowledgeBase",
    "load_policy_corpus",
    "search_policy_corpus",
]
