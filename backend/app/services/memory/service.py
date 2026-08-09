"""Persistent user memory service.

Follows the Mem0 ADD/SEARCH loop:
- capture_interaction: after a QA answer, extract durable facts and store them
  (ADD), scoped to the user and conversation.
- retrieve_for_query: before the next answer, rank stored memories against the
  query with semantic similarity (SEARCH) and return the top candidates.
The whole pipeline is gated by the user's persistent_memory_enabled preference.
"""
from __future__ import annotations

from typing import Any

from app import db
from app.models.memory import UserMemory
from app.models.user import UserPreference

RETRIEVE_TOP_K = 5
MIN_SIMILARITY = 0.30

VALID_CATEGORIES = {"preference", "fact", "decision", "goal", "other"}

_CATEGORY_LABELS = {
    "preference": "偏好",
    "fact": "事实",
    "decision": "决定",
    "goal": "目标",
    "other": "其他",
}


def memory_enabled(user_id: int) -> bool:
    preferences = UserPreference.query.filter_by(user_id=user_id).first()
    return bool(preferences and preferences.persistent_memory_enabled)


def capture_interaction(
    *,
    user_id: int,
    conversation_id: int | None,
    record_id: int | None,
    question: str,
    answer: str,
) -> int:
    """Extract durable facts from one QA interaction and store them (ADD)."""
    if not memory_enabled(user_id):
        return 0
    provider = _selector_provider(user_id)
    if provider is None:
        return 0
    facts = _extract(provider, question, answer)
    if not facts:
        return 0
    _store(user_id, conversation_id, record_id, facts)
    return len(facts)


def retrieve_for_query(
    *,
    user_id: int,
    query: str,
    conversation_id: int | None = None,
    top_k: int = RETRIEVE_TOP_K,
) -> list[dict[str, Any]]:
    """Rank the user's memories against the query (SEARCH) and return top items."""
    if not memory_enabled(user_id):
        return []
    memories = (
        UserMemory.query.filter_by(user_id=user_id)
        .order_by(UserMemory.created_at.desc())
        .limit(200)
        .all()
    )
    if not memories:
        return []
    contents = [memory.content for memory in memories]
    try:
        from app.services.secbert_embedding import compute_text_similarity

        scores = compute_text_similarity(query, contents)
    except Exception:
        scores = [0.0] * len(memories)
    ranked = sorted(
        (
            (memory, float(score))
            for memory, score in zip(memories, scores)
            if float(score) >= MIN_SIMILARITY
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )
    if conversation_id is not None:
        ranked.sort(
            key=lambda pair: (pair[0].source_conversation_id == conversation_id, pair[1]),
            reverse=True,
        )
    return [
        {"content": memory.content, "category": memory.category}
        for memory, _score in ranked[:top_k]
    ]


def list_memories(user_id: int, params: dict) -> tuple[list[UserMemory], int]:
    query = UserMemory.query.filter_by(user_id=user_id)
    category = str(params.get("category") or "").strip()
    if category:
        query = query.filter(UserMemory.category == category)
    page = max(1, int(params.get("page", 1)))
    per_page = max(1, min(100, int(params.get("per_page", 20))))
    pagination = db.paginate(
        query.order_by(UserMemory.created_at.desc()).statement,
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return pagination.items, pagination.total


def delete_memory(user_id: int, memory_id: int) -> bool:
    memory = UserMemory.query.filter_by(id=memory_id, user_id=user_id).first()
    if memory is None:
        return False
    db.session.delete(memory)
    db.session.commit()
    return True


def create_memory(user_id: int, content: str, category: str) -> UserMemory:
    """手动新增一条记忆（用户主动维护，不受持久记忆开关门控）。"""
    content = (content or "").strip()
    if not content:
        raise ValueError("记忆内容不能为空")
    if len(content) > 2000:
        raise ValueError("记忆内容不能超过 2000 字")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"无效的记忆分类：{category}")
    memory = UserMemory(user_id=user_id, content=content, category=category)
    db.session.add(memory)
    db.session.commit()
    return memory


def update_memory(user_id: int, memory_id: int, content: str, category: str) -> UserMemory | None:
    """更新一条记忆（仅限本人），不存在或不属于该用户时返回 None。"""
    memory = UserMemory.query.filter_by(id=memory_id, user_id=user_id).first()
    if memory is None:
        return None
    content = (content or "").strip()
    if not content:
        raise ValueError("记忆内容不能为空")
    if len(content) > 2000:
        raise ValueError("记忆内容不能超过 2000 字")
    if category not in VALID_CATEGORIES:
        raise ValueError(f"无效的记忆分类：{category}")
    memory.content = content
    memory.category = category
    db.session.commit()
    return memory


def category_label(category: str) -> str:
    return _CATEGORY_LABELS.get(category, "其他")


def _extract(provider: Any, question: str, answer: str) -> list[dict]:
    from .extractor import extract_facts

    return extract_facts(provider, question, answer)


def _store(
    user_id: int,
    conversation_id: int | None,
    record_id: int | None,
    facts: list[dict],
) -> None:
    for fact in facts:
        db.session.add(
            UserMemory(
                user_id=user_id,
                content=fact["content"],
                category=fact["category"],
                source_conversation_id=conversation_id,
                source_record_id=record_id,
            )
        )
    db.session.commit()


def _selector_provider(user_id: int):
    try:
        from app.services.llm.provider_selector import select_provider

        return select_provider(user_id=user_id, operation="memory")
    except Exception:
        return None
