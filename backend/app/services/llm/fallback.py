"""LLM 未启用时的规则化 Provider。"""
from __future__ import annotations

from collections.abc import Callable

from .contracts import LLMRequest, LLMResponse


class RuleBasedProvider:
    """将规则化生成器适配到统一 Provider 契约。"""

    provider_name = "rule-based"
    model = None
    model_version = "rules-v1"
    accepts_llm_request = True

    def __init__(
        self,
        generator: Callable[[LLMRequest], str],
        *,
        warning_code: str = "LLM_DISABLED",
    ) -> None:
        self._generator = generator
        self._warning_code = warning_code

    def generate(self, request: LLMRequest) -> LLMResponse:
        try:
            text = self._generator(request)
        except Exception:
            return LLMResponse(
                text=None,
                provider_name=self.provider_name,
                model=self.model,
                model_version=self.model_version,
                warning_code="LLM_FALLBACK_FAILED",
            )
        return LLMResponse(
            text=text,
            provider_name=self.provider_name,
            model=self.model,
            model_version=self.model_version,
            warning_code=self._warning_code,
        )
