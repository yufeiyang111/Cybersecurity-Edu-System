# -*- coding: utf-8 -*-
"""Harness V3 的受版本控制审计技能目录。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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
        required_evidence=(
            "untrusted_input",
            "query_or_command_sink",
            "parameterization_or_absence",
        ),
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
        required_evidence=(
            "untrusted_path_or_url",
            "file_or_network_sink",
            "allowlist_or_absence",
        ),
        falsification_conditions=("根目录约束", "内部地址阻断", "安全路径规范化"),
        max_attempts=2,
    ),
    AuditSkill(
        key="unsafe_runtime_configuration",
        title="运行时危险配置验证",
        cwe_tags=("CWE-16", "CWE-489"),
        trigger_signals=("debug", "configuration", "cwe-489", "exposure"),
        languages=("python", "javascript", "typescript", "java", "go"),
        frameworks=("flask", "django", "express", "spring", "gin"),
        recommended_tools=("get_findings", "search_code", "run_deep_review"),
        required_evidence=(
            "unsafe_runtime_setting",
            "production_guard_or_absence",
        ),
        falsification_conditions=(
            "危险运行时开关仅在受控开发环境启用",
            "生产环境存在显式禁用守卫",
            "部署配置覆盖并关闭危险开关",
        ),
        max_attempts=2,
    ),
)


class AuditSkillCatalog:
    """只读技能目录；调用方只能按 key 查询既有定义。"""

    VERSION = "v3.2"

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

    def select(
        self,
        *,
        snapshot_summary: object | None,
        evidence_summary: object | None,
        run_mode: str,
        finding_signals: Iterable[object] = (),
        limit: int = 3,
    ) -> tuple[AuditSkill, ...]:
        """从固定技能中选择与确定性扫描元数据最匹配的少量候选。

        只读取 finding 的规则名、分类、CWE、路径和消息等元数据，绝不读取源码切片；
        选择阈值采用相对最高分，避免一个很弱的关键字把无关技能一起扩展为伪多 Agent。
        """
        del snapshot_summary, evidence_summary
        if str(run_mode or "").strip().lower() not in {"hybrid", "deep_audit"}:
            return ()
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            return ()

        texts = tuple(_signal_text(signal) for signal in finding_signals)
        texts = tuple(text for text in texts if text)
        if not texts:
            return ()

        scored: list[tuple[int, AuditSkill]] = []
        for skill in self._skills:
            score = sum(
                1
                for trigger in skill.trigger_signals
                if any(trigger.lower() in text for text in texts)
            )
            if score > 0:
                scored.append((score, skill))
        if not scored:
            return ()

        highest_score = max(score for score, _ in scored)
        threshold = max(1, (highest_score * 3 + 4) // 5)
        selected = [
            (score, skill)
            for score, skill in scored
            if score >= threshold
        ]
        selected.sort(key=lambda item: (-item[0], item[1].key))
        return tuple(skill for _, skill in selected[:limit])


def _signal_text(signal: object) -> str:
    """归一化可公开的扫描元数据，不返回或存储源码内容。"""
    searchable = getattr(signal, "searchable_text", None)
    if callable(searchable):
        value = searchable()
        return str(value or "").lower()
    if isinstance(signal, dict):
        fields = (
            signal.get("rule_id"),
            signal.get("category"),
            signal.get("cwe_id"),
            signal.get("file_path"),
            signal.get("message"),
        )
    else:
        fields = (
            getattr(signal, "rule_id", None),
            getattr(signal, "category", None),
            getattr(signal, "cwe_id", None),
            getattr(signal, "file_path", None),
            getattr(signal, "message", None),
        )
    return " ".join(str(value or "") for value in fields).lower()
