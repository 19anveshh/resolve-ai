"""Policy knowledge-base search endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.config import get_settings
from app.schemas.policy import PolicySearchResponse
from app.services.policy_kb import PolicyKnowledgeBase

settings = get_settings()
router = APIRouter(prefix=settings.api_v1_prefix, tags=["policies"])


def get_policy_kb() -> PolicyKnowledgeBase:
    """Build policy search from the configured corpus directory."""

    return PolicyKnowledgeBase(get_settings().policy_dir)


PolicyKnowledgeBaseDependency = Annotated[PolicyKnowledgeBase, Depends(get_policy_kb)]


@router.get("/policies/search", response_model=PolicySearchResponse)
def search_policies(
    policy_kb: PolicyKnowledgeBaseDependency,
    q: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=50),
) -> PolicySearchResponse:
    """Return deterministic policy matches with source citations."""

    return policy_kb.search(q, limit=limit)
