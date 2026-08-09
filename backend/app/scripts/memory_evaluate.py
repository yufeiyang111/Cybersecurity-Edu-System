"""持久记忆离线评估脚本：对 memory_eval_cases 评估集计算检索质量指标。

用法（backend 目录下）：
    .venv\\Scripts\\python.exe -m app.scripts.memory_evaluate [--top-k 5]

指标：
    hit@1 / hit@3 / hit@5 / MRR（基于期望命中的记忆内容）

原理：把评估集所有期望记忆作为种子写入评测用户（id=999999）的记忆库，
逐条运行 retrieve_for_query（混合检索），检查期望内容是否出现在 top-k 中。
评估结束后自动清理种子数据，不污染真实用户。
"""
from __future__ import annotations

import argparse
import json

from app import create_app, db
from app.models.memory import UserMemory
from app.models.user import User, UserPreference
from app.services.memory import service as memory_service

EVAL_USER_ID = 999999


def _seed_case(user_id: int, content: str, category: str) -> int:
    memory = memory_service.create_memory(user_id, content, category)
    return memory.id


def _ensure_eval_user(user_id: int) -> "User | None":
    """创建（或复用）评测占位用户，返回用户对象；失败返回 None。"""
    from app.models.user import User, Role

    user = User.query.get(user_id)
    if user is not None:
        return user
    try:
        role = Role.query.filter_by(name="user").first()
        user = User(
            id=user_id,
            username="memory_eval_bot",
            email="memory-eval-bot@local.test",
            role_id=role.id if role else None,
        )
        db.session.add(user)
        db.session.commit()
        return user
    except Exception:
        db.session.rollback()
        return None


def evaluate(top_k: int = 5) -> dict:
    from app.models.qa import MemoryEvalCase

    cases = db.session.query(MemoryEvalCase).all()
    if not cases:
        return {"error": "评估集为空：请先导入 memory_eval_cases 评测用例"}

    # 评测占位用户（外键依赖 users.id）
    eval_user = _ensure_eval_user(EVAL_USER_ID)
    if eval_user is None:
        return {"error": "无法创建评测占位用户，请检查 users 表状态"}

    # 确保评测用户开启持久记忆（检索有开关门控）
    preference = UserPreference.query.filter_by(user_id=EVAL_USER_ID).first()
    if preference is None:
        preference = UserPreference(user_id=EVAL_USER_ID, persistent_memory_enabled=True)
        db.session.add(preference)
    else:
        preference.persistent_memory_enabled = True
    db.session.commit()

    # 种子：期望记忆全部入库
    seeded: list[int] = []
    for case in cases:
        seeded.append(_seed_case(EVAL_USER_ID, case.expected_content, case.category))

    hits = {1: 0, 3: 0, 5: 0}
    mrr_sum = 0.0
    details = []

    try:
        for case in cases:
            retrieved = memory_service.retrieve_for_query(
                user_id=EVAL_USER_ID,
                query=case.query,
                top_k=top_k,
            )
            contents = [item["content"] for item in retrieved]
            for k in (1, 3, 5):
                if case.expected_content in contents[:k]:
                    hits[k] += 1
            for rank, content in enumerate(contents, start=1):
                if content == case.expected_content:
                    mrr_sum += 1.0 / rank
                    break
            details.append({
                "query": case.query,
                "expected": case.expected_content,
                "retrieved_top5": contents,
                "hit@5": case.expected_content in contents[:5],
            })
    finally:
        # 清理种子数据（记忆、开关偏好、占位用户），不污染真实用户
        UserMemory.query.filter_by(user_id=EVAL_USER_ID).delete()
        db.session.delete(preference)
        eval_user = User.query.get(EVAL_USER_ID)
        if eval_user is not None:
            db.session.delete(eval_user)
        db.session.commit()

    total = max(1, len(cases))
    return {
        "cases": len(cases),
        "hit@1": round(hits[1] / total, 4),
        "hit@3": round(hits[3] / total, 4),
        "hit@5": round(hits[5] / total, 4),
        "mrr": round(mrr_sum / total, 4),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="持久记忆检索离线评估")
    parser.add_argument("--top-k", type=int, default=5, help="检索返回条数（默认 5）")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        report = evaluate(top_k=args.top_k)
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
