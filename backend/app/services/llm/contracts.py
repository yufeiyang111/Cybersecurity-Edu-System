"""LLM Provider 的统一请求与响应契约。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMRequest:
    """发送给 Provider 的受限文本生成请求。"""

    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Provider 返回的标准化文本生成结果。"""

    text: str | None
    provider_name: str
    model: str | None
    model_version: str | None = None
    status_code: int | None = None
    warning_code: str | None = None
    latency_ms: int | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None

    @property
    def is_success(self) -> bool:
        """仅当存在文本且没有警告码时表示成功。"""
        return bool(self.text and not self.warning_code)


class LLMProvider(Protocol):
    """远程或规则 Provider 需要实现的最小接口。"""

    provider_name: str
    model: str | None
    model_version: str | None

    def generate(self, request: LLMRequest) -> LLMResponse:
        """生成标准化响应。"""


class ProviderUnavailableError(RuntimeError):
    """Provider 不可用时使用的安全异常。"""
