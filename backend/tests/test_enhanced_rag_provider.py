from __future__ import annotations

from app.services.enhanced_rag_engine import EnhancedRAGEngine
from app.services.llm import LLMResponse, LLMStreamChunk


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


class _StreamingFakeRagProvider(_FakeRagProvider):
    def generate_stream(self, request):
        yield LLMStreamChunk(reasoning_delta="\u5206\u6790")
        yield LLMStreamChunk(delta="\u7f51")
        yield LLMStreamChunk(delta="\u5b89")
        yield LLMStreamChunk(reasoning_delta="\u5b8c\u6210")
        yield LLMStreamChunk(finished=True)


def test_enhanced_rag_streams_deltas_reasoning_and_final_metadata():
    provider = _StreamingFakeRagProvider()
    engine = _engine_with_provider(provider)

    events = list(engine.generate_stream("SQL", "context", retrieved_docs=[]))

    delta_events = [e for e in events if e["type"] == "delta"]
    reasoning_events = [e for e in events if e["type"] == "reasoning"]
    done_events = [e for e in events if e["type"] == "done"]

    assert "".join(e["content"] for e in delta_events) == "\u7f51\u5b89"
    assert "".join(e["delta"] for e in reasoning_events) == "\u5206\u6790\u5b8c\u6210"
    assert len(done_events) == 1
    done = done_events[0]
    assert done["answer"] == "\u7f51\u5b89"
    assert done["reasoning"] == "\u5206\u6790\u5b8c\u6210"
    assert done["provider"] == "test-rag-provider"
    assert done["model_name"] == "test-rag-model"
    assert done["model_version"] == "test-rag-version"
    assert done["confidence"] == 0.8
    assert done["response_time"] >= 0


def test_enhanced_rag_stream_degrades_to_one_shot_without_stream_support():
    provider = _FakeRagProvider()
    engine = _engine_with_provider(provider)

    events = list(engine.generate_stream("SQL", "context", retrieved_docs=[]))

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["answer"] == "????"
    assert done_events[0]["provider"] == "test-rag-provider"


def test_enhanced_rag_stream_emits_unavailable_done_event_without_provider():
    engine = EnhancedRAGEngine.__new__(EnhancedRAGEngine)
    engine._get_llm_provider = lambda: None

    events = list(engine.generate_stream("security", "context"))

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["warning_code"] == "LLM_PROVIDER_UNAVAILABLE"


def test_enhanced_rag_stream_empty_output_maps_to_failure_result():
    class _EmptyStreamProvider(_FakeRagProvider):
        def generate_stream(self, request):
            yield LLMStreamChunk(finished=True)

    provider = _EmptyStreamProvider()
    engine = _engine_with_provider(provider)

    events = list(engine.generate_stream("SQL", "context", retrieved_docs=[]))

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["warning_code"] == "LLM_OUTPUT_INVALID"


def test_enhanced_rag_ask_stream_includes_retrieved_docs_payload():
    provider = _StreamingFakeRagProvider()
    engine = _engine_with_provider(provider)
    engine._retrieve_and_build = lambda query, use_rerank=True: (
        [{"id": "d1", "metadata": {"title": "t1", "source": "s1"}, "similarity": 0.9, "source": "vector"}],
        "context",
    )

    events = list(engine.ask_stream("SQL"))
    done_events = [e for e in events if e["type"] == "done"]

    assert len(done_events) == 1
    payload = done_events[0]["retrieved_docs"]
    assert payload[0]["id"] == "d1"
    assert payload[0]["title"] == "t1"
    assert payload[0]["source_type"] == "vector"
