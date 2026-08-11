# -*- coding: utf-8 -*-
"""
共享 LLM Provider 客户端（知识图谱领域）

统一 Multi-Provider 调用：MiniMax 主 + 备用（deepseek-v4-flash），
额度耗尽自动切换；token 用量统计。社区摘要、GraphRAG 全局/局部检索、
实体描述回填等模块共用，避免各自复制 HTTP 调用代码。

QuotaExhaustedError 语义与 kg/llm_extractor.py 一致：全部 Provider
额度耗尽时抛出，由任务层决定暂停/降级。

审计：带 user_id 的调用（图谱问答流式/非流式）写入 llm_call_logs，
与用户自定义 LLM Provider 的用量审计共用同一张表。
"""
import json
import logging
import threading
import time
from typing import Any, Dict, Generator, List, Optional

import requests

from app.config import Config
from app.services.kg.llm_extractor import QuotaExhaustedError, _is_quota_error

logger = logging.getLogger(__name__)


def write_call_log(
    *,
    user_id: Optional[int],
    provider_name: str,
    model: Optional[str],
    operation: str,
    status: str,
    streaming: bool = False,
    input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    latency_ms: Optional[int] = None,
    warning_code: Optional[str] = None,
) -> None:
    """写入 LLM 调用审计日志（llm_call_logs）；无 user_id 时跳过。"""
    if not user_id:
        return
    try:
        from app import db
        from app.models.llm import LLMCallLog

        log = LLMCallLog(
            user_id=user_id,
            provider_name=str(provider_name)[:128],
            model=model,
            operation=str(operation)[:64],
            status=str(status)[:32],
            streaming=bool(streaming),
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            reasoning_tokens=int(reasoning_tokens or 0),
            total_tokens=int(input_tokens or 0) + int(output_tokens or 0),
            latency_ms=int(latency_ms) if latency_ms is not None else None,
            warning_code=warning_code,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        # 审计失败不应阻断问答主链路
        logger.warning("LLM 调用审计写入失败: %s", type(exc).__name__)


class LLMProviderClient:
    """多 Provider 文本生成客户端（主→备用自动切换，额度耗尽切换）。"""

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        timeout_seconds: int = 180,
        max_retries: int = 2,
    ) -> None:
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        self.providers: List[Dict[str, str]] = []
        if Config.MINIMAX_API_KEY:
            self.providers.append({
                "name": "minimax",
                "api_key": Config.MINIMAX_API_KEY,
                "api_base": Config.MINIMAX_API_BASE,
                "model": Config.MINIMAX_MODEL,
                "endpoint": "chatcompletion_v2",
            })
        if Config.KG_FALLBACK_API_KEY:
            self.providers.append({
                "name": "fallback",
                "api_key": Config.KG_FALLBACK_API_KEY,
                "api_base": Config.KG_FALLBACK_API_BASE,
                "model": Config.KG_FALLBACK_MODEL,
                "endpoint": "chat/completions",
            })

        # token 用量统计（跨线程累计，按 provider 拆分）
        self.usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        self.usage_by_provider: Dict[str, Dict[str, int]] = {}
        self._usage_lock = threading.Lock()
        self._session = requests.Session()
        # 直连，绕过本机系统代理（Windows 系统代理会拦截 https 导致 ProxyError）
        self._session.trust_env = False

    # ------------------------------------------------------------------
    def call(
        self,
        user_content: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        user_id: Optional[int] = None,
        operation: str = "kg_llm",
    ) -> Optional[str]:
        """按 Provider 优先级生成文本；全部额度耗尽抛 QuotaExhaustedError。

        Args:
            user_id: 传入时本次调用写入 llm_call_logs 审计（用量/耗时/模型）
            operation: 审计操作标识（如 graph_global_search）

        Returns:
            原始文本；所有 Provider 都失败（非额度问题）返回 None
        """
        result = self.call_with_thinking(
            user_content,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
            operation=operation,
        )
        return result["text"] if result is not None else None

    def call_with_thinking(
        self,
        user_content: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        user_id: Optional[int] = None,
        operation: str = "kg_llm",
    ) -> Optional[Dict[str, Any]]:
        """按 Provider 优先级生成文本，附带模型思考过程（若返回）。

        Returns:
            {"text", "thinking", "usage", "provider", "model"}；所有 Provider 都
            失败（非额度问题）返回 None。thinking 为模型 reasoning 字段，不支持
            思考的模型为 None；usage 为本次调用的 token 用量。
        """
        prompt = system_prompt if system_prompt is not None else self.system_prompt
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        last_quota_error: Optional[QuotaExhaustedError] = None
        for provider in self.providers:
            started = time.monotonic()
            try:
                result = self._call_provider(provider, prompt, user_content, temp, tokens)
                latency_ms = int((time.monotonic() - started) * 1000)
                if result is not None:
                    result["provider"] = provider["name"]
                    result["model"] = provider["model"]
                    usage = result.get("usage") or {}
                    write_call_log(
                        user_id=user_id,
                        provider_name=provider["name"],
                        model=provider["model"],
                        operation=operation,
                        status="success",
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        reasoning_tokens=usage.get("reasoning_tokens", 0),
                        latency_ms=latency_ms,
                    )
                return result
            except QuotaExhaustedError as exc:
                last_quota_error = exc
                write_call_log(
                    user_id=user_id,
                    provider_name=provider["name"],
                    model=provider["model"],
                    operation=operation,
                    status="error",
                    warning_code="quota_exhausted",
                )
                logger.warning("Provider %s 额度耗尽，切换到备用", provider["name"])
        if last_quota_error is not None:
            raise last_quota_error
        return None

    # ------------------------------------------------------------------
    def _call_provider(
        self, provider: Dict[str, str], system_prompt: str, user_content: str,
        temperature: float, max_tokens: int,
    ) -> Optional[Dict[str, Any]]:
        """调用单个 Provider，返回 {"text", "thinking"}；失败返回 None。"""
        if provider["endpoint"] == "chatcompletion_v2":
            url = f"{provider['api_base']}/text/chatcompletion_v2"
        else:
            url = f"{provider['api_base']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})
        payload = {
            "model": provider["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.post(
                    url, headers=headers, json=payload, timeout=self.timeout_seconds
                )
                if resp.status_code != 200:
                    if _is_quota_error(resp):
                        raise QuotaExhaustedError(
                            f"LLM 额度耗尽（HTTP {resp.status_code}，provider={provider['name']}）"
                        )
                    logger.warning(
                        "LLM 请求失败 provider=%s status=%d attempt=%d",
                        provider["name"], resp.status_code, attempt,
                    )
                    last_error = RuntimeError(f"status={resp.status_code}")
                    continue
                data = resp.json()
                # 记录 token 用量（跨线程安全）
                usage = data.get("usage") or {}
                input_tokens = int(usage.get("prompt_tokens") or 0)
                completion_tokens = int(usage.get("completion_tokens") or 0)
                reasoning_tokens = int(usage.get("reasoning_tokens") or 0)
                with self._usage_lock:
                    self.usage["prompt_tokens"] += input_tokens
                    self.usage["completion_tokens"] += completion_tokens
                    provider_usage = self.usage_by_provider.setdefault(
                        provider["name"], {"prompt_tokens": 0, "completion_tokens": 0}
                    )
                    provider_usage["prompt_tokens"] += input_tokens
                    provider_usage["completion_tokens"] += completion_tokens
                # 提取文本与思考过程（reasoning_content/reasoning 字段，兼容两类 API）
                message: Dict[str, Any] = {}
                choices = data.get("choices") or []
                if choices:
                    message = choices[0].get("message", {}) or {}
                output = data.get("output")
                if isinstance(output, dict):
                    text = output.get("text", "")
                    thinking = output.get("reasoning_content") or output.get("reasoning")
                elif isinstance(output, str):
                    text = output
                    thinking = None
                else:
                    text = message.get("content", "") or ""
                    thinking = (
                        message.get("reasoning_content")
                        or message.get("reasoning")
                        or None
                    )
                return {
                    "text": text,
                    "thinking": thinking if isinstance(thinking, str) and thinking.strip() else None,
                    "usage": {
                        "prompt_tokens": input_tokens,
                        "completion_tokens": completion_tokens,
                        "reasoning_tokens": reasoning_tokens,
                    },
                }
            except QuotaExhaustedError:
                raise
            except (requests.RequestException, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "LLM 请求异常 provider=%s type=%s attempt=%d",
                    provider["name"], type(exc).__name__, attempt,
                )
        if last_error is not None:
            logger.warning("LLM 最终失败: %s", type(last_error).__name__)
        return None

    # ------------------------------------------------------------------
    # 流式调用（SSE 生成器）
    # ------------------------------------------------------------------
    def call_stream(
        self,
        user_content: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        user_id: Optional[int] = None,
        operation: str = "kg_llm_stream",
    ) -> Generator[Dict[str, Any], None, None]:
        """按 Provider 优先级流式生成文本（打字机输出）。

        每个事件为 dict：
          {"type": "reasoning", "text": str}   思考过程增量
          {"type": "delta", "text": str}       答案增量
          {"type": "done", "text", "thinking", "usage", "provider", "model"}
          {"type": "error", "error": str, "warning_code": str|None}

        全部 Provider 额度耗尽时以 error 事件结束（QuotaExhaustedError 语义）。
        """
        prompt = system_prompt if system_prompt is not None else self.system_prompt
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        last_quota_error: Optional[QuotaExhaustedError] = None
        for provider in self.providers:
            started = time.monotonic()
            emitted_error = False
            try:
                for event in self._call_provider_stream(
                    provider, prompt, user_content, temp, tokens
                ):
                    if event["type"] == "done":
                        usage = event.get("usage") or {}
                        latency_ms = int((time.monotonic() - started) * 1000)
                        write_call_log(
                            user_id=user_id,
                            provider_name=provider["name"],
                            model=provider["model"],
                            operation=operation,
                            status="success",
                            streaming=True,
                            input_tokens=usage.get("prompt_tokens", 0),
                            output_tokens=usage.get("completion_tokens", 0),
                            reasoning_tokens=usage.get("reasoning_tokens", 0),
                            latency_ms=latency_ms,
                        )
                    yield event
                # 生成器正常结束：返回的是 dict（finish 事件）
                return
            except QuotaExhaustedError as exc:
                last_quota_error = exc
                emitted_error = True
                write_call_log(
                    user_id=user_id,
                    provider_name=provider["name"],
                    model=provider["model"],
                    operation=operation,
                    status="error",
                    streaming=True,
                    warning_code="quota_exhausted",
                )
                logger.warning("Provider %s 额度耗尽（流式），切换到备用", provider["name"])
            except Exception as exc:  # noqa: BLE001
                emitted_error = True
                latency_ms = int((time.monotonic() - started) * 1000)
                write_call_log(
                    user_id=user_id,
                    provider_name=provider["name"],
                    model=provider["model"],
                    operation=operation,
                    status="error",
                    streaming=True,
                    warning_code="stream_failed",
                    latency_ms=latency_ms,
                )
                logger.warning(
                    "流式 LLM 请求异常 provider=%s type=%s",
                    provider["name"], type(exc).__name__,
                )
            if not emitted_error:
                write_call_log(
                    user_id=user_id,
                    provider_name=provider["name"],
                    model=provider["model"],
                    operation=operation,
                    status="error",
                    streaming=True,
                    warning_code="empty_stream",
                )
        yield {
            "type": "error",
            "error": (
                "LLM 额度耗尽，请稍后重试" if last_quota_error is not None
                else "LLM 生成失败，请稍后重试"
            ),
            "warning_code": "quota_exhausted" if last_quota_error is not None else "llm_failed",
        }

    def _call_provider_stream(
        self, provider: Dict[str, str], system_prompt: str, user_content: str,
        temperature: float, max_tokens: int,
    ) -> Generator[Dict[str, Any], None, None]:
        """流式调用单个 Provider，逐 delta yield 事件；结束后 yield finish dict。

        兼容两类 API 的流式响应：
        - MiniMax chatcompletion_v2：SSE data 行，choices[0].delta
          {content, reasoning_content}，usage 在末条 delta 携带
        - OpenAI 兼容（deepseek/硅基流动）：SSE data 行，choices[0].delta
          {content, reasoning_content}，末条带 usage，结束为 data: [DONE]
        """
        if provider["endpoint"] == "chatcompletion_v2":
            url = f"{provider['api_base']}/text/chatcompletion_v2"
        else:
            url = f"{provider['api_base']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})
        payload = {
            "model": provider["model"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        text_parts: List[str] = []
        thinking_parts: List[str] = []
        usage: Dict[str, int] = {}
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                with self._session.post(
                    url, headers=headers, json=payload,
                    stream=True, timeout=self.timeout_seconds,
                ) as resp:
                    if resp.status_code != 200:
                        if _is_quota_error(resp):
                            raise QuotaExhaustedError(
                                f"LLM 额度耗尽（HTTP {resp.status_code}，provider={provider['name']}）"
                            )
                        logger.warning(
                            "流式 LLM 请求失败 provider=%s status=%d attempt=%d",
                            provider["name"], resp.status_code, attempt,
                        )
                        last_error = RuntimeError(f"status={resp.status_code}")
                        continue
                    for raw_line in resp.iter_lines(decode_unicode=True):
                        line = (raw_line or "").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        delta: Dict[str, Any] = {}
                        choices = data.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta", {}) or {}
                        output = data.get("output")
                        if isinstance(output, dict):
                            text_piece = output.get("text") or ""
                            thinking_piece = (
                                output.get("reasoning_content") or output.get("reasoning") or ""
                            )
                        else:
                            text_piece = delta.get("content") or ""
                            thinking_piece = (
                                delta.get("reasoning_content") or delta.get("reasoning") or ""
                            )
                        if thinking_piece:
                            thinking_parts.append(thinking_piece)
                            yield {"type": "reasoning", "text": thinking_piece}
                        if text_piece:
                            text_parts.append(text_piece)
                            yield {"type": "delta", "text": text_piece}
                        # 用量：部分 API 在末条 delta 携带
                        if data.get("usage"):
                            usage = {
                                "prompt_tokens": int(data["usage"].get("prompt_tokens") or 0),
                                "completion_tokens": int(data["usage"].get("completion_tokens") or 0),
                                "reasoning_tokens": int(data["usage"].get("reasoning_tokens") or 0),
                            }
                    # 累计用量（跨线程安全）
                    with self._usage_lock:
                        self.usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                        self.usage["completion_tokens"] += usage.get("completion_tokens", 0)
                        provider_usage = self.usage_by_provider.setdefault(
                            provider["name"], {"prompt_tokens": 0, "completion_tokens": 0}
                        )
                        provider_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                        provider_usage["completion_tokens"] += usage.get("completion_tokens", 0)
                    thinking = "".join(thinking_parts).strip() or None
                    yield {
                        "type": "done",
                        "text": "".join(text_parts),
                        "thinking": thinking,
                        "usage": usage,
                        "provider": provider["name"],
                        "model": provider["model"],
                    }
                    return
            except QuotaExhaustedError:
                raise
            except (requests.RequestException, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "流式 LLM 请求异常 provider=%s type=%s attempt=%d",
                    provider["name"], type(exc).__name__, attempt,
                )
        if last_error is not None:
            logger.warning("流式 LLM 最终失败: %s", type(last_error).__name__)
        raise RuntimeError("stream failed")


_client: Optional[LLMProviderClient] = None
_client_lock = threading.Lock()


def get_llm_provider_client() -> LLMProviderClient:
    """获取共享客户端单例（配置来自 Config）。"""
    global _client
    with _client_lock:
        if _client is None:
            _client = LLMProviderClient()
        return _client


__all__ = ["LLMProviderClient", "get_llm_provider_client"]
