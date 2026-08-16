# -*- coding: utf-8 -*-
"""Harness V3 的受版本控制审计技能目录。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditSkill:
    """单个审计技能的冻结定义，不能由用户或模型在运行时注册。"""

    key: str
    title: str
    cwe_tags: tuple[str, ...]
    trigger_signals: tuple[str, ...]
    languages: tuple[str, ...]
    frameworks: tuple[str, ...]
    recommended_tools: tuple[str, ...]
    required_evidence: tuple[str, ...]
    falsification_conditions: tuple[str, ...]
    max_attempts: int


DEFAULT_AUDIT_SKILLS: tuple[AuditSkill, ...] = (
    AuditSkill(
        key="authorization_boundary",
        title="授权边界验证",
        cwe_tags=("CWE-284", "CWE-639"),
        trigger_signals=("authorization", "permission", "owner", "tenant", "role"),
        languages=("python", "javascript", "typescript", "java", "go"),
        frameworks=("flask", "django", "express", "spring", "gin"),
        recommended_tools=("get_findings", "search_code", "run_deep_review"),
        required_evidence=("subject", "object", "authorization_guard"),
        falsification_conditions=("对象绑定当前主体", "服务端授权守卫覆盖路径"),
        max_attempts=2,
    ),
    AuditSkill(
        key="injection_dataflow",
        title="注入数据流验证",
        cwe_tags=("CWE-89", "CWE-78", "CWE-79"),
        trigger_signals=("sql", "query", "command", "shell", "template"),
        languages=("python", "javascript", "typescript", "java", "go"),
        frameworks=("flask", "django", "express", "spring", "gin"),
        recommended_tools=("get_findings", "search_code", "run_deep_review"),
        required_evidence=("untrusted_input", "query_or_command_sink", "parameterization_or_absence"),
        falsification_conditions=("参数化绑定", "严格 allowlist", "输入不可控"),
        max_attempts=2,
    ),
    AuditSkill(
        key="unsafe_execution_deserialization",
        title="危险执行与反序列化验证",
        cwe_tags=("CWE-78", "CWE-94", "CWE-502"),
        trigger_signals=("eval", "exec", "deserialize", "pickle", "yaml"),
        languages=("python", "javascript", "typescript", "java", "go"),
        frameworks=("flask", "django", "express", "spring", "gin"),
        recommended_tools=("get_findings", "search_code", "run_deep_review"),
        required_evidence=("untrusted_input", "dangerous_sink", "guard_or_absence"),
        falsification_conditions=("固定输入", "安全解析器", "受控 allowlist"),
        max_attempts=2,
    ),
    AuditSkill(
        key="untrusted_file_network",
        title="不可信文件与网络边界验证",
        cwe_tags=("CWE-22", "CWE-73", "CWE-918"),
        trigger_signals=("path", "file", "upload", "url", "request", "redirect"),
        languages=("python", "javascript", "typescript", "java", "go"),
        frameworks=("flask", "django", "express", "spring", "gin"),
        recommended_tools=("get_findings", "search_code", "run_deep_review"),
        required_evidence=("untrusted_path_or_url", "file_or_network_sink", "allowlist_or_absence"),
        falsification_conditions=("根目录约束", "内部地址阻断", "安全路径规范化"),
        max_attempts=2,
    ),
)


class AuditSkillCatalog:
    """只读技能目录；调用方只能按 key 查询既有定义。"""

    VERSION = "v3.1"

    def __init__(self, skills: tuple[AuditSkill, ...] = DEFAULT_AUDIT_SKILLS) -> None:
        self._skills = tuple(skills)
        self._by_key = {skill.key: skill for skill in self._skills}
        if len(self._by_key) != len(self._skills):
            raise ValueError("审计技能 key 不允许重复")

    def keys(self) -> tuple[str, ...]:
        return tuple(skill.key for skill in self._skills)

    def get(self, key: str) -> AuditSkill | None:
        return self._by_key.get(str(key or ""))

    def require(self, key: str) -> AuditSkill:
        skill = self.get(key)
        if skill is None:
            raise KeyError(f"未注册审计技能：{key}")
        return skill

    def all(self) -> tuple[AuditSkill, ...]:
        return self._skills