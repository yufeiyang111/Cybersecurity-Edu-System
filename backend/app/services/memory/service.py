"""Persistent user memory service.

Follows the Mem0 ADD/SEARCH loop:
- capture_interaction: after a QA answer, extract durable facts and store them
  (ADD), scoped to the user and conversation. New facts are deduplicated
  against existing memories before being written (context lookup).
- retrieve_for_query: before the next answer, rank stored memories against the
  query with hybrid retrieval (semantic + lexical + temporal boost) and return
  the top candidates (SEARCH). Expired memories are never returned; hits
  reinforce last_reinforced_at under a throttle so per-query writes stay cheap.
- feedback_memory: user rates a memory useful/useless; enough negative ratings
  flag it "suggest delete" in the management page (no auto delete).
The whole pipeline is gated by the user's persistent_memory_enabled preference.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from flask import current_app

from app import db
from app.models.memory import (
    MemoryEntity,
    MemoryEntityLink,
    MemoryFeedback,
    UserMemory,
)
from app.models.user import UserPreference

logger = logging.getLogger(__name__)

RETRIEVE_TOP_K = 5
MIN_SIMILARITY = 0.30
# 混合检索：向量/词法两路的召回倍率与 RRF 融合常数
_RECALL_MULTIPLIER = 2
_RRF_CONSTANT = 60
# 时间加权：距今超过该天数后不再获得加成（配合衰减因子封顶 ±10%）
_TEMPORAL_WINDOW_DAYS = 5
# 强化回写节流：同一记忆两次强化写入的最小间隔（秒），避免每次检索都写库
_REINFORCE_THROTTLE_SECONDS = 300

VALID_CATEGORIES = {"preference", "fact", "decision", "goal", "other"}

# memory_id -> 上次强化写入时间戳（进程内节流，可接受多实例重复写）
_last_reinforced_ts: dict[int, float] = {}

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
    extracted = _extract(provider, question, answer)
    facts = extracted["facts"]
    if not facts:
        return {"added": 0, "updated": 0, "skipped": 0}
    kept, skipped = _dedup_against_existing(user_id, facts)
    if kept:
        _store(user_id, conversation_id, record_id, kept, extracted["entities"])
        logger.info(
            "memory.capture user_id=%s added=%d skipped=%d entities=%d",
            user_id,
            len(kept),
            skipped,
            len(extracted["entities"]),
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
    now = datetime.utcnow()
    memories = (
        UserMemory.query.filter_by(user_id=user_id)
        .filter(
            db.or_(UserMemory.expires_at.is_(None), UserMemory.expires_at > now)
        )
        .order_by(UserMemory.created_at.desc())
        .limit(200)
        .all()
    )
    if not memories:
        return []
    ranked = _hybrid_rank(query, memories)
    boost = _entity_boost(user_id, query, memories)
    ranked = [
        (memory, score + boost.get(memory.id, 0.0))
        for memory, score in ranked
    ]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    if conversation_id is not None:
        ranked.sort(
            key=lambda pair: (pair[0].source_conversation_id == conversation_id, pair[1]),
            reverse=True,
        )
    hits = ranked[:top_k]
    _reinforce(hits)
    return [
        {"content": memory.content, "category": memory.category}
        for memory, _score in hits
    ]


def _entity_boost(
    user_id: int, query: str, memories: list[UserMemory]
) -> dict[int, float]:
    """Entity signal: memories whose stored entities appear in the query get +0.1.

    Query terms come from jieba (fallback to 2+ char ngrams); matching is a
    single batched ``IN`` query so retrieval cost stays flat.
    """
    terms = _query_terms(query)
    if not terms:
        return {}
    try:
        entities = (
            MemoryEntity.query.filter(
                MemoryEntity.user_id == user_id,
                MemoryEntity.name.in_(terms),
            )
            .all()
        )
    except Exception:
        logger.warning("memory.entity_boost unavailable user_id=%s", user_id)
        return {}
    boosts: dict[int, float] = {}
    for entity in entities:
        if entity.memory_id is not None:
            boosts[entity.memory_id] = boosts.get(entity.memory_id, 0.0) + 0.1
    return boosts


def _query_terms(query: str) -> list[str]:
    try:
        import jieba

        words = [word.strip() for word in jieba.lcut(query) if len(word.strip()) >= 2]
    except Exception:
        words = [query[index : index + 2] for index in range(max(0, len(query) - 1))]
    return list(dict.fromkeys(words))[:20]


def _reinforce(hits: list[tuple[UserMemory, float]]) -> None:
    """Throttled reinforcement: write last_reinforced_at at most once per window."""
    now_ts = time.time()
    now = datetime.utcnow()
    dirty = False
    for memory, _score in hits:
        previous = _last_reinforced_ts.get(memory.id)
        if previous is not None and now_ts - previous < _REINFORCE_THROTTLE_SECONDS:
            continue
        memory.last_reinforced_at = now
        _last_reinforced_ts[memory.id] = now_ts
        dirty = True
    if dirty:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.warning("memory.reinforce write failed, skipped", exc_info=True)


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


def negative_feedback_counts(user_id: int, memory_ids: list[int]) -> dict[int, int]:
    """批量返回 记忆 id -> 负面反馈（rating=0）计数（限当前用户）。"""
    if not memory_ids:
        return {}
    from sqlalchemy import func

    rows = (
        db.session.query(MemoryFeedback.memory_id, func.count(MemoryFeedback.id))
        .filter(
            MemoryFeedback.memory_id.in_(memory_ids),
            MemoryFeedback.user_id == user_id,
            MemoryFeedback.rating == 0,
        )
        .group_by(MemoryFeedback.memory_id)
        .all()
    )
    return {memory_id: count for memory_id, count in rows}


def suggest_delete_threshold() -> int:
    return max(1, int(current_app.config.get("MEMORY_FEEDBACK_SUGGEST_THRESHOLD", 3)))


def submit_feedback(user_id: int, memory_id: int, rating: int) -> tuple[UserMemory | None, int]:
    """记录用户对一条记忆的好/坏反馈，返回 (记忆, 累计负面计数)。"""
    memory = UserMemory.query.filter_by(id=memory_id, user_id=user_id).first()
    if memory is None:
        return None, 0
    if isinstance(rating, bool) or rating not in (0, 1):
        raise ValueError("rating 必须是 0（没用）或 1（有用）")
    db.session.add(MemoryFeedback(memory_id=memory.id, user_id=user_id, rating=rating))
    db.session.commit()
    from sqlalchemy import func

    negative = (
        db.session.query(func.count(MemoryFeedback.id))
        .filter(MemoryFeedback.memory_id == memory.id, MemoryFeedback.rating == 0)
        .scalar()
        or 0
    )
    return memory, negative


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


def _extract(provider: Any, question: str, answer: str) -> dict:
    from .extractor import extract_facts

    return extract_facts(provider, question, answer)


def _store(
    user_id: int,
    conversation_id: int | None,
    record_id: int | None,
    facts: list[dict],
    entities: list[dict] | None = None,
) -> None:
    for fact in facts:
        memory = UserMemory(
            user_id=user_id,
            content=fact["content"],
            category=fact["category"],
            source_conversation_id=conversation_id,
            source_record_id=record_id,
        )
        db.session.add(memory)
        db.session.flush()
        _store_entities(user_id, memory.id, entities or [])
    db.session.commit()


def _store_entities(user_id: int, memory_id: int, entities: list[dict]) -> None:
    """同一轮抽取的实体关联到每条新记忆。"""
    if not entities:
        return
    for entity in entities:
        db.session.add(
            MemoryEntity(
                user_id=user_id,
                memory_id=memory_id,
                name=entity["name"],
                entity_type=entity["type"],
            )
        )


def _selector_provider(user_id: int):
    # 记忆抽取只使用用户自己配置的 LLM provider（用户默认 provider 优先，
    # 无则回退服务端默认 provider）；硅基流动仅限 embedding/rerank，禁止用于 LLM 生成。
    try:
        from app.services.llm.provider_selector import select_provider

        return select_provider(user_id=user_id, operation="memory")
    except Exception:
        return None
