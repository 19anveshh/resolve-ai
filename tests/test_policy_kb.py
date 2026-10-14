import re
from pathlib import Path

from app.schemas.policy import PolicySearchResponse, PolicySearchResult
from app.services.policy_kb import PolicyKnowledgeBase


def write_policy(path: Path, *, policy_id: str, title: str, body: str) -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                f"id: {policy_id}",
                f"title: {title}",
                "category: orders",
                'version: "1"',
                "---",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )


def search(
    kb: PolicyKnowledgeBase, query: str, *, limit: int = 10
) -> PolicySearchResponse:
    response = kb.search(query, limit=limit)
    assert isinstance(response, PolicySearchResponse)
    assert all(isinstance(result, PolicySearchResult) for result in response.results)
    return response


def test_missing_policy_directory_returns_empty(tmp_path: Path) -> None:
    response = search(PolicyKnowledgeBase(tmp_path / "missing"), "refund")

    assert response.results == []


def test_search_results_use_deterministic_sorted_source_order(tmp_path: Path) -> None:
    for name in ("zeta.md", "alpha.md", "middle.md"):
        write_policy(
            tmp_path / name,
            policy_id=name.removesuffix(".md"),
            title="Shared policy",
            body="Common eligibility policy applies to this document.",
        )

    kb = PolicyKnowledgeBase(tmp_path)
    first = search(kb, "common eligibility", limit=10).results
    second = search(kb, "common eligibility", limit=10).results

    first_order = [result.source for result in first]
    second_order = [result.source for result in second]
    assert first_order == sorted(first_order)
    assert second_order == first_order


def test_result_preserves_metadata_and_citation_line_range(tmp_path: Path) -> None:
    write_policy(
        tmp_path / "returns.md",
        policy_id="returns",
        title="Returns Policy",
        body="Refunds are available for delivered orders within 30 days.",
    )

    result = search(PolicyKnowledgeBase(tmp_path), "refunds", limit=1).results[0]

    assert result.metadata["id"] == "returns"
    assert result.metadata["title"] == "Returns Policy"
    citation = re.fullmatch(
        r"(?:returns\.md|.*/returns\.md)#L(\d+)(?:-L(\d+))?", result.citation
    )
    assert citation is not None
    start = int(citation.group(1))
    end = int(citation.group(2) or citation.group(1))
    assert 1 <= start <= end <= 9


def test_policy_chunks_are_capped_at_1200(tmp_path: Path) -> None:
    for index in range(1205):
        write_policy(
            tmp_path / f"policy-{index:04d}.md",
            policy_id=f"policy-{index:04d}",
            title="Shared policy",
            body="Shared retrieval text.",
        )

    results = search(PolicyKnowledgeBase(tmp_path), "shared retrieval", limit=2_000)

    assert 0 < len(results.results) <= 1_200


def test_ranking_is_stable_and_relevant_result_is_first(tmp_path: Path) -> None:
    write_policy(
        tmp_path / "returns.md",
        policy_id="returns",
        title="Returns Policy",
        body="Refunds are available for delivered orders within 30 days.",
    )
    write_policy(
        tmp_path / "cancellation.md",
        policy_id="cancellation",
        title="Cancellation Policy",
        body="Cancellation is available for pending orders within 24 hours.",
    )

    kb = PolicyKnowledgeBase(tmp_path)
    first = search(kb, "refunds delivered", limit=10).results
    second = search(kb, "refunds delivered", limit=10).results

    assert [(item.source, item.score) for item in first] == [
        (item.source, item.score) for item in second
    ]
    assert Path(first[0].source).name == "returns.md"


def test_blank_query_returns_empty(tmp_path: Path) -> None:
    write_policy(
        tmp_path / "returns.md",
        policy_id="returns",
        title="Returns Policy",
        body="Refunds are available for delivered orders within 30 days.",
    )

    response = search(PolicyKnowledgeBase(tmp_path), "   ")

    assert response.results == []


def test_malformed_and_missing_front_matter_are_skipped(tmp_path: Path) -> None:
    write_policy(
        tmp_path / "valid.md",
        policy_id="valid",
        title="Valid Policy",
        body="Refunds are available for delivered orders.",
    )
    (tmp_path / "malformed.md").write_text(
        "---\ntitle: [broken\n---\nRefunds must not load.\n", encoding="utf-8"
    )
    (tmp_path / "missing.md").write_text(
        "# Missing metadata\nRefunds must not load.\n", encoding="utf-8"
    )

    response = search(PolicyKnowledgeBase(tmp_path), "refunds", limit=10)

    assert [Path(result.source).name for result in response.results] == ["valid.md"]


def test_secret_like_assignments_are_not_exposed(tmp_path: Path) -> None:
    write_policy(
        tmp_path / "safe.md",
        policy_id="safe",
        title="Safe Policy",
        body=(
            "Internal handling note.\n"
            'api_key = "do-not-return-this-value"\n'
            'password = "do-not-return-this-value"\n'
            'token = "do-not-return-this-value"'
        ),
    )

    response = search(PolicyKnowledgeBase(tmp_path), "internal handling", limit=10)
    serialized = response.model_dump_json().lower()

    assert "do-not-return-this-value" not in serialized
    assert "api_key =" not in serialized
    assert "password =" not in serialized
    assert "token =" not in serialized
