# -*- coding: utf-8 -*-
"""Agent LLM 分析服务：把多轮对话接入统一 LLM Provider 与事件契约。

职责边界（独立于 runner / tools，避免巨型模块）：
- 通过 select_provider(user_id=run.created_by, operation="agent") 获取 Provider，
  本模块绝不实例化任何具体 Provider。
- 汇总确定性工具证据（扫描发现、覆盖报告、风险排序）生成结构化分析请求。
- 流式消费 LLMStreamChunk：思维链增量走 llm.reasoning_delta 直通事件，
  回复文本累积后写入 AgentMessage(llm_analysis) 并随 llm.completed 事件下发，
  调用日志复用 llm/call_logging 的 observe_provider 包装（operation="agent"）。
- Provider 缺失/超时/解析失败时显式降级：返回确定性摘要文本，并发出
  llm.failed + warning.raised，绝不伪装成模型分析成功。
- 不记录 API Key、Prompt 或响应原文到日志；只写结构化安全日志。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app import db
from app.models.agent_runtime import AgentArtifact, AgentMessage, AgentRun, AgentRunStatus
from app.models.conversation import AgentConversationMessage, AgentTurn
from app.services.agent_observability import AgentLogger
from app.services.llm.contracts import LLMRequest
from app.services.llm.provider_selector import resolve_provider_max_tokens, select_provider
from app.services.llm.redactor import redact_reasoning
from app.services.llm.usage_normalizer import normalize_usage
from app.services.security_agent.contracts import (
    EVENT_LLM_COMPLETED,
    EVENT_LLM_FAILED,
    EVENT_LLM_REASONING_DELTA,
    EVENT_LLM_STARTED,
    EVENT_LLM_USAGE,
    EVENT_WARNING_RAISED,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.llm_invocation import (
    USAGE_SOURCE_ESTIMATED,
    USAGE_SOURCE_PROVIDER_REPORTED,
    record_invocation,
)
from app.services.security_agent.prompt_templates.planner_v1 import prompt_digest

logger = logging.getLogger(__name__)

AGENT_OPERATION = "agent"
INVOCATION_OPERATION = "agent_analysis"
ANALYSIS_MESSAGE_TYPE = "llm_analysis"
MAX_ANALYSIS_CHARS = 6000
MAX_EVIDENCE_CHARS = 12000
STOP_POLL_EVERY_CHUNKS = 10

# Provider 警告码 -> Agent 域警告码（AGENT_WARNING_CODES 白名单内）
_PROVIDER_WARNING_MAP = {
    "LLM_PROVIDER_TIMEOUT": "AGENT_PROVIDER_TIMEOUT",
    "LLM_PROVIDER_RATE_LIMITED": "AGENT_PROVIDER_RATE_LIMITED",
    "LLM_OUTPUT_INVALID": "AGENT_PROVIDER_INVALID_RESPONSE",
    "LLM_PROVIDER_RESPONSE_INVALID": "AGENT_PROVIDER_INVALID_RESPONSE",
    "LLM_PROVIDER_NON_SUCCESS": "AGENT_PROVIDER_UNHEALTHY",
    "LLM_PROVIDER_REQUEST_FAILED": "AGENT_PROVIDER_UNHEALTHY",
    "LLM_PROVIDER_RESPONSE_TOO_LARGE": "AGENT_PROVIDER_INVALID_RESPONSE",
}

_WARNING_LABELS = {
    "AGENT_PROVIDER_NOT_CONFIGURED": "尚未配置 LLM Provider",
    "AGENT_PROVIDER_TIMEOUT": "LLM Provider 调用超时",
    "AGENT_PROVIDER_UNHEALTHY": "LLM Provider 调用失败",
    "AGENT_PROVIDER_RATE_LIMITED": "LLM Provider 触发限流",
    "AGENT_PROVIDER_INVALID_RESPONSE": "LLM Provider 返回内容无法解析",
}

# 需要裁剪的列表字段（保留 Top N 防止证据过大）
_LIST_TRIM_KEYS = {"top_findings", "top_ranked", "top_extensions", "top_directories", "languages"}


class AgentLlmAnalysisService:
    """面向一次 run 的 LLM 分析编排（幂等，结果落库且可经 SSE 重放）。"""

    def __init__(self, events: EventService) -> None:
        self._events = events
        self._agent_log = AgentLogger()

    # ------------------------------------------------------------------ public

    def analyze(self, run: AgentRun, *, trace_id: str) -> dict | None:
        """对一次 run 执行 LLM 分析；返回分析 payload 或 None（已存在/已停止）。"""
        if self._has_analysis(run.id):
            return None
        if self._run_stopped(run.id):
            return None

        goal = self._turn_input(run) or run.goal_text or ""
        evidence = self._collect_evidence(run.id)

        provider = select_provider(user_id=run.created_by, operation=AGENT_OPERATION)
        if provider is None:
            return self._degrade(run, "AGENT_PROVIDER_NOT_CONFIGURED", evidence, trace_id)

        self._events.emit(
            run,
            EVENT_LLM_STARTED,
            {
                "provider": getattr(provider, "provider_name", "unknown"),
                "model": getattr(provider, "model", None),
                "operation": AGENT_OPERATION,
            },
            trace_id=trace_id,
        )
        self._agent_log.llm_event(
            "llm.started",
            run,
            operation=INVOCATION_OPERATION,
            provider=getattr(provider, "provider_name", "unknown"),
            model=getattr(provider, "model", None),
            status="started",
            trace_id=trace_id,
        )
        request = self._build_request(goal, evidence, provider)
        self._last_prompt = request.prompt
        try:
            return self._consume_stream(run, provider, request, evidence, trace_id)
        except Exception as exc:
            # 流式消费意外失败：记录结构化日志后安全降级，不让 worker 崩溃
            logger.warning(
                "Agent LLM stream crashed (run_id=%s, error_type=%s)",
                run.id,
                type(exc).__name__,
            )
            return self._degrade(
                run,
                "AGENT_PROVIDER_UNHEALTHY",
                evidence,
                trace_id,
                provider=provider,
            )

    # ------------------------------------------------------------------ stream

    def _consume_stream(
        self,
        run: AgentRun,
        provider: object,
        request: LLMRequest,
        evidence: dict,
        trace_id: str,
    ) -> dict:
        analysis_parts: list[str] = []
        usage: dict[str, Any] = {}
        warning_code: str | None = None
        chunk_index = 0

        for chunk in provider.generate_stream(request):
            chunk_index += 1
            if chunk.reasoning_delta:
                # 思维链直通前必须脱敏；无法安全脱敏的增量直接丢弃
                safe_delta = redact_reasoning(chunk.reasoning_delta)
                if safe_delta:
                    self._events.emit(
                        run,
                        EVENT_LLM_REASONING_DELTA,
                        {"delta": safe_delta},
                        trace_id=trace_id,
                    )
            if chunk.delta:
                analysis_parts.append(chunk.delta)
            if isinstance(chunk.usage, dict) and chunk.usage:
                usage = chunk.usage
            if chunk.warning_code:
                warning_code = chunk.warning_code
            if chunk.finished:
                break
            if chunk_index % STOP_POLL_EVERY_CHUNKS == 0 and self._run_stopped(run.id):
                # 中途被暂停/取消：回滚已 emit 的增量事件，恢复后重新分析
                db.session.rollback()
                return {"stopped": True, "degraded": True}

        if warning_code:
            agent_code = _PROVIDER_WARNING_MAP.get(warning_code, "AGENT_PROVIDER_UNHEALTHY")
            return self._degrade(
                run,
                agent_code,
                evidence,
                trace_id,
                warning_code=warning_code,
                usage=usage,
                provider=provider,
            )

        analysis = "".join(analysis_parts).strip()
        if not analysis:
            return self._degrade(
                run,
                "AGENT_PROVIDER_INVALID_RESPONSE",
                evidence,
                trace_id,
                warning_code="LLM_PROVIDER_RESPONSE_INVALID",
                usage=usage,
                provider=provider,
            )

        normalized = normalize_usage(usage) or {}
        input_tokens = int(normalized.get("prompt_tokens") or 0)
        output_tokens = int(normalized.get("completion_tokens") or 0)
        if not normalized:
            output_tokens = max(0, len(analysis) // 4)
        invocation = record_invocation(
            run,
            provider=provider,
            operation=INVOCATION_OPERATION,
            status="success",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=int(normalized.get("cached_tokens") or 0),
            cache_creation_tokens=int(normalized.get("cache_write_tokens") or 0),
            reasoning_tokens=_nested_usage_int(
                usage, "reasoning_tokens", "completion_tokens_details.reasoning_tokens"
            ),
            total_tokens=int(normalized.get("total_tokens") or 0) or input_tokens + output_tokens,
            usage_source=USAGE_SOURCE_PROVIDER_REPORTED if normalized else USAGE_SOURCE_ESTIMATED,
            input_digest=prompt_digest(request.prompt),
            output_digest=prompt_digest(analysis),
            prompt_template_version="analysis-v1",
        )
        self._agent_log.llm_event(
            "llm.completed",
            run,
            operation=INVOCATION_OPERATION,
            provider=getattr(provider, "provider_name", "unknown"),
            model=getattr(provider, "model", None),
            status="success",
            input_tokens=invocation.input_tokens,
            output_tokens=invocation.output_tokens,
            cached_input_tokens=invocation.cached_input_tokens,
            reasoning_tokens=invocation.reasoning_tokens,
            total_tokens=invocation.total_tokens,
            usage_source=invocation.usage_source,
            cost=float(invocation.total_cost or 0),
            currency=invocation.currency,
            latency_ms=invocation.latency_ms,
            first_token_latency_ms=invocation.first_token_latency_ms,
            input_digest=invocation.input_digest,
            output_digest=invocation.output_digest,
            prompt_template_version="analysis-v1",
            trace_id=trace_id,
        )
        summary = analysis[:MAX_ANALYSIS_CHARS]
        db.session.add(
            AgentMessage(
                run_id=run.id,
                role="agent",
                content=summary,
                message_type=ANALYSIS_MESSAGE_TYPE,
            )
        )
        payload = {
            "analysis": summary,
            "provider": getattr(provider, "provider_name", "unknown"),
            "model": getattr(provider, "model", None),
            "degraded": False,
            "usage": _usage_payload(normalized, usage),
        }
        self._events.emit(
            run,
            EVENT_LLM_USAGE,
            {
                "tokens": payload["usage"]["tokens"],
                "input_tokens": payload["usage"]["input_tokens"],
                "output_tokens": payload["usage"]["output_tokens"],
                "reasoning_tokens": payload["usage"]["reasoning_tokens"],
            },
            trace_id=trace_id,
        )
        self._events.emit(run, EVENT_LLM_COMPLETED, payload, trace_id=trace_id)
        db.session.commit()
        return payload

    # ------------------------------------------------------------------ degrade

    def _degrade(
        self,
        run: AgentRun,
        agent_warning_code: str,
        evidence: dict | None,
        trace_id: str,
        *,
        warning_code: str | None = None,
        usage: dict | None = None,
        provider: object | None = None,
    ) -> dict:
        """显式降级：确定性摘要 + llm.failed + warning.raised，不伪装成功。"""
        analysis = _deterministic_summary(agent_warning_code, evidence)
        summary = analysis[:MAX_ANALYSIS_CHARS]
        self._events.emit(
            run,
            EVENT_LLM_FAILED,
            {
                "warning_code": warning_code or agent_warning_code,
                "agent_warning_code": agent_warning_code,
            },
            trace_id=trace_id,
        )
        self._events.emit(
            run,
            EVENT_WARNING_RAISED,
            {"warning_codes": [agent_warning_code]},
            trace_id=trace_id,
        )
        if usage:
            normalized = normalize_usage(usage) or {}
            invocation = record_invocation(
                run,
                provider=provider or _UnavailableProvider(),
                operation=INVOCATION_OPERATION,
                status="failed",
                warning_code=warning_code or agent_warning_code,
                input_tokens=int(normalized.get("prompt_tokens") or 0),
                output_tokens=int(normalized.get("completion_tokens") or 0),
                cached_input_tokens=int(normalized.get("cached_tokens") or 0),
                reasoning_tokens=_nested_usage_int(
                    usage, "reasoning_tokens", "completion_tokens_details.reasoning_tokens"
                ),
                total_tokens=int(normalized.get("total_tokens") or 0),
                usage_source=USAGE_SOURCE_PROVIDER_REPORTED,
                input_digest=prompt_digest(self._last_prompt) if self._last_prompt else None,
                prompt_template_version="analysis-v1",
            )
            self._agent_log.llm_event(
                "llm.failed",
                run,
                operation=INVOCATION_OPERATION,
                provider=getattr(provider or _UnavailableProvider(), "provider_name", "unavailable"),
                model=getattr(provider or _UnavailableProvider(), "model", None),
                status="failed",
                warning_code=warning_code or agent_warning_code,
                input_tokens=invocation.input_tokens,
                output_tokens=invocation.output_tokens,
                total_tokens=invocation.total_tokens,
                usage_source=invocation.usage_source,
                cost=float(invocation.total_cost or 0),
                latency_ms=invocation.latency_ms,
                trace_id=trace_id,
            )
        else:
            normalized = {}
            self._agent_log.llm_event(
                "llm.failed",
                run,
                operation=INVOCATION_OPERATION,
                provider=getattr(provider or _UnavailableProvider(), "provider_name", "unavailable"),
                status="failed",
                warning_code=warning_code or agent_warning_code,
                trace_id=trace_id,
            )
        db.session.add(
            AgentMessage(
                run_id=run.id,
                role="agent",
                content=summary,
                message_type=ANALYSIS_MESSAGE_TYPE,
            )
        )
        payload = {
            "analysis": summary,
            "provider": None,
            "model": None,
            "degraded": True,
            "warning_code": agent_warning_code,
            "usage": _usage_payload(normalized, usage or {}),
        }
        self._events.emit(run, EVENT_LLM_COMPLETED, payload, trace_id=trace_id)
        db.session.commit()
        return payload

    # ------------------------------------------------------------------ helpers

    def _build_request(self, goal: str, evidence: dict, provider: object) -> LLMRequest:
        evidence_text = json.dumps(evidence, ensure_ascii=False)[:MAX_EVIDENCE_CHARS]
        return LLMRequest(
            prompt=f"本轮目标：{goal}\n\n确定性工具证据：\n{evidence_text}",
            system_prompt=(
                "你是 CyberGuard 安全分析助手。请基于给定的确定性扫描证据，"
                "用简体中文回答本轮目标。输出结构：1）结论；2）关键风险（引用具体证据）；"
                "3）修复建议。只能依据证据作答，禁止编造证据之外的发现。"
            ),
            temperature=0.3,
            max_tokens=resolve_provider_max_tokens(provider, 1200),
        )

    def _turn_input(self, run: AgentRun) -> str | None:
        """读取当前 Turn 的用户输入（多轮语义：引用本轮输入而非历史轮次）。"""
        turn = (
            AgentTurn.query.filter_by(run_id=run.id).order_by(AgentTurn.id.desc()).first()
        )
        if turn is None or turn.input_message_id is None:
            return None
        message = db.session.get(AgentConversationMessage, turn.input_message_id)
        if message is None:
            return None
        return (message.content_redacted or "")[:2000]

    def _collect_evidence(self, run_id: int) -> dict:
        rows = (
            AgentArtifact.query.filter_by(run_id=run_id)
            .order_by(AgentArtifact.id.asc())
            .all()
        )
        evidence: dict[str, Any] = {}
        for artifact in rows:
            metrics = (artifact.content_json or {}).get("metrics") or {}
            if not metrics:
                continue
            evidence[artifact.artifact_type] = _bounded_metrics(metrics)
        return evidence

    def _has_analysis(self, run_id: int) -> bool:
        return (
            AgentMessage.query.filter_by(run_id=run_id, message_type=ANALYSIS_MESSAGE_TYPE)
            .first()
            is not None
        )

    def _run_stopped(self, run_id: int) -> bool:
        current = db.session.get(AgentRun, run_id)
        if current is None:
            return True
        status = current.status.value if hasattr(current.status, "value") else str(current.status)
        return status in {AgentRunStatus.PAUSED.value, AgentRunStatus.CANCELED.value}


# ------------------------------------------------------------------ module helpers


class _UnavailableProvider:
    """占位 Provider：仅在无 Provider 但又有 usage 需要记账时使用。"""

    provider_name = "unavailable"
    model = None
    model_version = None
    provider_config_id = None


def _deterministic_summary(warning_code: str, evidence: dict | None) -> str:
    """Provider 不可用时的确定性摘要文本（显式说明不是模型分析）。"""
    lines = [
        "【LLM 分析暂不可用】",
        f"原因：{_WARNING_LABELS.get(warning_code, warning_code)}。"
        "以下为确定性工具证据摘要，非模型分析结论。",
    ]
    if evidence:
        lines.append("")
        lines.append("确定性证据摘要：")
        for key in ("finding_set", "coverage_report", "risk_ranking", "agent_report"):
            if evidence.get(key):
                lines.append(f"- {key}：{_compact_metrics(evidence[key])}")
    return "\n".join(lines)


def _compact_metrics(metrics: dict) -> str:
    """把单类证据 metrics 压成一行可读摘要。"""
    parts: list[str] = []
    for key in (
        "findings_count",
        "severity_counts",
        "ranked_count",
        "critical",
        "high",
        "total_files",
        "scanned_with_findings",
        "specialized_sast",
        "file_count",
        "languages",
    ):
        value = metrics.get(key)
        if value is None or value == "" or value == []:
            continue
        if isinstance(value, dict):
            parts.append(f"{key}={value}")
        elif isinstance(value, list):
            parts.append(f"{key}={','.join(str(item) for item in value[:5])}")
        else:
            parts.append(f"{key}={value}")
    return "；".join(parts) if parts else "无关键指标"


def _bounded_metrics(metrics: dict) -> dict:
    """裁剪 metrics：长列表只保留 Top N，长字符串截断，限制证据体积。"""
    result: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, dict):
            result[key] = _bounded_metrics(value)
        elif isinstance(value, list):
            cap = 5 if key in _LIST_TRIM_KEYS else 10
            result[key] = _bounded_items(value[:cap])
        elif isinstance(value, str) and len(value) > 200:
            result[key] = value[:200]
        else:
            result[key] = value
    return result


def _bounded_items(items: list) -> list:
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(_bounded_metrics(item))
        elif isinstance(item, str) and len(item) > 200:
            result.append(item[:200])
        else:
            result.append(item)
    return result


def _usage_payload(normalized: dict, raw_usage: dict) -> dict:
    input_tokens = int(normalized.get("prompt_tokens") or 0)
    output_tokens = int(normalized.get("completion_tokens") or 0)
    total_tokens = int(normalized.get("total_tokens") or 0) or input_tokens + output_tokens
    reasoning_tokens = _nested_usage_int(
        raw_usage, "reasoning_tokens", "completion_tokens_details.reasoning_tokens"
    )
    return {
        "tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": int(normalized.get("cached_tokens") or 0),
        "reasoning_tokens": reasoning_tokens,
    }


def _nested_usage_int(usage: dict, *keys: str) -> int:
    for key in keys:
        current: Any = usage
        for part in key.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        if isinstance(current, int) and not isinstance(current, bool) and current >= 0:
            return current
    return 0
