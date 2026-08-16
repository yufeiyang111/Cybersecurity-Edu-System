# -*- coding: utf-8 -*-
"""Harness V3 漏洞假设的只读查询与脱敏聚合指标。"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, func
from sqlalchemy.orm import selectinload

from app import db
from app.models.agent_hypothesis import AgentAuditHypothesis, AuditHypothesisStatus
from app.models.agent_llm import LLMInvocation

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class HypothesisPage:
    """假设列表的服务端分页结果。"""

    items: tuple[AgentAuditHypothesis, ...]
    total: int
    page: int
    page_size: int


class HypothesisQueryService:
    """只读暴露受控审计事实，绝不返回 Provider 原文、Prompt 或源码。"""

    def list_for_run(
        self,
        run_id: int,
        *,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> HypothesisPage:
        """按优先级读取当前 Run 的假设，始终在数据库层完成分页。"""
        self.validate_pagination(page=page, page_size=page_size)
        query = (
            AgentAuditHypothesis.query.filter_by(run_id=run_id)
            .order_by(
                AgentAuditHypothesis.priority.desc(),
                AgentAuditHypothesis.id.asc(),
            )
        )
        total = query.count()
        rows = (
            query.offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return HypothesisPage(
            items=tuple(rows),
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_for_run(
        self,
        run_id: int,
        hypothesis_id: int,
    ) -> AgentAuditHypothesis | None:
        """按 Run 归属读取详情，跨 Run ID 一律视为不存在。"""
        return (
            AgentAuditHypothesis.query.options(
                selectinload(AgentAuditHypothesis.verdicts)
            )
            .filter_by(run_id=run_id, id=hypothesis_id)
            .first()
        )

    def metrics_for_run(self, run_id: int) -> dict:
        """返回不含源码和 Provider 内容的运行级聚合指标。"""
        total = (
            db.session.query(func.count(AgentAuditHypothesis.id))
            .filter(AgentAuditHypothesis.run_id == run_id)
            .scalar()
            or 0
        )
        status_counts = self._status_counts(run_id)
        confirmed = status_counts.get(AuditHypothesisStatus.CONFIRMED.value, 0)
        needs_evidence = status_counts.get(AuditHypothesisStatus.NEEDS_EVIDENCE.value, 0)
        stopped_for_budget = status_counts.get(
            AuditHypothesisStatus.STOPPED_FOR_BUDGET.value,
            0,
        )
        return {
            "hypothesis_count": total,
            "status_counts": status_counts,
            "skill_counts": self._skill_counts(run_id),
            "code_evidence_coverage": _rate(confirmed, total),
            "evidence_insufficient_rate": _rate(needs_evidence, total),
            "budget_exhaustion_rate": _rate(stopped_for_budget, total),
            "deep_review_cost": self._deep_review_cost(run_id, total),
        }

    @staticmethod
    def validate_pagination(*, page: int, page_size: int) -> None:
        """统一限制页码，避免列表端点出现无边界读取。"""
        if not isinstance(page, int) or page < 1:
            raise ValueError("page 必须大于 0")
        if not isinstance(page_size, int) or not 1 <= page_size <= _MAX_PAGE_SIZE:
            raise ValueError(f"page_size 必须在 1 至 {_MAX_PAGE_SIZE} 之间")

    @staticmethod
    def serialize_list_item(hypothesis: AgentAuditHypothesis) -> dict:
        """列表仅返回 UI 所需的显式白名单字段。"""
        return {
            "id": hypothesis.id,
            "hypothesis_key": hypothesis.hypothesis_key,
            "skill_key": hypothesis.skill_key,
            "title": hypothesis.title,
            "target_summary": hypothesis.target_summary,
            "priority": hypothesis.priority,
            "status": _enum_value(hypothesis.status),
            "planner_source": hypothesis.planner_source,
            "required_evidence": hypothesis.required_evidence_json or [],
            "authorized_scopes": hypothesis.authorized_scopes_json or [],
            "satisfied_evidence": hypothesis.satisfied_evidence_json or [],
            "evidence_gaps": hypothesis.evidence_gaps_json or [],
            "reflection_count": hypothesis.reflection_count,
            "execution_attempt_count": hypothesis.execution_attempt_count,
            "created_at": hypothesis.created_at.isoformat() if hypothesis.created_at else None,
            "updated_at": hypothesis.updated_at.isoformat() if hypothesis.updated_at else None,
        }

    @staticmethod
    def serialize_detail(hypothesis: AgentAuditHypothesis) -> dict:
        """详情只追加受控 Critic Verdict，不转发模型或持久化内部字段。"""
        result = HypothesisQueryService.serialize_list_item(hypothesis)
        result["verdicts"] = [
            {
                "id": verdict.id,
                "hypothesis_id": verdict.hypothesis_id,
                "verdict_version": verdict.verdict_version,
                "verdict": _enum_value(verdict.verdict),
                "reason_summary": verdict.reason_summary,
                "evidence_gaps": verdict.evidence_gaps_json or [],
                "next_action": _next_action_payload(verdict.next_action_json),
                "critic_version": verdict.critic_version,
                "created_at": verdict.created_at.isoformat() if verdict.created_at else None,
            }
            for verdict in hypothesis.verdicts
        ]
        return result

    @staticmethod
    def _status_counts(run_id: int) -> dict[str, int]:
        rows = (
            db.session.query(
                AgentAuditHypothesis.status,
                func.count(AgentAuditHypothesis.id),
            )
            .filter(AgentAuditHypothesis.run_id == run_id)
            .group_by(AgentAuditHypothesis.status)
            .all()
        )
        return {
            _enum_value(status): int(count or 0)
            for status, count in rows
        }

    @staticmethod
    def _skill_counts(run_id: int) -> list[dict]:
        rows = (
            db.session.query(
                AgentAuditHypothesis.skill_key,
                func.count(AgentAuditHypothesis.id),
            )
            .filter(AgentAuditHypothesis.run_id == run_id)
            .group_by(AgentAuditHypothesis.skill_key)
            .order_by(AgentAuditHypothesis.skill_key.asc())
            .all()
        )
        return [
            {
                "skill_key": skill_key,
                "candidate_count": int(count or 0),
            }
            for skill_key, count in rows
        ]

    @staticmethod
    def _deep_review_cost(run_id: int, hypothesis_count: int) -> dict:
        """只均摊 Deep Review 调用成本，避免虚构全链路的单候选价格。"""
        call_count, total_cost, priced_calls = (
            db.session.query(
                func.count(LLMInvocation.id),
                func.coalesce(func.sum(LLMInvocation.total_cost), 0),
                func.coalesce(
                    func.sum(
                        case((LLMInvocation.pricing_version.is_not(None), 1), else_=0)
                    ),
                    0,
                ),
            )
            .filter(
                LLMInvocation.run_id == run_id,
                LLMInvocation.operation == "deep_review",
            )
            .one()
        )
        calls = int(call_count or 0)
        known = calls > 0 and int(priced_calls or 0) == calls
        if not known:
            return {
                "call_count": calls,
                "cost_known": False,
                "total_cost": None,
                "average_per_hypothesis": None,
            }
        total_cost_float = round(float(total_cost or 0), 6)
        return {
            "call_count": calls,
            "cost_known": True,
            "total_cost": total_cost_float,
            "average_per_hypothesis": (
                round(total_cost_float / hypothesis_count, 6)
                if hypothesis_count
                else None
            ),
        }


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _next_action_payload(value: object) -> dict[str, str]:
    """只公开 Critic 的下一步动作标识，不透传内部上下文或 Provider 字段。"""
    if not isinstance(value, dict):
        return {}
    action = value.get("action")
    if not isinstance(action, str):
        return {}
    normalized = action.strip()[:120]
    return {"action": normalized} if normalized else {}
