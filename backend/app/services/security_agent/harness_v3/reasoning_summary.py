# -*- coding: utf-8 -*-
"""Harness V3 受控 Reasoning Summary。

该模块只持久化代码可验证的审计事实：假设标识、行动理由、证据缺口和下一步。
Provider 原始 reasoning、Prompt、源码和 Observation 原文均不能进入这里。
"""
from __future__ import annotations

from datetime import datetime

from app import db
from app.models.agent_hypothesis import AgentAuditHypothesis
from app.models.agent_items import AgentItem
from app.services.security_agent.harness_v3.evidence_critic import CriticDecision
from app.services.security_agent.timeline.contracts import (
    EVENT_REASONING_SUMMARY_COMPLETED,
    EVENT_REASONING_SUMMARY_DELTA,
    EVENT_REASONING_SUMMARY_STARTED,
)
from app.services.security_agent.timeline.event_writer import EventWriter

_MAX_FIELD_CHARS = 360

_NEXT_STEP_TEXT = {
    "complete_hypothesis": "证据条件已满足，结束该候选审查并等待人工复核。",
    "request_supplemental_review": "在同一授权范围内执行一次补充审查。",
    "close_as_needs_evidence": "证据不足，安全收口为待补证据。",
    "stop_for_budget": "预算已耗尽，停止继续扩展该候选。",
    "reject_invalid_hypothesis": "假设契约无效，拒绝继续审查。",
}


class V3ReasoningSummaryService:
    """生成可回放的 V3 决策摘要，但绝不接收 Provider 原始文本。"""

    def __init__(self, writer: EventWriter | None = None) -> None:
        self._writer = writer or EventWriter()

    def emit_action(
        self,
        run,
        hypothesis: AgentAuditHypothesis,
        *,
        review_kind: str,
        trace_id: str | None,
    ) -> AgentItem:
        """记录一次有界 ReAct 行动的受控理由。"""
        phase = f"{review_kind}-action"
        review_label = "主审" if review_kind == "primary" else "补充审查"
        return self._emit(
            run,
            hypothesis,
            phase=phase,
            action_reason=(
                f"按固定技能 {hypothesis.skill_key} 执行{review_label}，"
                "只读取该假设已授权的代码范围。"
            ),
            evidence_gap="等待工具 Observation 返回受授权代码位置与所需结构化证据条件。",
            next_step=f"执行 {review_label}。",
            trace_id=trace_id,
        )

    def emit_decision(
        self,
        run,
        hypothesis: AgentAuditHypothesis,
        decision: CriticDecision,
        *,
        review_kind: str,
        trace_id: str | None,
    ) -> AgentItem:
        """记录独立 Critic 的安全结论，不复制 Observation 或 Provider 文字。"""
        next_action = str(decision.next_action.get("action") or "")
        gaps = "；".join(decision.evidence_gaps) or "未发现额外证据缺口。"
        return self._emit(
            run,
            hypothesis,
            phase=f"{review_kind}-critic",
            action_reason="Critic 仅核验声明证据是否具有匹配的授权代码位置与角色。",
            evidence_gap=gaps,
            next_step=_NEXT_STEP_TEXT.get(next_action, "结束本轮受限审查。"),
            trace_id=trace_id,
        )

    def _emit(
        self,
        run,
        hypothesis: AgentAuditHypothesis,
        *,
        phase: str,
        action_reason: str,
        evidence_gap: str,
        next_step: str,
        trace_id: str | None,
    ) -> AgentItem:
        public_id = f"v3-rs-{run.id}-{hypothesis.id}-{phase}"
        existing = AgentItem.query.filter_by(
            run_id=run.id,
            public_id=public_id,
        ).first()
        if existing is not None:
            return existing

        summary = {
            "hypothesis_id": hypothesis.id,
            "action_reason": _bounded(action_reason),
            "evidence_gap": _bounded(evidence_gap),
            "next_step": _bounded(next_step),
            "sensitive_level": "internal",
        }
        content = (
            f"行动理由：{summary['action_reason']}\n"
            f"证据缺口：{summary['evidence_gap']}\n"
            f"下一步：{summary['next_step']}"
        )
        item = AgentItem(
            public_id=public_id,
            run_id=run.id,
            iteration=int(run.iteration_count or 0),
            item_type="reasoning_summary",
            status="completed",
            content_redacted=content,
            summary_json=summary,
            sensitive_level="internal",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.session.add(item)
        db.session.flush()
        payload = {
            "sensitive_level": "internal",
            "summary": summary,
        }
        self._writer.emit(
            run,
            event_type=EVENT_REASONING_SUMMARY_STARTED,
            item_id=public_id,
            iteration=item.iteration,
            payload=payload,
            trace_id=trace_id,
        )
        self._writer.emit(
            run,
            event_type=EVENT_REASONING_SUMMARY_DELTA,
            item_id=public_id,
            parent_item_id=public_id,
            iteration=item.iteration,
            payload={
                "delta": content,
                "sensitive_level": "internal",
            },
            trace_id=trace_id,
        )
        self._writer.emit(
            run,
            event_type=EVENT_REASONING_SUMMARY_COMPLETED,
            item_id=public_id,
            iteration=item.iteration,
            payload=payload,
            trace_id=trace_id,
        )
        return item


def _bounded(value: str) -> str:
    text = str(value or "").strip()
    return text[:_MAX_FIELD_CHARS]
