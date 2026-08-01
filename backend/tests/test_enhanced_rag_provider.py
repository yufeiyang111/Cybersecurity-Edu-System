from __future__ import annotations

from app.services.enhanced_rag_engine import EnhancedRAGEngine
from app.services.llm import LLMResponse


class _FakeRagProvider:
    provider_name = "test-rag-provider"
    model = "test-rag-model"
    model_version = "test-rag-version"
    accepts_llm_request = True

    def __init__(self):
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return LLMResponse(
            text="????",
            provider_name=self.provider_name,
            model=self.model,
            model_version=self.model_version,
            status_code=200,
            latency_ms=25,
            usage={"total_tokens": 11},
        )


def _engine_with_provider(provider):
    engine = EnhancedRAGEngine.__new__(EnhancedRAGEngine)
    engine._get_llm_provider = lambda: provider
    engine.build_prompt = lambda query, context, history: [
        {"role": "system", "content": "system"},
        {"role": "user", "content": query},
    ]
    engine._calculate_confidence = lambda _docs: 0.8
    return engine


def test_enhanced_rag_uses_shared_provider_contract_and_exposes_metadata():
    provider = _FakeRagProvider()
    engine = _engine_with_provider(provider)

    result = engine.generate("??? SQL ???", "?????", retrieved_docs=[])

    assert result["answer"] == "????"
    assert result["provider"] == "test-rag-provider"
    assert result["model_name"] == "test-rag-model"
    assert result["model_version"] == "test-rag-version"
    assert result["response_time"] == 0.025
    assert result["usage"] == {"total_tokens": 11}
    assert len(provider.requests) == 1
    assert provider.requests[0].system_prompt == "system"
    assert "SQL" in provider.requests[0].prompt


def test_enhanced_rag_keeps_safe_unavailable_result_without_provider():
    engine = EnhancedRAGEngine.__new__(EnhancedRAGEngine)
    engine._get_llm_provider = lambda: None

    result = engine.generate("security", "context")

    assert result["provider"] is None
    assert result["warning_code"] == "LLM_PROVIDER_UNAVAILABLE"
    assert result["error"] == "API\u672a\u914d\u7f6e"
    assert "traceback" not in result["answer"].lower()
