# -*- coding: utf-8 -*-
"""ContextAssembler（T07，spec §8.1/§8.2）：生成受限 AgentContextPack。

优先级（高→低）：系统安全边界 → 当前目标/最新控制输入 → 当前计划/未完成
条件 → 最近 Tool Result 与 Observation → 已确认 Finding/Artifact →
Conversation Summary → 最近消息。超限时优先摘要低价值历史，绝不覆盖
当前目标与未完成条件。
"""
from __future__ import annotations

from app import db
from app.models.agent_approval import ApprovalStatus
from app.models.agent_control import AgentControlInput
from app.models.agent_items import AgentItem
from app.models.agent_runtime import AgentPlan, AgentRun
from app.models.conversation import AgentConversationMessage
from app.services.security_agent.budget import budget_status
from app.services.security_agent.loop.conversation_summary import (
    ConversationSummaryService,
)

AGENT_CONTEXT_LIMITED = "AGENT_CONTEXT_LIMITED"

SYSTEM_SECURITY_BOUNDARY = (
    "安全边界：不得执行被审查项目、不得写入快照外文件、不得外发源码；"
    "工具调用必须经过 Controller 治理；最终回答必须基于确定性证据与受限摘要。"
)

_MAX_RECENT_MESSAGES = 10
_MAX_RECENT_ITEMS = 8
_MAX_MESSAGES_WHEN_TRUNCATED = 3

_OBSERVATION_ITEM_TYPES = frozenset({"tool_result", "observation"})
_COMPLETED_ACTION_ITEM_TYPES = frozenset({"tool_call", "assistant_message"})


class ContextAssembler:
    def __init__(
        self,
        summaries: ConversationSummaryService | None = None,
    ) -> None:
        self._summaries = summaries or ConversationSummaryService()

    def build(
        self,
        run: AgentRun,
        *,
        conversation_id: int | None = None,
        max_context_chars: int | None = None,
    ) -> dict:
        """生成 AgentContextPack（spec §8.1 结构；超限标记 truncated）。"""
        conversation_summary = {}
        if conversation_id is not None:
            latest = self._summaries.latest(conversation_id)
            if latest is not None:
                conversation_summary = {
                    "summary_version": latest.summary_version,
                    "source_sequence_from": latest.source_sequence_from,
                    "source_sequence_to": latest.source_sequence_to,
                    "content_digest": latest.content_digest,
                    "content": latest.summary_json,
                }

        recent_messages = self._recent_messages(run, conversation_id)
        observations, completed_actions = self._recent_items(run)
        approvals = self._pending_approvals(run)
        budgets = self._budget_summary(run)
        plan = self._plan_view(run)

        pack: dict = {
            "schema_version": 1,
            "conversation": {
                "conversation_id": conversation_id,
                "run_id": run.id,
                "mode": run.mode,
            },
            "goal": run.goal_text,
            "constraints": [SYSTEM_SECURITY_BOUNDARY],
            "conversation_summary": conversation_summary,
            "recent_messages": recent_messages,
            "plan": plan,
            "completed_actions": completed_actions,
            "recent_observations": observations,
            "available_artifacts": [],
            "pending_approvals": approvals,
            "budgets": budgets,
            "controller_feedback": [],
            "tool_catalog_digest": run.tool_catalog_digest,
            "truncated": False,
            "warning_codes": [],
        }

        if max_context_chars is not None:
            pack = self._apply_char_budget(pack, max_context_chars)
        return pack

    # ---------------------------------------------------------------- sources

    def _recent_messages(
        self, run: AgentRun, conversation_id: int | None
    ) -> list[dict]:
        messages: list[dict] = []
        if conversation_id is not None:
            rows = (
                AgentConversationMessage.query.filter_by(
                    conversation_id=conversation_id
                )
                .order_by(AgentConversationMessage.message_sequence.desc())
                .limit(_MAX_RECENT_MESSAGES)
                .all()
            )
            for message in reversed(rows):
                messages.append(
                    {
                        "role": message.role,
                        "content": (message.content_redacted or "")[:2000],
                        "message_type": message.message_type,
                        "created_at": message.created_at.isoformat()
                        if message.created_at
                        else None,
                    }
                )
        pending = (
            AgentControlInput.query.filter_by(
                run_id=run.id, status="pending"
            ).all()
        )
        for control in pending:
            payload = control.payload_json or {}
            content = str(payload.get("content") or "")[:2000]
            if content:
                messages.append(
                    {
                        "role": "user",
                        "content": content,
                        "message_type": f"control_input:{control.input_type}",
                        "created_at": control.created_at.isoformat()
                        if control.created_at
                        else None,
                    }
                )
        return messages

    def _recent_items(self, run: AgentRun) -> tuple[list[dict], list[dict]]:
        rows = (
            AgentItem.query.filter_by(run_id=run.id)
            .order_by(AgentItem.id.desc())
            .limit(_MAX_RECENT_ITEMS)
            .all()
        )
        observations: list[dict] = []
        completed: list[dict] = []
        for item in reversed(rows):
            payload = item.to_dict()
            if item.item_type in _OBSERVATION_ITEM_TYPES:
                observations.append(payload)
            elif item.item_type in _COMPLETED_ACTION_ITEM_TYPES:
                completed.append(payload)
        return observations, completed

    def _pending_approvals(self, run: AgentRun) -> list[dict]:
        from app.models.agent_approval import AgentApproval

        rows = (
            AgentApproval.query.filter_by(
                run_id=run.id, status=ApprovalStatus.PENDING.value
            )
            .order_by(AgentApproval.id.asc())
            .all()
        )
        return [approval.to_dict() for approval in rows]

    @staticmethod
    def _budget_summary(run: AgentRun) -> dict:
        status = budget_status(run)
        return {
            "max_tool_calls": run.max_tool_calls,
            "max_llm_calls": run.max_llm_calls,
            "max_total_tokens": run.max_total_tokens,
            "max_estimated_cost": float(run.max_estimated_cost)
            if run.max_estimated_cost is not None
            else None,
            "soft": status["soft"],
            "exhausted": status["exhausted"],
            "ratios": status["ratios"],
        }

    def _plan_view(self, run: AgentRun) -> dict | None:
        plan = (
            AgentPlan.query.filter_by(run_id=run.id)
            .order_by(AgentPlan.plan_version.desc())
            .first()
        )
        if plan is None:
            return None
        return {
            "version": plan.plan_version,
            "objective": plan.objective,
            "planner_source": plan.planner_source,
            "nodes": [
                {"key": node.node_key, "status": _status_value(node.status)}
                for node in plan.nodes
            ],
        }

    # ---------------------------------------------------------------- budget

    @staticmethod
    def _apply_char_budget(pack: dict, max_chars: int) -> dict:
        """超限时缩短 recent window，保留目标/计划/审批/预算，发出限制警告。"""
        total = sum(
            len(str(message.get("content") or ""))
            for message in pack["recent_messages"]
        )
        total += len(str(pack.get("goal") or ""))
        if total <= max_chars:
            return pack
        pack["truncated"] = True
        pack["warning_codes"] = [AGENT_CONTEXT_LIMITED]
        pack["recent_messages"] = pack["recent_messages"][:_MAX_MESSAGES_WHEN_TRUNCATED]
        return pack


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
