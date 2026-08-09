"""Persistent user memory service.

Follows the Mem0 ADD/SEARCH loop:
- capture_interaction: after a QA answer, extract durable facts and store them
  (ADD), scoped to the user and conversation. New facts are deduplicated
  against existing memories before being written (context lookup).
- retrieve_for_query: before the next answer, rank stored memories against the
  query with hybrid retrieval (semantic + lexical + temporal boost) and return
  the top candidates (SEARCH).
The whole pipeline is gated by the user's persistent_memory_enabled preference.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flask import current_app

from app import db
from app.models.memory import UserMemory
from app.models.user import UserPreference

logger = logging.getLogger(__name__)

RETRIEVE_TOP_K = 5
MIN_SIMILARITY = 0.30
# 混合检索：向量/词法两路的召回倍率与 RRF 融合常数
_RECALL_MULTIPLIER = 2
_RRF_CONSTANT = 60
# 时间加权：距今超过该天数后不再获得加成（配合衰减因子封顶 ±10%）
_TEMPORAL_WINDOW_DAYS = 5

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
) -> dict[str, int]:
    """Extract durable facts from one QA interaction and store them (ADD).

    Facts already known (semantic similarity >= threshold against existing
    memories) are skipped. Returns ``{"added": n, "updated": 0, "skipped": m}``.
    """
    if not memory_enabled(user_id):
        return {"added": 0, "updated": 0, "skipped": 0}
    provider = _selector_provider(user_id)
    if provider is None:
        return {"added": 0, "updated": 0, "skipped": 0}
    facts = _extract(provider, question, answer)
    if not facts:
        return {"added": 0, "updated": 0, "skipped": 0}
    kept, skipped = _dedup_against_existing(user_id, facts)
    if kept:
        _store(user_id, conversation_id, record_id, kept)
        logger.info(
            "memory.capture user_id=%s added=%d skipped=%d",
            user_id,
            len(kept),
            skipped,
        )
    return {"added": len(kept), "updated": 0, "skipped": skipped}


def _dedup_against_existing(
    user_id: int, facts: list[dict]
) -> tuple[list[dict], int]:
    """Context lookup: drop facts already covered by the user's existing memories.

    The similarity engine is best-effort; if it fails (degraded embedder, model
    unload) all facts are kept so memory capture never silently loses data.
    """
    existing = UserMemory.query.filter_by(user_id=user_id).all()
    if not existing or not facts:
        return facts, 0
    existing_contents = [memory.content for memory in existing]
    threshold = float(
        current_app.config.get("MEMORY_DEDUP_THRESHOLD", 0.92)
    )
    kept: list[dict] = []
    skipped = 0
    try:
        from app.services.secbert_embedding import compute_text_similarity

        for fact in facts:
            scores = compute_text_similarity(fact["content"], existing_contents)
            if scores and max(scores) >= threshold:
                skipped += 1
            else:
                kept.append(fact)
    except Exception:
        logger.warning("memory.dedup unavailable, keeping all facts user_id=%s", user_id)
        return facts, 0
    return kept, skipped


def retrieve_for_query(
    *,
    user_id: int,
    query: str,
    conversation_id: int | None = None,
    top_k: int = RETRIEVE_TOP_K,
) -> list[dict[str, Any]]:
    """Rank the user's memories against the query (SEARCH) and return top items.

    Hybrid retrieval: semantic vector scores (when the embedder is available)
    and lexical term overlap are fused with RRF, then lightly time-weighted so
    recently reinforced memories rank slightly higher. When the embedder is
    degraded or unavailable, only the lexical path is used and no similarity
    filter is applied (mirrors the RAG degraded path).
    """
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
    ranked = _hybrid_rank(query, memories)
    if conversation_id is not None:
        ranked.sort(
            key=lambda pair: (pair[0].source_conversation_id == conversation_id, pair[1]),
            reverse=True,
        )
    return [
        {"content": memory.content, "category": memory.category}
        for memory, _score in ranked[:top_k]
    ]


def _hybrid_rank(query: str, memories: list[UserMemory]) -> list[tuple[UserMemory, float]]:
    """Fuse semantic + lexical candidate scores with RRF and apply time boost."""
    vec_scores: dict[int, float] = {}
    try:
        from app.services.secbert_embedding import compute_text_similarity

        raw = compute_text_similarity(query, [memory.content for memory in memories])
        for memory, score in zip(memories, raw):
            if score >= MIN_SIMILARITY:
                vec_scores[memory.id] = float(score)
    except Exception:
        logger.warning("memory.vector_path unavailable, lexical only user_id=%s", memories[0].user_id)

    lex_scores = _lexical_scores(query, memories)
    lex_ids = {
        memory.id: score for memory, score in zip(memories, lex_scores) if score > 0
    }

    fused: dict[int, float] = {}
    for ranked_ids in (
        sorted(vec_scores, key=vec_scores.get, reverse=True),
        sorted(lex_ids, key=lex_ids.get, reverse=True),
    ):
        for rank, memory_id in enumerate(ranked_ids):
            fused[memory_id] = fused.get(memory_id, 0.0) + 1.0 / (_RRF_CONSTANT + rank)
    if not fused:
        return []

    by_id = {memory.id: memory for memory in memories}
    ranked = [
        (by_id[memory_id], score * _temporal_factor(by_id[memory_id]))
        for memory_id, score in fused.items()
    ]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked


def _lexical_scores(query: str, memories: list[UserMemory]) -> list[int]:
    """Count query terms (jieba, fallback to 2+ char ngrams) present per memory."""
    try:
        import jieba

        words = [word for word in jieba.lcut(query) if len(word.strip()) >= 2]
    except Exception:
        words = [query[index : index + 2] for index in range(max(0, len(query) - 1))]
    if not words:
        return [0] * len(memories)
    return [sum(1 for word in words if word in memory.content) for memory in memories]


def _temporal_factor(memory: UserMemory) -> float:
    """Light recency boost: up to +10% for memories touched within the window."""
    updated_at = memory.updated_at or memory.created_at
    if updated_at is None:
        return 1.0
    days = max(0, (datetime.utcnow() - updated_at).days)
    decay = float(current_app.config.get("MEMORY_TEMPORAL_DECAY_PER_DAY", 0.02))
    return 1.0 + decay * max(0, _TEMPORAL_WINDOW_DAYS - min(days, _TEMPORAL_WINDOW_DAYS))


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
    # 记忆抽取优先使用结构化输出稳定的专用模型（如硅基流动 DeepSeek），
    # MiniMax 免费档对 JSON 输出时好时坏（LLM_OUTPUT_INVALID）
    provider = _memory_dedicated_provider(user_id)
    if provider is not None:
        return provider
    try:
        from app.services.llm.provider_selector import select_provider

        return select_provider(user_id=user_id, operation="memory")
    except Exception:
        return None


def _memory_dedicated_provider(user_id: int):
    """创建记忆抽取专用 provider；配置缺失或创建失败时返回 None（走默认链路）。"""
    from app.config import Config

    base = getattr(Config, "MEMORY_LLM_API_BASE", "") or ""
    api_key = getattr(Config, "MEMORY_LLM_API_KEY", "") or ""
    model = getattr(Config, "MEMORY_LLM_MODEL", "") or ""
    if not api_key or not model:
        return None
    try:
        from app.services.llm.call_logging import observe_provider
        from app.services.llm.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            provider_name="memory-llm",
            base_url=base,
            api_key=api_key,
            model=model,
            user_id=user_id,
            operation="memory",
        )
        return observe_provider(provider, user_id=user_id, operation="memory")
    except Exception:
        return None
