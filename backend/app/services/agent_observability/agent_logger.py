# -*- coding: utf-8 -*-
"""Agent 行为结构化日志：按时间戳写入滚动文件（可观测性 §19）。

与 AgentEvent（前端业务事件）、AuditEvent（安全审计）分离，本模块只面向
运维排障。安全红线（§19.3）：绝不记录 Prompt、模型响应原文、API Key、
Authorization/Cookie、源码、物理 Snapshot 路径；只记白名单元数据与摘要。
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

AGENT_LOGGER_NAME = "cyberguard.agent"


class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """轮转失败兜底：文件被其他进程/编辑器占用时保留原流继续写，下次再试。

    Windows 下 TimedRotatingFileHandler 轮转需要 rename 独占文件；失败时
    super().doRollover() 已关闭 stream，后续日志会全部丢失。本类捕获异常并
    重新打开原文件，保证"写不丢"优先于"轮转成功"。
    """

    def doRollover(self):
        try:
            super().doRollover()
        except Exception:
            if self.stream is None:
                try:
                    self.stream = self._open()
                except Exception:
                    pass

# 工具 metrics 中允许进入日志的白名单键（其余 metrics 一律丢弃）
_METRIC_SUMMARY_KEYS = frozenset(
    {
        "findings_count",
        "severity_counts",
        "total_files",
        "specialized_sast",
        "generic_only",
        "scanned_with_findings",
        "scanned_no_finding",
        "excluded",
        "skipped",
        "ranked_count",
        "critical",
        "high",
        "file_count",
        "total_bytes",
        "dependencies_count",
        "ecosystems",
        "languages",
    }
)


def configure_agent_logger(app) -> None:
    """为 Agent 行为日志配置按天滚动的文件 handler（幂等，路径变化时重建）。

    多进程（后端 + RQ worker + reloader）共享同一日志文件时，Windows 上
    TimedRotatingFileHandler 轮转 rename 会被其他进程句柄挡住（WinError 32）。
    因此未显式配置 AGENT_LOG_FILE 时按进程分文件（agent-{pid}.log），
    保证轮转与写入互不干扰；显式配置路径仅用于单进程场景（如测试）。
    """
    configured = app.config.get("AGENT_LOG_FILE")
    if not configured:
        log_file = Path(str(app.config.get("LOG_FILE", "logs/app.log")))
        configured = str(log_file.parent / f"agent-{os.getpid()}.log")
    target = str(Path(str(configured)).resolve())

    logger = logging.getLogger(AGENT_LOGGER_NAME)
    for handler in list(logger.handlers):
        if not isinstance(handler, TimedRotatingFileHandler):
            continue
        existing = getattr(handler, "baseFilename", None)
        if existing and str(Path(existing).resolve()) == target:
            return
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    Path(target).parent.mkdir(parents=True, exist_ok=True)
    handler = SafeTimedRotatingFileHandler(
        target,
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(app.config.get("LOG_LEVEL", "INFO"))
    logger.propagate = False


class AgentLogger:
    """结构化行为日志入口；每个方法只记录白名单字段，值经安全规整。"""

    def __init__(self) -> None:
        self._logger = logging.getLogger(AGENT_LOGGER_NAME)

    # ------------------------------------------------------------------ run

    def run_event(self, action: str, run, *, trace_id: str | None = None, **fields) -> None:
        """run 生命周期事件：created/paused/resumed/canceled/completed/failed/partial。"""
        payload = self._base(run, trace_id)
        payload["event"] = action
        payload["status"] = _enum_value(run.status)
        payload["mode"] = _enum_value(run.mode)
        if run.goal_text:
            payload["goal"] = _truncate(run.goal_text, 100)
        payload.update(self._safe_fields(fields))
        self._write(logging.INFO, payload)

    def worker_crash(self, run, *, trace_id: str | None = None) -> None:
        payload = self._base(run, trace_id)
        payload["event"] = "run.worker_crash"
        payload["status"] = _enum_value(run.status)
        self._write(logging.ERROR, payload)

    # ------------------------------------------------------------------ plan

    def plan_created(
        self,
        run,
        *,
        planner_source: str,
        plan_version: int,
        node_count: int,
        trace_id: str | None = None,
        fallback_reason: str | None = None,
        decision_summary: str | None = None,
    ) -> None:
        payload = self._base(run, trace_id)
        payload["event"] = "plan.created"
        payload["planner_source"] = planner_source
        payload["plan_version"] = plan_version
        payload["node_count"] = node_count
        if fallback_reason:
            payload["fallback_reason"] = _truncate(fallback_reason, 200)
        if decision_summary:
            payload["decision_summary"] = _truncate(decision_summary, 200)
        self._write(logging.INFO, payload)

    def plan_repair_failed(
        self,
        run,
        *,
        attempt: int,
        reason: str,
        trace_id: str | None = None,
    ) -> None:
        payload = self._base(run, trace_id)
        payload["event"] = "plan.repair_failed"
        payload["attempt"] = attempt
        payload["reason"] = _truncate(reason, 300)
        self._write(logging.WARNING, payload)

    def plan_replanned(
        self,
        run,
        *,
        reason_code: str,
        plan_version: int,
        supersedes_version: int | None,
        decision_type: str,
        trace_id: str | None = None,
    ) -> None:
        payload = self._base(run, trace_id)
        payload["event"] = "plan.replanned"
        payload["reason_code"] = reason_code
        payload["plan_version"] = plan_version
        payload["supersedes_version"] = supersedes_version
        payload["decision_type"] = decision_type
        self._write(logging.INFO, payload)

    # ------------------------------------------------------------------ tool

    def tool_event(
        self,
        action: str,
        run,
        *,
        node_key: str,
        tool_name: str,
        status: str,
        latency_ms: int | None,
        trace_id: str | None = None,
        step_execution_id: int | None = None,
        tool_call_id: int | None = None,
        summary: str | None = None,
        metrics: dict | None = None,
        warning_codes: list | None = None,
        error_code: str | None = None,
        artifact_refs: list | None = None,
    ) -> None:
        """工具调用记录：只记 metrics 白名单摘要与状态元数据，不记原文/路径列表。"""
        payload = self._base(run, trace_id)
        payload["event"] = action
        payload["node_key"] = node_key
        payload["tool_name"] = tool_name
        payload["status"] = status
        if step_execution_id is not None:
            payload["step_execution_id"] = step_execution_id
        if tool_call_id is not None:
            payload["tool_call_id"] = tool_call_id
        if latency_ms is not None:
            payload["latency_ms"] = latency_ms
        if summary:
            payload["summary"] = _truncate(summary, 200)
        metric_summary = _metric_summary(metrics)
        if metric_summary:
            payload["metrics"] = metric_summary
        if warning_codes:
            payload["warning_codes"] = list(warning_codes)[:10]
        if error_code:
            payload["error_code"] = error_code
        if artifact_refs:
            payload["artifact_types"] = list(artifact_refs)[:10]
        self._write(logging.INFO if status == "succeeded" else logging.WARNING, payload)

    # ------------------------------------------------------------------ llm

    def llm_event(
        self,
        action: str,
        run,
        *,
        operation: str,
        provider: str,
        model: str | None = None,
        status: str,
        trace_id: str | None = None,
        warning_code: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_input_tokens: int = 0,
        reasoning_tokens: int = 0,
        total_tokens: int = 0,
        usage_source: str | None = None,
        cost: float = 0.0,
        currency: str | None = None,
        latency_ms: int | None = None,
        first_token_latency_ms: int | None = None,
        input_digest: str | None = None,
        output_digest: str | None = None,
        prompt_template_version: str | None = None,
    ) -> None:
        """LLM 调用记录：只记 token/成本/延迟/digest，绝不记 prompt 与响应原文。"""
        payload = self._base(run, trace_id)
        payload["event"] = action
        payload["operation"] = operation
        payload["provider"] = provider
        if model:
            payload["model"] = model
        payload["status"] = status
        if warning_code:
            payload["warning_code"] = warning_code
        if input_tokens:
            payload["input_tokens"] = input_tokens
        if output_tokens:
            payload["output_tokens"] = output_tokens
        if cached_input_tokens:
            payload["cached_input_tokens"] = cached_input_tokens
        if reasoning_tokens:
            payload["reasoning_tokens"] = reasoning_tokens
        if total_tokens:
            payload["total_tokens"] = total_tokens
        if usage_source:
            payload["usage_source"] = usage_source
        if cost:
            payload["cost"] = round(float(cost), 6)
        if currency:
            payload["currency"] = currency
        if latency_ms is not None:
            payload["latency_ms"] = latency_ms
        if first_token_latency_ms is not None:
            payload["first_token_latency_ms"] = first_token_latency_ms
        if input_digest:
            payload["input_digest"] = input_digest
        if output_digest:
            payload["output_digest"] = output_digest
        if prompt_template_version:
            payload["prompt_template_version"] = prompt_template_version
        self._write(logging.INFO if status == "success" else logging.WARNING, payload)

    # ------------------------------------------------------------------ budget

    def budget_blocked(
        self,
        run,
        *,
        reached_codes: list[str],
        ratios: dict,
        trace_id: str | None = None,
    ) -> None:
        payload = self._base(run, trace_id)
        payload["event"] = "budget.blocked"
        payload["reached_codes"] = reached_codes
        payload["ratios"] = ratios
        self._write(logging.WARNING, payload)

    # ------------------------------------------------------------------ helpers

    def _base(self, run, trace_id: str | None) -> dict:
        payload: dict[str, Any] = {
            "run_id": run.id,
            "workspace_id": run.workspace_id,
            "project_id": run.project_id,
            "user_id": run.created_by,
        }
        if trace_id:
            payload["trace_id"] = trace_id
        return payload

    def _safe_fields(self, fields: dict) -> dict:
        """只保留标量/列表/字典字段，丢弃不可序列化对象，防注入与异常。"""
        safe: dict[str, Any] = {}
        for key, value in fields.items():
            if value is None or isinstance(value, (str, int, float, bool)):
                safe[key] = value if isinstance(value, str) else value
            elif isinstance(value, (list, dict)):
                safe[key] = value
        return safe

    def _write(self, level: int, payload: dict) -> None:
        payload["ts"] = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
        payload["level"] = logging.getLevelName(level)
        try:
            self._logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))
        except (TypeError, ValueError):
            payload["_redacted"] = "unserializable"
            self._logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))


def _metric_summary(metrics: dict | None) -> dict:
    if not isinstance(metrics, dict):
        return {}
    return {key: metrics[key] for key in _METRIC_SUMMARY_KEYS if key in metrics}


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _truncate(value: str, limit: int) -> str:
    text = str(value)
    return text[:limit] + "…" if len(text) > limit else text
