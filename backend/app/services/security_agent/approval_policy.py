# -*- coding: utf-8 -*-
"""审批策略（A7）：什么操作需要审批、谁能审批、过期如何处理。

- requires_approval：预算硬限且计划未完成 → budget_increase 审批。
- can_resolve：high/medium 风险操作仅 Owner/Security Admin 可批；
  low 风险允许 workspace 成员（预留，当前审批均为 medium）。
- 拒绝/过期路线：拒绝后不执行受限操作；过期自动标记并提示（不自动放行）。
"""
from __future__ import annotations

from app.models.agent_approval import ApprovalOperationType, ApprovalRiskLevel

APPROVAL_EXPIRES_MINUTES = 30

_OPERATION_LABELS = {
    ApprovalOperationType.BUDGET_INCREASE.value: "预算超限（继续执行）",
    ApprovalOperationType.REMOTE_SOURCE_SEND.value: "远程源码发送",
    ApprovalOperationType.REMEDIATION_GENERATION.value: "修复建议生成",
    ApprovalOperationType.TOOL_EXECUTION.value: "敏感工具执行",
}

_RISK_BY_OPERATION = {
    ApprovalOperationType.BUDGET_INCREASE.value: ApprovalRiskLevel.MEDIUM.value,
    ApprovalOperationType.REMOTE_SOURCE_SEND.value: ApprovalRiskLevel.HIGH.value,
    ApprovalOperationType.REMEDIATION_GENERATION.value: ApprovalRiskLevel.LOW.value,
    ApprovalOperationType.TOOL_EXECUTION.value: ApprovalRiskLevel.MEDIUM.value,
}

# 需要 Owner/Security Admin 才能批准的风险级别
_PRIVILEGED_RISK_LEVELS = {ApprovalRiskLevel.HIGH.value, ApprovalRiskLevel.MEDIUM.value}


def operation_label(operation_type: str) -> str:
    return _OPERATION_LABELS.get(operation_type, operation_type)


def risk_for_operation(operation_type: str) -> str:
    return _RISK_BY_OPERATION.get(operation_type, ApprovalRiskLevel.MEDIUM.value)


def requires_approval(*, budget_exhausted: bool, plan_incomplete: bool) -> bool:
    """预算硬限且还有未执行计划节点时需要审批。"""
    return bool(budget_exhausted and plan_incomplete)


def can_resolve(approval, role: str | None) -> bool:
    """审批人角色校验：high/medium 需 owner/admin，low 需 workspace 成员。"""
    if approval.risk_level in _PRIVILEGED_RISK_LEVELS:
        return role in {"owner", "admin"}
    return role in {"owner", "admin", "analyst"}
