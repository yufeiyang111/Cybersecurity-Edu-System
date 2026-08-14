# -*- coding: utf-8 -*-
"""
RAG核心引擎 - 增强版
检索增强生成：集成重排序、多路召回、优化的Prompt工程

支持 MiniMax 和 DashScope 通义千问两种 LLM 后端
"""
import time
import json
import uuid
from time import perf_counter
from typing import List, Dict, Any, Optional, Tuple
from app.config import Config
from app.services.vector_store import get_vector_store
from app.services.graph_store import get_knowledge_graph
from app.services.secbert_embedding import get_embedding_service
from app.services.llm import LLMRequest, LLMResponse
from app.services.llm.prompt_cache_key_factory import for_stable_prefix
from app.services.rag_guard import detect_prompt_injection, wrap_untrusted_section
from app.services.llm.provider_selector import resolve_provider_max_tokens, select_provider
from app.services.text_chunker import chunk_text
from app.services.rag_prompt_builder import (
    DEFAULT_QA_MAX_TOKENS,
    SYSTEM_PROMPT as XML_SYSTEM_PROMPT,
    build_qa_messages,
    resolve_qa_max_tokens,
)


class Reranker:
    """文档重排序器 - 真实 cross-encoder 优先，失败降级为 embedding 伪重排"""

    def __init__(self):
        self.embedding_service = get_embedding_service()
        self._real_reranker = None

    def _get_real_reranker(self):
        """懒加载真实 rerank 服务（加载失败返回 None，走降级）。"""
        if self._real_reranker is None:
            try:
                from app.services.llm.reranker_service import get_reranker_service

                service = get_reranker_service()
                if service._load():
                    self._real_reranker = service
            except Exception:
                self._real_reranker = False
        return self._real_reranker or None

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = None
    ) -> List[Dict]:
        """
        对检索结果进行重排序

        Args:
            query: 用户查询
            documents: 检索到的文档列表
            top_k: 返回数量

        Returns:
            重排序后的文档列表
        """
        top_k = top_k or Config.RERANK_TOP_K

        if not documents:
            return []

        # 真实 cross-encoder 重排（batch 打分）
        real = self._get_real_reranker()
        if real is not None:
            reranked = real.rerank(query, documents, top_k)
            if reranked:
                return reranked

        # embedding 降级时不做伪重排（伪向量打分是噪声），保持检索顺序
        if getattr(self.embedding_service, "is_degraded", False):
            return documents[:top_k]

        # 降级：embedding 余弦伪重排（batch 一次前向，避免逐文档两次 encode 的分钟级延迟）
        texts = [doc.get("text", "") for doc in documents if doc.get("text")]
        try:
            cross_scores = self.embedding_service.compute_similarity(query, texts)
        except Exception:
            cross_scores = [doc.get("score", doc.get("similarity", 0.5)) for doc in documents]

        scored_docs = []
        for doc, similarity in zip([d for d in documents if d.get("text")], cross_scores):
            original_score = doc.get("score", doc.get("similarity", 0.5))
            combined_score = 0.4 * original_score + 0.6 * similarity

            scored_docs.append({
                **doc,
                "rerank_score": combined_score,
                "original_score": original_score,
                "cross_score": similarity
            })

        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

        return scored_docs[:top_k]


class EnhancedRAGEngine:
    """增强版检索增强生成引擎"""

    # 系统提示词（XML 标签化稳定前缀，见 rag_prompt_builder.SYSTEM_PROMPT）
    SYSTEM_PROMPT = XML_SYSTEM_PROMPT

    # 安全专家角色提示
    SECURITY_EXPERT_PROMPT = """你是一位资深的网络安全专家，具有丰富的教学经验和实战经历。
你擅长将复杂的安全概念用通俗易懂的方式解释清楚。
你会结合实际案例来说明抽象的概念。
你会特别注意提醒用户潜在的安全风险和防护措施。
你的目标是帮助用户真正理解网络安全的原理，而不是简单地给出答案。"""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.knowledge_graph = get_knowledge_graph()
        self.embedding_service = get_embedding_service()
        self.reranker = Reranker()
        self.last_injected_docs: List[tuple[str, tuple[str, ...]]] = []

        # Provider is selected lazily so the RAG engine does not import a concrete SDK.
        self.llm_provider = None
        self.api_key = None
        self.model_name = None

    def retrieve(self, query: str, top_k: int = None) -> List[Dict]:
        """混合检索：向量检索 + 知识图谱检索 + RRF融合（向量结果按 doc_id 去重）"""
        top_k = top_k or Config.VECTOR_TOP_K
        all_results = {}

        # 1. 混合检索（向量 + Qdrant 原生 BM25，RRF 融合；分块后按 doc_id 去重）
        #    embedding 降级时跳过向量路（伪向量与库中真实向量空间错配，只走词法）
        try:
            backend = self.vector_store.backend
            embedding_service = self.vector_store.embedding_service
            degraded = bool(getattr(embedding_service, "is_degraded", False))
            query_vector = None
            if not degraded:
                query_vector = embedding_service.encode_query(query)[0]
                if hasattr(query_vector, "tolist"):
                    query_vector = query_vector.tolist()
            if hasattr(backend, "hybrid_search"):
                vector_results = backend.hybrid_search(
                    vector=query_vector,
                    text=query,
                    where=None,
                    top_k=top_k * 2,
                )
            else:
                if query_vector is None:
                    vector_results = []
                else:
                    vector_results = backend.search(
                        vector=query_vector,
                        where=None,
                        top_k=top_k * 2,
                    )
            for rank, item in enumerate(vector_results):
                metadata = dict(item.metadata)
                doc_id = str(metadata.get("doc_id") or item.id)
                weight = Config.VECTOR_WEIGHT * (1 / (60 + rank + 1))
                existing = all_results.get(doc_id)
                # BM25-only 降级路 similarity 为 None；None 视为最低相似度，
                # 避免 None 参与比较抛 TypeError
                item_similarity = item.similarity if item.similarity is not None else -1.0
                existing_similarity = (
                    existing.get("similarity")
                    if existing and existing.get("similarity") is not None
                    else -1.0
                )
                if existing is None or item_similarity > existing_similarity:
                    all_results[doc_id] = {
                        "id": doc_id,
                        "text": item.text,
                        "metadata": metadata,
                        "score": weight,
                        "source": "vector",
                        "similarity": item.similarity
                    }
        except Exception as e:
            print(f"向量检索失败: {e}")
            vector_results = []

        # 2. 知识图谱检索
        try:
            graph_results = self.knowledge_graph.get_neighbors(
                query, depth=Config.GRAPH_MAX_HOPS
            )
            for rank, item in enumerate(graph_results):
                node_id = item["node_id"]
                weight = Config.GRAPH_WEIGHT * (1 / (60 + rank + 1))
                if node_id in all_results:
                    all_results[node_id]["score"] += weight
                    all_results[node_id]["graph_relation"] = item.get("relation", "")
                else:
                    all_results[node_id] = {
                        "id": node_id,
                        "text": item.get("title", item.get("name", "")),
                        "metadata": {"title": item.get("title", "")},
                        "score": weight,
                        "source": "graph",
                        "graph_relation": item.get("relation", ""),
                        "similarity": 0
                    }
        except Exception as e:
            print(f"图谱检索失败: {e}")

        # 3. RRF融合排序 (Reciprocal Rank Fusion)
        sorted_results = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)

        # 4. 去重并限制数量
        seen = set()
        unique_results = []
        for item in sorted_results:
            if item["id"] not in seen:
                seen.add(item["id"])
                unique_results.append(item)
                if len(unique_results) >= top_k * 2:  # 保留更多用于重排序
                    break

        return unique_results

    def rerank_results(self, query: str, retrieved_docs: List[Dict], top_k: int = None) -> List[Dict]:
        """对检索结果进行重排序。

        本地模型受 CPU 性能限制默认关闭（RERANK_ENABLED=false）；
        API 模式（RERANKER_API_ENABLED + key）毫秒级，自动生效。
        """
        top_k = top_k or Config.RERANK_TOP_K
        api_rerank = bool(
            getattr(Config, "RERANKER_API_ENABLED", False)
            and getattr(Config, "RERANKER_API_KEY", "")
        )
        if not Config.RERANK_ENABLED and not api_rerank:
            return retrieved_docs[:top_k]
        return self.reranker.rerank(query, retrieved_docs, top_k)

    def build_context(
        self,
        retrieved_docs: List[Dict],
        max_length: int = None,
        injected_out: List = None,
    ) -> str:
        """构建检索上下文；检测到注入模式的文档会被剔除并记录到 injected_out。

        检索/合成解耦：检索命中的是小块（行号精确），喂给 LLM 的是父块
        （所属段落全文，上下文完整）。
        """
        max_length = max_length or Config.MAX_CONTEXT_LENGTH
        context_parts = []
        injected_out = [] if injected_out is None else injected_out

        total_length = 0
        for i, doc in enumerate(retrieved_docs, 1):
            metadata = doc.get("metadata", {})
            source = metadata.get("source", "未知来源")
            title = metadata.get("title", "")
            content = metadata.get("parent_text") or doc["text"]

            flags = detect_prompt_injection(f"{title}\n{content}")
            if flags:
                injected_out.append((doc.get("id", ""), flags))
                continue

            # 计算当前部分长度
            part_length = len(title) + len(source) + len(content) + 50
            if total_length + part_length > max_length:
                break

            start_line = metadata.get("start_line")
            end_line = metadata.get("end_line")
            line_info = ""
            if start_line and end_line:
                line_info = f"（对应原文第 {start_line}-{end_line} 行）"

            part = f"""【参考资料 {i}】{line_info}
标题：{title}
来源：{source}
内容：{content}"""

            context_parts.append(part)
            total_length += part_length

        return wrap_untrusted_section(context_parts)

    def build_prompt(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict] = None,
        include_history: bool = True,
        user_preferences: Dict[str, Any] = None,
        memories: List[Dict] = None,
    ) -> List[Dict]:
        """
        构建 Prompt（委托 rag_prompt_builder：XML 标签化 + 稳定 system 前缀）

        Args:
            query: 用户问题
            context: 检索上下文
            conversation_history: 对话历史
            include_history: 是否包含历史
            user_preferences: 用户偏好
            memories: 用户持久记忆（Mem0 风格 SEARCH 结果）

        Returns:
            消息列表
        """
        return build_qa_messages(
            query=query,
            context=context,
            conversation_history=conversation_history,
            include_history=include_history,
            user_preferences=user_preferences,
            memories=memories,
            history_token_budget=Config.QA_HISTORY_TOKEN_BUDGET,
        )

    _DEFAULT_QA_MAX_TOKENS = DEFAULT_QA_MAX_TOKENS

    def _resolve_qa_max_tokens(self, user_preferences: Dict[str, Any] | None) -> int:
        """从用户偏好解析 QA 回答最大 tokens；缺失或非法时回退引擎默认。"""
        return resolve_qa_max_tokens(user_preferences)

    def generate(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict] = None,
        retrieved_docs: List[Dict] = None,
        user_preferences: Dict[str, Any] = None,
        user_id: int | None = None,
        operation: str = "qa",
        memories: List[Dict] = None,
        messages: List[Dict] | None = None,
    ) -> Dict[str, Any]:
        """Generate an answer through the shared Provider contract."""
        start_time = time.time()
        messages = messages or self.build_prompt(
            query,
            context,
            conversation_history,
            user_preferences=user_preferences,
            memories=memories,
        )
        provider = self._provider_for_call(user_id=user_id, operation=operation)
        if provider is None:
            return self._unavailable_result(start_time)

        request = LLMRequest(
            prompt=_render_messages_for_provider(messages),
            system_prompt=_system_prompt_from_messages(messages),
            max_tokens=self._resolve_qa_max_tokens(user_preferences),
            prompt_cache_key=self._prompt_cache_key(
                provider,
                _system_prompt_from_messages(messages),
            ),
        )
        try:
            response = provider.generate(request)
        except Exception:
            return self._provider_failure_result(
                provider,
                start_time,
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
            )
        if not isinstance(response, LLMResponse):
            return self._provider_failure_result(
                provider,
                start_time,
                warning_code="LLM_PROVIDER_RESPONSE_INVALID",
            )
        if not response.is_success:
            return self._provider_failure_result(
                provider,
                start_time,
                warning_code=response.warning_code or "LLM_PROVIDER_FAILED",
                response=response,
            )

        return {
            "answer": response.text,
            "reasoning": response.reasoning,
            "sources": self._source_payload(retrieved_docs),
            "confidence": self._calculate_confidence(retrieved_docs),
            "model_name": response.model,
            "provider": response.provider_name,
            "model_version": response.model_version,
            "response_time": _response_time_seconds(response, start_time),
            "warning_code": response.warning_code,
            "usage": response.usage,
            "rag_warnings": self._rag_warnings(),
        }

    def _get_llm_provider(self, *, user_id: int | None = None, operation: str = "qa"):
        """Get the configured remote Provider from the shared selector."""
        try:
            return select_provider(user_id=user_id, operation=operation)
        except RuntimeError:
            # Offline retrieval can continue without a Flask application context.
            return None

    def _provider_for_call(self, *, user_id: int | None, operation: str):
        """Keep the legacy no-argument provider hook usable for default QA calls."""
        if user_id is None and operation == "qa":
            return self._get_llm_provider()
        return self._get_llm_provider(user_id=user_id, operation=operation)

    def _prompt_cache_key(self, provider: object, system_prompt: str | None) -> str:
        """稳定前缀缓存键，与 LabexAgent PromptCacheKeyFactory 对齐。

        同一 Provider + 模型 + 系统提示 映射到同一缓存键，使 MiniMax 等
        Provider 每次请求都报告该键的缓存命中情况（命中/未命中）。
        """
        return for_stable_prefix(
            base_url=getattr(provider, "base_url", "") or "",
            model_name=getattr(provider, "model", "") or "",
            system_prompt=system_prompt or "",
            tool_schema_json="",
        )

    def _source_payload(self, retrieved_docs: List[Dict] = None) -> list[dict]:
        sources: list[dict] = []
        for doc in (retrieved_docs or [])[:3]:
            metadata = doc.get("metadata", {})
            source_info = {
                "title": metadata.get("title", ""),
                "source": metadata.get("source", ""),
                "similarity": doc.get("similarity", 0),
                "doc_id": doc.get("id", ""),
                "start_line": metadata.get("start_line", 0),
                "end_line": metadata.get("end_line", 0),
            }
            if source_info not in sources:
                sources.append(source_info)
        return sources

    def _unavailable_result(self, start_time: float) -> Dict[str, Any]:
        return {
            "answer": "LLM服务暂不可用，请检查 Provider 配置。",
            "reasoning": None,
            "sources": [],
            "confidence": 0.0,
            "model_name": None,
            "provider": None,
            "model_version": None,
            "response_time": time.time() - start_time,
            "error": "API未配置",
            "warning_code": "LLM_PROVIDER_UNAVAILABLE",
            "rag_warnings": [],
        }

    def _provider_failure_result(
        self,
        provider: object,
        start_time: float,
        *,
        warning_code: str,
        response: LLMResponse | None = None,
    ) -> Dict[str, Any]:
        return {
            "answer": "生成失败：当前 LLM Provider 不可用。",
            "reasoning": None,
            "sources": [],
            "confidence": 0.0,
            "model_name": response.model if response else getattr(provider, "model", None),
            "provider": response.provider_name if response else getattr(provider, "provider_name", None),
            "model_version": response.model_version if response else getattr(provider, "model_version", None),
            "response_time": _response_time_seconds(response, start_time),
            "error": warning_code,
            "warning_code": warning_code,
            "rag_warnings": [],
        }

    def _calculate_confidence(self, retrieved_docs: List[Dict]) -> float:
        """计算答案置信度（降级模式下 similarity 可能为 None，需归一化）"""
        if not retrieved_docs:
            return 0.0

        # 综合考虑相似度分数
        scores = []
        for doc in retrieved_docs:
            # 原始检索分数（词法降级时可能为 None）
            sim = doc.get("similarity") or 0
            # 重排序分数（如果有）
            rerank = doc.get("rerank_score") or 0
            cross = doc.get("cross_score") or 0

            # 综合分数
            combined = 0.3 * sim + 0.3 * rerank + 0.4 * cross if cross else sim
            scores.append(combined)

        avg_score = sum(scores) / len(scores)
        # 转换为置信度（0-1）
        confidence = min(avg_score * 1.5, 1.0)
        return round(confidence, 3)

    def _retrieve_and_build(
        self,
        query: str,
        use_rerank: bool = True
    ) -> Tuple[List[Dict], str]:
        """混合检索并构建上下文（供 ask / generate_stream 复用）"""
        retrieve_started = perf_counter()
        retrieved_docs = self.retrieve(query)
        if use_rerank and retrieved_docs:
            retrieved_docs = self.rerank_results(query, retrieved_docs)
        self.last_retrieval_ms = int((perf_counter() - retrieve_started) * 1000)
        injected: List[tuple[str, tuple[str, ...]]] = []
        context = self.build_context(retrieved_docs, injected_out=injected)
        self.last_injected_docs = injected
        return retrieved_docs, context

    def _rag_warnings(self) -> list[str]:
        """把被剔除的注入文档序列化为可审计的警告列表。"""
        injected_docs = getattr(self, "last_injected_docs", ())
        return [
            f"{doc_id}:{','.join(flags)}" for doc_id, flags in injected_docs
        ]

    def generate_stream(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict] = None,
        retrieved_docs: List[Dict] = None,
        user_preferences: Dict[str, Any] = None,
        user_id: int | None = None,
        operation: str = "qa",
        memories: List[Dict] = None,
    ) -> Any:
        """流式生成回答，逐块产出事件字典。

        Yields:
            {"type": "delta", "content": str}
            {"type": "reasoning", "delta": str}
            {"type": "done", "answer": ..., "reasoning": ..., ...} 完整结果
        """
        start_time = time.time()
        messages = self.build_prompt(
            query,
            context,
            conversation_history,
            user_preferences=user_preferences,
            memories=memories,
        )
        provider = self._provider_for_call(user_id=user_id, operation=operation)
        if provider is None:
            yield {"type": "done", **self._unavailable_result(start_time)}
            return

        request = LLMRequest(
            prompt=_render_messages_for_provider(messages),
            system_prompt=_system_prompt_from_messages(messages),
            max_tokens=self._resolve_qa_max_tokens(user_preferences),
            prompt_cache_key=self._prompt_cache_key(
                provider,
                _system_prompt_from_messages(messages),
            ),
        )
        stream_method = getattr(provider, "generate_stream", None)
        if not callable(stream_method):
            # Provider 不支持流式：降级为一次性生成
            result = self.generate(
                query,
                context,
                conversation_history,
                retrieved_docs,
                user_preferences,
                user_id=user_id,
                operation=operation,
                memories=memories,
            )
            yield {"type": "done", **result}
            return

        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        warning_code: str | None = None
        try:
            for chunk in stream_method(request):
                if chunk.delta:
                    text_parts.append(chunk.delta)
                    yield {"type": "delta", "content": chunk.delta}
                if chunk.reasoning_delta:
                    reasoning_parts.append(chunk.reasoning_delta)
                    yield {"type": "reasoning", "delta": chunk.reasoning_delta}
                if chunk.warning_code:
                    warning_code = chunk.warning_code
                if chunk.finished:
                    break
        except Exception:
            warning_code = "LLM_PROVIDER_REQUEST_FAILED"

        answer = "".join(text_parts).strip()
        if not answer or warning_code:
            result = self._provider_failure_result(
                provider,
                start_time,
                warning_code=warning_code or "LLM_OUTPUT_INVALID",
            )
            yield {"type": "done", **result}
            return

        yield {
            "type": "done",
            "answer": answer,
            "reasoning": "".join(reasoning_parts).strip() or None,
            "sources": self._source_payload(retrieved_docs),
            "confidence": self._calculate_confidence(retrieved_docs),
            "model_name": getattr(provider, "model", None),
            "provider": getattr(provider, "provider_name", None),
            "model_version": getattr(provider, "model_version", None),
            "response_time": _response_time_seconds(None, start_time),
            "warning_code": None,
            "usage": {},
            "rag_warnings": self._rag_warnings(),
        }

    def _retrieved_docs_payload(self, retrieved_docs: List[Dict]) -> list[dict]:
        """序列化检索文档供端点返回（含行号，引用可定位到具体行）"""
        return [
            {
                "id": doc["id"],
                "title": doc.get("metadata", {}).get("title", ""),
                "source": doc.get("metadata", {}).get("source", ""),
                "similarity": doc.get("similarity", 0),
                "source_type": doc.get("source", "unknown"),
                "start_line": doc.get("metadata", {}).get("start_line", 0),
                "end_line": doc.get("metadata", {}).get("end_line", 0),
            }
            for doc in retrieved_docs[:5]
        ]

    def _enterprise_rag_pipeline(self):
        """委托公共 RAG Core 适配器，避免继续扩展遗留引擎。"""
        from app.services.rag_core.engine_adapter import build_public_rag_pipeline

        return build_public_rag_pipeline(self)
    @staticmethod
    def _rag_execution_request(
        query: str,
        conversation_history: List[Dict] | None,
        use_rerank: bool,
        user_preferences: Dict[str, Any] | None,
        user_id: int | None,
        memories: List[Dict] | None,
    ):
        """将 legacy 参数收敛为 RAG Core request；请求原文不写入 trace。"""
        from app.services.rag_core import RagExecutionRequest

        return RagExecutionRequest(
            query=query,
            request_id=uuid.uuid4().hex,
            conversation_history=tuple(conversation_history or ()),
            use_rerank=use_rerank,
            user_preferences=user_preferences,
            user_id=user_id,
            memories=tuple(memories or ()),
        )

    def ask_stream(
        self,
        query: str,
        conversation_history: List[Dict] = None,
        use_rerank: bool = True,
        user_preferences: Dict[str, Any] = None,
        user_id: int | None = None,
        memories: List[Dict] = None,
    ) -> Any:
        """流式 RAG 入口；默认保持 legacy 行为，v2 仅通过 Feature Flag 灰度启用。"""
        if not Config.RAG_PIPELINE_V2_ENABLED:
            yield from self._ask_stream_legacy(
                query,
                conversation_history,
                use_rerank,
                user_preferences,
                user_id,
                memories,
            )
            return
        request = self._rag_execution_request(
            query,
            conversation_history,
            use_rerank,
            user_preferences,
            user_id,
            memories,
        )
        yield from self._enterprise_rag_pipeline().stream(request)
    def _ask_stream_legacy(
        self,
        query: str,
        conversation_history: List[Dict] = None,
        use_rerank: bool = True,
        user_preferences: Dict[str, Any] = None,
        user_id: int | None = None,
        memories: List[Dict] = None,
    ) -> Any:
        """完整的流式 RAG 问答流程，逐块产出事件字典。

        Yields:
            {"type": "delta", "content": str}
            {"type": "reasoning", "delta": str}
            {"type": "done", ...完整结果, "retrieved_docs": [...]}
        """
        retrieved_docs, context = self._retrieve_and_build(query, use_rerank)
        for event in self.generate_stream(
            query,
            context,
            conversation_history,
            retrieved_docs,
            user_preferences,
            user_id=user_id,
            operation="qa",
            memories=memories,
        ):
            if event["type"] == "done":
                event["retrieved_docs"] = self._retrieved_docs_payload(retrieved_docs)
            yield event

    def ask(
        self,
        query: str,
        conversation_history: List[Dict] = None,
        use_rerank: bool = True,
        user_preferences: Dict[str, Any] = None,
        user_id: int | None = None,
        memories: List[Dict] = None,
    ) -> Dict[str, Any]:
        """非流式 RAG 入口；默认保持 legacy 行为，v2 使用统一执行契约。"""
        if not Config.RAG_PIPELINE_V2_ENABLED:
            return self._ask_legacy(
                query,
                conversation_history,
                use_rerank,
                user_preferences,
                user_id,
                memories,
            )
        request = self._rag_execution_request(
            query,
            conversation_history,
            use_rerank,
            user_preferences,
            user_id,
            memories,
        )
        return self._enterprise_rag_pipeline().execute(request).to_legacy_payload()
    def _ask_legacy(
        self,
        query: str,
        conversation_history: List[Dict] = None,
        use_rerank: bool = True,
        user_preferences: Dict[str, Any] = None,
        user_id: int | None = None,
        memories: List[Dict] = None,
    ) -> Dict[str, Any]:
        """
        完整的RAG问答流程

        Args:
            query: 用户问题
            conversation_history: 对话历史
            use_rerank: 是否使用重排序
            memories: 用户持久记忆（Mem0 风格 SEARCH 结果）

        Returns:
            包含答案、来源、置信度等信息的字典
        """
        # 1. 混合检索 + 2. 重排序 + 3. 构建上下文
        retrieved_docs, context = self._retrieve_and_build(query, use_rerank)

        # 4. 生成答案
        result = self.generate(
            query,
            context,
            conversation_history,
            retrieved_docs,
            user_preferences,
            user_id=user_id,
            operation="qa",
            memories=memories,
        )

        # 5. 补充来源信息
        result["retrieved_docs"] = self._retrieved_docs_payload(retrieved_docs)

        return result

    def get_suggested_questions(self, query: str, user_id: int | None = None) -> List[str]:
        """Generate follow-up questions through the shared Provider contract."""
        suggestions: list[str] = []
        prompt = f"""\u57fa\u4e8e\u4ee5\u4e0b\u7f51\u7edc\u5b89\u5168\u95ee\u9898\uff0c\u751f\u62103\u4e2a\u76f8\u5173\u7684\u8ffd\u95ee\u5efa\u8bae\u3002
\u8ffd\u95ee\u5e94\u8be5\uff1a
1. \u6df1\u5165\u63a2\u8ba8\u539f\u95ee\u9898\u7684\u67d0\u4e2a\u65b9\u9762
2. \u6d89\u53ca\u76f8\u5173\u7684\u5b9e\u9645\u5e94\u7528\u573a\u666f
3. \u8be2\u95ee\u539f\u7406\u6216\u6700\u4f73\u5b9e\u8df5

\u95ee\u9898\uff1a{query}

\u8bf7\u53ea\u8f93\u51fa\u8ffd\u95ee\u5efa\u8bae\uff0c\u6bcf\u884c\u4e00\u4e2a\uff0c\u683c\u5f0f\u4e3a\"\u8ffd\u95ee\uff1axxx\"\u3002"""
        provider = self._get_llm_provider(user_id=user_id, operation="suggestion")
        if provider is not None:
            try:
                response = provider.generate(
                    LLMRequest(
                        prompt=prompt,
                        max_tokens=resolve_provider_max_tokens(provider, 512),
                        prompt_cache_key=self._prompt_cache_key(provider, None),
                    )
                )
                if isinstance(response, LLMResponse) and response.is_success and response.text:
                    for line in response.text.splitlines():
                        normalized = line.strip().replace("\u8ffd\u95ee\uff1a", "").replace("\u8ffd\u95ee:", "").strip()
                        if normalized and len(normalized) > 5:
                            suggestions.append(normalized)
            except Exception:
                suggestions = []

        if len(suggestions) < 3:
            topic = query.split()[0] if query.split() else "\u8fd9\u4e2a"
            default_suggestions = [
                f"\u80fd\u8be6\u7ec6\u89e3\u91ca\u4e00\u4e0b{topic}\u6982\u5ff5\u5417\uff1f",
                f"{query}\u5728\u5b9e\u9645\u573a\u666f\u4e2d\u5982\u4f55\u5e94\u7528\uff1f",
                "\u6709\u4ec0\u4e48\u76f8\u5173\u7684\u5b89\u5168\u6848\u4f8b\uff1f",
                f"{query}\u7684\u9632\u5fa1\u63aa\u65bd\u6709\u54ea\u4e9b\uff1f",
                f"{query}\u7684\u539f\u7406\u662f\u4ec0\u4e48\uff1f",
            ]
            for suggestion in default_suggestions:
                if suggestion not in suggestions and len(suggestions) < 3:
                    suggestions.append(suggestion)
        return suggestions[:3]

    def index_knowledge(self, knowledge_items: List[Dict]) -> Dict[str, int]:
        """为知识库建立索引（按文档分块入库，每块一个向量，payload 带行号元数据）"""
        vector_count = 0
        graph_count = 0

        # 向量化存储：先按 doc_id 清理旧块，再分块写入
        backend = self.vector_store.backend
        for item in knowledge_items:
            doc_id = str(item["id"])
            text = f"{item.get('title', '')}。{item.get('content', '')}"
            chunks = chunk_text(
                text,
                doc_id=doc_id,
                metadata={
                    "title": item.get("title", ""),
                    "category": item.get("category_name", ""),
                    "source": item.get("source", ""),
                    "difficulty": item.get("difficulty", "medium"),
                    "title_path": item.get("title", ""),
                },
                strategy="smart",
            )
            if not chunks:
                continue
            try:
                backend.delete(where={"doc_id": doc_id})
                vectors = self.vector_store.embedding_service.encode(
                    [chunk["text"] for chunk in chunks]
                )
                written = backend.upsert(
                    ids=[chunk["id"] for chunk in chunks],
                    vectors=vectors.tolist(),
                    texts=[chunk["text"] for chunk in chunks],
                    metadatas=[
                        {
                            "doc_id": doc_id,
                            "chunk_index": index,
                            "start_line": chunk.get("start_line", 0),
                            "end_line": chunk.get("end_line", 0),
                            "start_char": chunk.get("start_char", 0),
                            "end_char": chunk.get("end_char", 0),
                            "title_path": item.get("title", ""),
                            "title": item.get("title", ""),
                            "category": item.get("category_name", ""),
                            "source": item.get("source", ""),
                            "difficulty": item.get("difficulty", "medium"),
                            "parent_text": chunk.get("metadata", {}).get("parent_text", ""),
                        }
                        for index, chunk in enumerate(chunks)
                    ],
                )
                vector_count += written
            except Exception as e:
                print(f"索引写入失败 doc={doc_id}: {e}")

        # 图谱构建
        graph_count = self.knowledge_graph.add_entities_from_knowledge(knowledge_items)

        return {
            "vector_indexed": vector_count,
            "graph_indexed": graph_count,
            "total": len(knowledge_items)
        }

    def find_related_knowledge(
        self,
        knowledge_item: Dict[str, Any],
        top_k: int = 5,
        include_category_bonus: bool = True
    ) -> List[Dict[str, Any]]:
        """
        查找与给定知识条目相关的其他知识

        混合推荐算法：
        1. 向量相似度搜索（语义相似）
        2. 知识图谱关联（实体关系）
        3. 分类加成（同分类优先）

        Args:
            knowledge_item: 知识条目字典，包含 id, title, content, category_id, tags 等
            top_k: 返回数量
            include_category_bonus: 是否启用同分类加成

        Returns:
            相关知识列表，按综合评分排序
        """
        all_scores: Dict[str, Dict] = {}

        # 构建查询文本
        query_text = f"{knowledge_item.get('title', '')}。{knowledge_item.get('content', '')}"
        item_category_id = knowledge_item.get("category_id")
        item_tags = knowledge_item.get("tags", [])

        # 1. 向量相似度搜索
        try:
            vector_results = self.vector_store.search(query_text, top_k=top_k * 3)
            for rank, result in enumerate(vector_results):
                doc_id = str(result.get("metadata", {}).get("doc_id") or result["id"])
                if doc_id == str(knowledge_item.get("id")):
                    continue

                # 基础相似度分数 (排名衰减)
                base_score = 0.5 * (1 / (1 + rank * 0.1))

                all_scores[doc_id] = {
                    "id": doc_id,
                    "title": result["metadata"].get("title", ""),
                    "similarity": result.get("similarity", 0),
                    "vector_rank": rank + 1,
                    "category_id": result["metadata"].get("category_id"),
                    "tags": result["metadata"].get("tags", []),
                    "base_score": base_score,
                    "final_score": base_score
                }
        except Exception as e:
            print(f"向量检索失败: {e}")

        # 2. 知识图谱关联
        try:
            graph_results = self.knowledge_graph.get_neighbors(
                knowledge_item.get("title", ""),
                depth=2
            )
            for rank, result in enumerate(graph_results):
                node_id = result["node_id"]
                if node_id == str(knowledge_item.get("id")):
                    continue
                if node_id in all_scores:
                    # 已在向量结果中，增加图谱加成
                    all_scores[node_id]["final_score"] += 0.2 * (1 / (1 + rank * 0.2))
                    all_scores[node_id]["graph_relation"] = result.get("relation", "")
                else:
                    all_scores[node_id] = {
                        "id": node_id,
                        "title": result.get("title", result.get("name", "")),
                        "similarity": 0,
                        "vector_rank": None,
                        "graph_relation": result.get("relation", ""),
                        "category_id": None,
                        "tags": [],
                        "base_score": 0.15 * (1 / (1 + rank * 0.2)),
                        "final_score": 0.15 * (1 / (1 + rank * 0.2))
                    }
        except Exception as e:
            print(f"图谱检索失败: {e}")

        # 3. 同分类加成
        if include_category_bonus and item_category_id:
            for doc_id, scores in all_scores.items():
                if scores.get("category_id") == item_category_id:
                    scores["final_score"] += 0.15
                    scores["same_category"] = True

        # 4. 标签重叠加成
        if item_tags:
            for doc_id, scores in all_scores.items():
                doc_tags = scores.get("tags", [])
                if isinstance(doc_tags, str):
                    doc_tags = [doc_tags]
                common_tags = set(item_tags) & set(doc_tags)
                if common_tags:
                    scores["final_score"] += 0.1 * len(common_tags)
                    scores["common_tags"] = list(common_tags)

        # 排序并返回 top_k
        sorted_results = sorted(
            all_scores.values(),
            key=lambda x: x["final_score"],
            reverse=True
        )

        return sorted_results[:top_k]

    def batch_index_documents(
        self,
        documents: List[Dict[str, Any]],
        chunk_strategy: str = "smart"
    ) -> Dict[str, Any]:
        """
        批量索引文档（包含分块）

        Args:
            documents: [{"id": str, "text": str, "metadata": dict}, ...]
            chunk_strategy: 分块策略 "sentence", "paragraph", "smart"

        Returns:
            索引结果统计
        """
        from app.services.text_chunker import chunk_documents_batch

        # 文本分块
        chunks = chunk_documents_batch(documents, strategy=chunk_strategy)

        # 批量添加到向量库
        vector_count = self.vector_store.add_documents_batch(chunks)

        return {
            "chunks_created": len(chunks),
            "vectors_indexed": vector_count,
            "documents_processed": len(documents)
        }


# 全局单例
enhanced_rag_engine = None


def _system_prompt_from_messages(messages: List[Dict]) -> str | None:
    system_messages = [message.get("content", "") for message in messages if message.get("role") == "system"]
    return "\n\n".join(content for content in system_messages if content) or None


def _render_messages_for_provider(messages: List[Dict]) -> str:
    rendered = []
    for message in messages:
        role = str(message.get("role", "user")).strip() or "user"
        content = str(message.get("content", ""))
        if role == "system":
            continue
        rendered.append(f"[{role}]\n{content}")
    return "\n\n".join(rendered)


def _response_time_seconds(response: LLMResponse | None, started: float) -> float:
    if response is not None and response.latency_ms is not None:
        return response.latency_ms / 1000
    return time.time() - started


def get_enhanced_rag_engine() -> EnhancedRAGEngine:
    global enhanced_rag_engine
    if enhanced_rag_engine is None:
        enhanced_rag_engine = EnhancedRAGEngine()
    return enhanced_rag_engine


# 保持向后兼容
def get_rag_engine() -> EnhancedRAGEngine:
    """获取 RAG 引擎（向后兼容）"""
    return get_enhanced_rag_engine()
