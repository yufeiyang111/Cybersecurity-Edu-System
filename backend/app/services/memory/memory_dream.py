# -*- coding: utf-8 -*-
"""Dream：持久记忆后台整合（对标 Mem0 Dream）。

周期性扫描用户的记忆，用 LLM 做三类整合操作：
- synthesize：碎片合成（多条相关记忆合成一条新记忆）；
- supersede：新事实取代旧事实（旧记录 expires_at=NOW() 而非硬删）；
- merge：重复合并（参与合并的旧记录 expires_at=NOW()）。

所有操作写入 memory_dream_audit 审计（谁/何时/做了什么），可回滚
（被取代/合并的记忆只是过期，不删除，恢复时清空 expires_at 即可）。

运行方式（CLI）：
    flask --app run memory-dream              # 所有启用记忆的用户
    flask --app run memory-dream --user-id 4  # 指定用户
    flask --app run memory-dream --dry-run    # 只分析不执行
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from app import db
from app.models.memory import MemoryDreamAudit, UserMemory

logger = logging.getLogger(__name__)

DREAM_BATCH_SIZE = 100
DREAM_MAX_MEMORIES_PER_USER = 200

DREAM_PROMPT = """你是记忆整合助手。下面是一个用户的持久记忆列表（JSON 数组，每条含 id/content/category）。
请分析并输出三类整合操作（没有需要操作的则返回空数组）：

1. merge：多条记忆内容重复或高度相似 → 合并为一条。输出 {{"action": "merge", "memory_ids": [id...], "content": "合并后的内容"}}（参与合并的旧记录会过期，不删除）。
2. supersede：一条新记忆明显取代旧记忆（如偏好/目标变更）→ 输出 {{"action": "supersede", "supersede_id": 旧记忆id, "content": "新记忆内容"}}（旧记录会过期，新记忆入库）。
3. synthesize：多条碎片记忆可合成为一条更有用的概括 → 输出 {{"action": "synthesize", "memory_ids": [id...], "content": "概括内容", "category": "fact"}}。

规则：
- 只输出 JSON 数组，不要输出其他内容。
- 每条操作的 content 用第三人称客观描述。
- 不要输出敏感信息（密码、密钥、Token 等）。
- memory_ids 至少 2 个 id（supersede 只需 supersede_id）。
- 合并/合成时必须完整保留关键信息（姓名、数字、日期、具体工具/组织名称等），不得省略或改写为泛指（如"姓名"代替具体姓名）。

记忆列表：
{memories_json}
"""


def run_dream(
    *,
    user_id: int | None = None,
    dry_run: bool = False,
    limit_per_user: int = DREAM_MAX_MEMORIES_PER_USER,
) -> dict:
    """执行一轮 Dream 整合，返回统计（用户数 / 操作数 / 失败数）。"""
    users = _target_users(user_id)
    total_operations = 0
    total_failures = 0
    for current_user_id in users:
        provider = _selector_provider(current_user_id)
        if provider is None:
            logger.warning("memory.dream skipped user_id=%s (no provider)", current_user_id)
            continue
        memories = _user_memories(current_user_id, limit_per_user)
        if not memories:
            continue
        operations = _analyze(provider, memories)
        for operation in operations:
            try:
                if not dry_run:
                    _apply_operation(current_user_id, operation)
                total_operations += 1
            except Exception:
                db.session.rollback()
                total_failures += 1
                logger.warning(
                    "memory.dream operation failed user_id=%s action=%s",
                    current_user_id,
                    operation.get("action"),
                )
    return {"users": len(users), "operations": total_operations, "failures": total_failures}


def _target_users(user_id: int | None) -> list[int]:
    """目标用户：显式指定，或所有启用持久记忆且有记忆的用户。"""
    if user_id is not None:
        return [user_id]
    rows = (
        db.session.query(UserMemory.user_id)
        .distinct()
        .order_by(UserMemory.user_id)
        .all()
    )
    return [row[0] for row in rows]


def _user_memories(user_id: int, limit: int) -> list[UserMemory]:
    return (
        UserMemory.query.filter_by(user_id=user_id)
        .filter(UserMemory.expires_at.is_(None))
        .order_by(UserMemory.created_at.asc())
        .limit(limit)
        .all()
    )


def _analyze(provider: Any, memories: list[UserMemory]) -> list[dict]:
    """LLM 分析记忆列表，返回操作指令（解析失败返回空）。"""
    payload = [
        {"id": memory.id, "content": memory.content, "category": memory.category}
        for memory in memories[:DREAM_BATCH_SIZE]
    ]
    from app.services.llm.contracts import LLMRequest
    from app.services.llm.provider_selector import resolve_provider_max_tokens

    request = LLMRequest(
        prompt=DREAM_PROMPT.format(memories_json=json.dumps(payload, ensure_ascii=False)),
        temperature=0.1,
        # 推理模型（如 deepseek-v4-flash）思考会消耗大量 token，
        # 默认 4096 起步；用户在 Provider 配置了 max_tokens 则优先用配置值。
        max_tokens=resolve_provider_max_tokens(provider, 4096),
    )
    try:
        response = provider.generate(request)
    except Exception:
        logger.warning("memory.dream analyze failed user_id=%s", memories[0].user_id)
        return []
    if not getattr(response, "is_success", False) or not getattr(response, "text", None):
        return []
    return _parse_operations(response.text)


def _parse_operations(text: str) -> list[dict]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except (TypeError, ValueError):
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
        except (TypeError, ValueError):
            return []
    if not isinstance(payload, list):
        return []
    operations: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "")
        if action not in {"merge", "supersede", "synthesize"}:
            continue
        content = str(item.get("content") or "").strip()
        if not content or len(content) > 2000:
            continue
        operation = {"action": action, "content": content[:2000]}
        if action == "supersede":
            supersede_id = item.get("supersede_id")
            try:
                operation["supersede_id"] = int(supersede_id)
            except (TypeError, ValueError):
                continue
        else:
            memory_ids = item.get("memory_ids")
            if not isinstance(memory_ids, list) or len(memory_ids) < 2:
                continue
            try:
                operation["memory_ids"] = [int(mid) for mid in memory_ids]
            except (TypeError, ValueError):
                continue
        if action == "synthesize":
            operation["category"] = str(item.get("category") or "fact")[:32]
        operations.append(operation)
    return operations


def _apply_operation(user_id: int, operation: dict) -> None:
    """执行单条操作：synthesize/supersede 入库新记忆，旧记忆全部过期化。"""
    action = operation["action"]
    content = operation["content"]
    now = datetime.utcnow()
    expired_ids: list[int] = []

    if action == "supersede":
        supersede_id = operation["supersede_id"]
        memory = db.session.get(UserMemory, supersede_id)
        if memory is None or memory.user_id != user_id:
            raise ValueError("supersede 目标记忆不存在")
        memory.expires_at = now
        expired_ids = [supersede_id]
        new_memory = UserMemory(user_id=user_id, content=content, category="fact")
        db.session.add(new_memory)
        db.session.flush()
    elif action in ("merge", "synthesize"):
        memory_ids = operation["memory_ids"]
        owned = (
            UserMemory.query.filter(
                UserMemory.id.in_(memory_ids),
                UserMemory.user_id == user_id,
            ).all()
        )
        owned_ids = {memory.id for memory in owned}
        if len(owned_ids) < 2:
            raise ValueError("merge/synthesize 需要至少 2 条本人记忆")
        for memory in owned:
            memory.expires_at = now
        expired_ids = sorted(owned_ids)
        category = operation.get("category", "fact")
        if category not in _VALID_CATEGORIES:
            category = "fact"
        new_memory = UserMemory(user_id=user_id, content=content, category=category)
        db.session.add(new_memory)
        db.session.flush()
    else:
        raise ValueError(f"未知操作: {action}")

    db.session.add(
        MemoryDreamAudit(
            user_id=user_id,
            action=action,
            memory_ids=",".join(str(mid) for mid in expired_ids),
            detail=content[:500],
        )
    )
    db.session.commit()
    logger.info(
        "memory.dream applied user_id=%s action=%s expired_ids=%s",
        user_id,
        action,
        expired_ids,
    )


_VALID_CATEGORIES = {"preference", "fact", "decision", "goal", "other"}


def _selector_provider(user_id: int):
    """与抽取一致：只使用用户自己配置的 LLM provider（用户默认优先，无则服务端默认）。"""
    try:
        from app.services.llm.provider_selector import select_provider

        return select_provider(user_id=user_id, operation="memory")
    except Exception:
        return None
