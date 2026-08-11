# -*- coding: utf-8 -*-
"""
共享 LLM Provider 客户端（知识图谱领域）

统一 Multi-Provider 调用：MiniMax 主 + 备用（deepseek-v4-flash），
额度耗尽自动切换；token 用量统计。社区摘要、GraphRAG 全局/局部检索、
实体描述回填等模块共用，避免各自复制 HTTP 调用代码。

QuotaExhaustedError 语义与 kg/llm_extractor.py 一致：全部 Provider
额度耗尽时抛出，由任务层决定暂停/降级。
"""
import json
import logging
import threading
from typing import Any, Dict, List, Optional

import requests

from app.config import Config
from app.services.kg.llm_extractor import QuotaExhaustedError, _is_quota_error

logger = logging.getLogger(__name__)


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
    ) -> Optional[str]:
        """按 Provider 优先级生成文本；全部额度耗尽抛 QuotaExhaustedError。

        Returns:
            原始文本；所有 Provider 都失败（非额度问题）返回 None
        """
        prompt = system_prompt if system_prompt is not None else self.system_prompt
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        last_quota_error: Optional[QuotaExhaustedError] = None
        for provider in self.providers:
            try:
                return self._call_provider(provider, prompt, user_content, temp, tokens)
            except QuotaExhaustedError as exc:
                last_quota_error = exc
                logger.warning("Provider %s 额度耗尽，切换到备用", provider["name"])
        if last_quota_error is not None:
            raise last_quota_error
        return None

    # ------------------------------------------------------------------
    def _call_provider(
        self, provider: Dict[str, str], system_prompt: str, user_content: str,
        temperature: float, max_tokens: int,
    ) -> Optional[str]:
        """调用单个 Provider，返回原始文本；失败返回 None。"""
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
                with self._usage_lock:
                    self.usage["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                    self.usage["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                    provider_usage = self.usage_by_provider.setdefault(
                        provider["name"], {"prompt_tokens": 0, "completion_tokens": 0}
                    )
                    provider_usage["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                    provider_usage["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                choices = data.get("choices") or []
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                output = data.get("output")
                if isinstance(output, dict):
                    return output.get("text", "")
                if isinstance(output, str):
                    return output
                return None
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
