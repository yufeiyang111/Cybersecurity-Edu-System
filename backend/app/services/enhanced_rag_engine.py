"""
RAG核心引擎 - 增强版
检索增强生成：集成重排序、多路召回、优化的Prompt工程

支持 MiniMax 和 DashScope 通义千问两种 LLM 后端
"""
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from app.config import Config
from app.services.vector_store import get_vector_store
from app.services.graph_store import get_knowledge_graph
from app.services.secbert_embedding import get_embedding_service
from app.services.minimax_llm import MiniMaxLLM, get_minimax_llm

# 通义千问（保留作为备用）
try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False


class Reranker:
    """文档重排序器 - 使用交叉编码器进行精细化排序"""

    def __init__(self):
        self.embedding_service = get_embedding_service()

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

        # 计算 query 与每个文档的精细相似度
        scored_docs = []
        for doc in documents:
            text = doc.get("text", "")
            if not text:
                continue

            # 使用 SecBERT 计算精细相似度
            try:
                similarity = self.embedding_service.embedding_model.similarity(query, text)
            except Exception:
                # 如果 SecBERT 不可用，使用原始分数
                similarity = doc.get("score", doc.get("similarity", 0.5))

            # 综合原始分数和新计算的相似度
            original_score = doc.get("score", doc.get("similarity", 0.5))
            # 双重验证：原始检索相似度 vs 重排序相似度
            combined_score = 0.4 * original_score + 0.6 * similarity

            scored_docs.append({
                **doc,
                "rerank_score": combined_score,
                "original_score": original_score,
                "cross_score": similarity
            })

        # 按综合分数排序
        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

        return scored_docs[:top_k]


class EnhancedRAGEngine:
    """增强版检索增强生成引擎"""

    # 系统提示词 - 网络安全教学助手
    SYSTEM_PROMPT = """你是网络安全领域的专业教学助手"网安卫士"。

你的职责是：
1. 准确回答网络安全相关问题
2. 使用简洁易懂的语言解释复杂概念
3. 提供实际案例和代码示例
4. 标注答案的知识来源
5. 如不确定，明确告知用户

专业知识领域：
- 网络基础：TCP/IP协议、网络攻防原理
- Web安全：SQL注入、XSS、CSRF、SSRF等漏洞原理与防御
- 系统安全：操作系统加固、权限管理、安全配置
- 密码学：对称加密、非对称加密、哈希算法、数字签名
- 渗透测试：信息收集、漏洞利用、后渗透测试
- 应急响应：事件分析、取证调查、溯源处置
- 数据安全：数据加密、脱敏、隐私保护
- 移动安全：Android/iOS安全、应用加固

回答要求：
- 结构清晰，使用标题、列表等格式
- 复杂概念提供图示说明
- 包含相关的安全警告和最佳实践
- 引用可信的知识来源
- 如果问题超出网络安全领域，请说明并尝试提供相关建议"""

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

        # LLM 配置 - 优先使用 MiniMax
        self.llm_provider = "minimax"  # 或 "dashscope"
        self.api_key = Config.MINIMAX_API_KEY
        self.model_name = Config.MINIMAX_MODEL

        # 初始化 MiniMax LLM
        if self.api_key:
            self.minimax_llm = MiniMaxLLM(
                api_key=self.api_key,
                model=self.model_name
            )
        else:
            self.minimax_llm = None

    def retrieve(self, query: str, top_k: int = None) -> List[Dict]:
        """混合检索：向量检索 + 知识图谱检索 + RRF融合"""
        top_k = top_k or Config.VECTOR_TOP_K
        all_results = {}

        # 1. 向量检索（从 ChromaDB）
        try:
            vector_results = self.vector_store.search(query, top_k=top_k * 2)
            for rank, item in enumerate(vector_results):
                weight = Config.VECTOR_WEIGHT * (1 / (60 + rank + 1))
                all_results[item["id"]] = {
                    "id": item["id"],
                    "text": item["text"],
                    "metadata": item.get("metadata", {}),
                    "score": weight,
                    "source": "vector",
                    "similarity": item.get("similarity", 0)
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
        """对检索结果进行重排序"""
        top_k = top_k or Config.RERANK_TOP_K
        return self.reranker.rerank(query, retrieved_docs, top_k)

    def build_context(self, retrieved_docs: List[Dict], max_length: int = None) -> str:
        """构建检索上下文"""
        max_length = max_length or Config.MAX_CONTEXT_LENGTH
        context_parts = []

        total_length = 0
        for i, doc in enumerate(retrieved_docs, 1):
            metadata = doc.get("metadata", {})
            source = metadata.get("source", "未知来源")
            title = metadata.get("title", "")
            content = doc["text"]

            # 计算当前部分长度
            part_length = len(title) + len(source) + len(content) + 50
            if total_length + part_length > max_length:
                break

            part = f"""【参考资料 {i}】
标题：{title}
来源：{source}
内容：{content}"""

            context_parts.append(part)
            total_length += part_length

        return "\n\n".join(context_parts)

    def build_prompt(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict] = None,
        include_history: bool = True
    ) -> List[Dict]:
        """
        构建 Prompt

        Args:
            query: 用户问题
            context: 检索上下文
            conversation_history: 对话历史
            include_history: 是否包含历史

        Returns:
            消息列表
        """
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        if include_history and conversation_history:
            # 添加对话历史（限制最近5轮）
            for msg in conversation_history[-5:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg["content"]
                })

        # 构建用户消息
        if context:
            user_prompt = f"""基于以下网络安全领域的参考资料回答用户问题。
如果上下文中没有相关信息，请基于你的网络安全知识回答，但不要生成果断性的结论。

参考资料：
{context}

用户问题：{query}

请结合参考资料给出准确、专业的回答。
回答要求：
1. 优先使用参考资料中的信息
2. 明确标注答案来源（使用【参考来源】标注）
3. 对于不确定的内容，说明基于何种原理推断
4. 提供相关的安全建议和最佳实践"""
        else:
            user_prompt = f"""请回答以下网络安全领域的问题：

问题：{query}

注意：如果问题超出网络安全领域范围，请明确说明。"""

        messages.append({"role": "user", "content": user_prompt})

        return messages

    def generate(
        self,
        query: str,
        context: str,
        conversation_history: List[Dict] = None,
        retrieved_docs: List[Dict] = None
    ) -> Dict[str, Any]:
        """调用 LLM 生成答案（优先使用 MiniMax）"""
        start_time = time.time()

        # 构建消息
        messages = self.build_prompt(query, context, conversation_history)

        # 优先使用 MiniMax
        if self.minimax_llm and self.api_key:
            try:
                response = self.minimax_llm.chat(messages)

                elapsed_time = time.time() - start_time

                # 调试：打印完整响应
                import sys
                print(f"[MiniMax API] 完整响应: {response}", flush=True)
                sys.stdout.flush()

                if response.get("status_code") == 200:
                    # 兼容不同的响应格式
                    output = response.get("output", {})
                    if isinstance(output, dict) and "choices" in output:
                        answer = output["choices"][0]["message"]["content"]
                    elif isinstance(output, dict) and "text" in output:
                        answer = output["text"]
                    else:
                        answer = str(output)

                    # 提取来源信息
                    sources = []
                    if retrieved_docs:
                        for doc in retrieved_docs[:3]:
                            metadata = doc.get("metadata", {})
                            source_info = {
                                "title": metadata.get("title", ""),
                                "source": metadata.get("source", ""),
                                "similarity": doc.get("similarity", 0)
                            }
                            if source_info not in sources:
                                sources.append(source_info)

                    return {
                        "answer": answer,
                        "sources": sources,
                        "confidence": self._calculate_confidence(retrieved_docs),
                        "model_name": f"MiniMax-{self.model_name}",
                        "response_time": elapsed_time
                    }
                else:
                    return {
                        "answer": f"生成失败：{response.get('message', '未知错误')}",
                        "sources": [],
                        "confidence": 0.0,
                        "model_name": f"MiniMax-{self.model_name}",
                        "response_time": elapsed_time,
                        "error": response.get("message", "")
                    }

            except Exception as e:
                import sys
                import traceback
                print(f"[生成异常] {str(e)}", flush=True)
                print(f"[生成异常] traceback: {traceback.format_exc()}", flush=True)
                sys.stdout.flush()
                return {
                    "answer": f"生成过程出错：{str(e)}",
                    "sources": [],
                    "confidence": 0.0,
                    "model_name": f"MiniMax-{self.model_name}",
                    "response_time": time.time() - start_time,
                    "error": str(e)
                }

        # 备用：使用 DashScope 通义千问
        elif DASHSCOPE_AVAILABLE and Config.DASHSCOPE_API_KEY:
            try:
                response = Generation.call(
                    model=Config.DASHSCOPE_MODEL,
                    messages=messages,
                    result_format="message",
                    api_key=Config.DASHSCOPE_API_KEY
                )

                elapsed_time = time.time() - start_time

                if response.status_code == 200:
                    answer = response.output.choices[0].message.content

                    sources = []
                    if retrieved_docs:
                        for doc in retrieved_docs[:3]:
                            metadata = doc.get("metadata", {})
                            source_info = {
                                "title": metadata.get("title", ""),
                                "source": metadata.get("source", ""),
                                "similarity": doc.get("similarity", 0)
                            }
                            if source_info not in sources:
                                sources.append(source_info)

                    return {
                        "answer": answer,
                        "sources": sources,
                        "confidence": self._calculate_confidence(retrieved_docs),
                        "model_name": Config.DASHSCOPE_MODEL,
                        "response_time": elapsed_time
                    }
                else:
                    return {
                        "answer": f"生成失败：{response.message}",
                        "sources": [],
                        "confidence": 0.0,
                        "model_name": Config.DASHSCOPE_MODEL,
                        "response_time": elapsed_time,
                        "error": response.message
                    }

            except Exception as e:
                return {
                    "answer": f"生成过程出错：{str(e)}",
                    "sources": [],
                    "confidence": 0.0,
                    "model_name": Config.DASHSCOPE_MODEL,
                    "response_time": time.time() - start_time,
                    "error": str(e)
                }

        # 都没有配置
        return {
            "answer": "LLM服务暂不可用，请检查API配置。\n\n请在 .env 文件中配置 MINIMAX_API_KEY 或 DASHSCOPE_API_KEY",
            "sources": [],
            "confidence": 0.0,
            "model_name": None,
            "error": "API未配置"
        }

    def _calculate_confidence(self, retrieved_docs: List[Dict]) -> float:
        """计算答案置信度"""
        if not retrieved_docs:
            return 0.0

        # 综合考虑相似度分数
        scores = []
        for doc in retrieved_docs:
            # 原始检索分数
            sim = doc.get("similarity", 0)
            # 重排序分数（如果有）
            rerank = doc.get("rerank_score", 0)
            cross = doc.get("cross_score", 0)

            # 综合分数
            combined = 0.3 * sim + 0.3 * rerank + 0.4 * cross if cross else sim
            scores.append(combined)

        avg_score = sum(scores) / len(scores)
        # 转换为置信度（0-1）
        confidence = min(avg_score * 1.5, 1.0)
        return round(confidence, 3)

    def ask(
        self,
        query: str,
        conversation_history: List[Dict] = None,
        use_rerank: bool = True
    ) -> Dict[str, Any]:
        """
        完整的RAG问答流程

        Args:
            query: 用户问题
            conversation_history: 对话历史
            use_rerank: 是否使用重排序

        Returns:
            包含答案、来源、置信度等信息的字典
        """
        # 1. 混合检索
        retrieved_docs = self.retrieve(query)

        # 2. 可选：重排序
        if use_rerank and retrieved_docs:
            retrieved_docs = self.rerank_results(query, retrieved_docs)

        # 3. 构建上下文
        context = self.build_context(retrieved_docs)

        # 4. 生成答案
        result = self.generate(query, context, conversation_history, retrieved_docs)

        # 5. 补充来源信息
        result["retrieved_docs"] = [
            {
                "id": doc["id"],
                "title": doc.get("metadata", {}).get("title", ""),
                "source": doc.get("metadata", {}).get("source", ""),
                "similarity": doc.get("similarity", 0),
                "source_type": doc.get("source", "unknown")
            }
            for doc in retrieved_docs[:5]
        ]

        return result

    def get_suggested_questions(self, query: str) -> List[str]:
        """根据问题推荐相关追问"""
        suggestions = []

        prompt = f"""基于以下网络安全问题，生成3个相关的追问建议。
追问应该：
1. 深入探讨原问题的某个方面
2. 涉及相关的实际应用场景
3. 询问原理或最佳实践

问题：{query}

请只输出追问建议，每行一个，格式为"追问：xxx"。"""

        # 优先使用 MiniMax
        if self.minimax_llm and self.api_key:
            try:
                messages = [{"role": "user", "content": prompt}]
                response = self.minimax_llm.chat(messages)

                if response.get("status_code") == 200:
                    content = response["output"]["choices"][0]["message"]["content"]
                    for line in content.split("\n"):
                        line = line.strip()
                        if "追问" in line or "？" in line or "?" in line:
                            line = line.replace("追问：", "").replace("追问:", "").strip()
                            if line and len(line) > 5:
                                suggestions.append(line)
            except Exception:
                pass

        # 备用：使用 DashScope
        elif DASHSCOPE_AVAILABLE and Config.DASHSCOPE_API_KEY:
            try:
                response = Generation.call(
                    model=Config.DASHSCOPE_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    result_format="message",
                    api_key=Config.DASHSCOPE_API_KEY
                )

                if response.status_code == 200:
                    content = response.output.choices[0].message.content
                    for line in content.split("\n"):
                        line = line.strip()
                        if "追问" in line or "？" in line or "?" in line:
                            line = line.replace("追问：", "").replace("追问:", "").strip()
                            if line and len(line) > 5:
                                suggestions.append(line)
            except Exception:
                pass

        # 如果LLM不可用或未返回足够建议，使用默认模板
        if len(suggestions) < 3:
            default_suggestions = [
                f"能详细解释一下{query.split()[0] if query.split() else '这个'}概念吗？",
                f"{query}在实际场景中如何应用？",
                f"有什么相关的安全案例？",
                f"{query}的防御措施有哪些？",
                f"{query}的原理是什么？"
            ]
            for sug in default_suggestions:
                if sug not in suggestions and len(suggestions) < 3:
                    suggestions.append(sug)

        return suggestions[:3]

    def index_knowledge(self, knowledge_items: List[Dict]) -> Dict[str, int]:
        """为知识库建立索引"""
        vector_count = 0
        graph_count = 0

        # 向量化存储
        for item in knowledge_items:
            doc = {
                "doc_id": str(item["id"]),
                "text": f"{item.get('title', '')}。{item.get('content', '')}",
                "metadata": {
                    "title": item.get("title", ""),
                    "category": item.get("category_name", ""),
                    "source": item.get("source", ""),
                    "difficulty": item.get("difficulty", "medium")
                }
            }
            if self.vector_store.add_document(**doc):
                vector_count += 1

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
                doc_id = result["id"]
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

def get_enhanced_rag_engine() -> EnhancedRAGEngine:
    global enhanced_rag_engine
    if enhanced_rag_engine is None:
        enhanced_rag_engine = EnhancedRAGEngine()
    return enhanced_rag_engine


# 保持向后兼容
def get_rag_engine() -> EnhancedRAGEngine:
    """获取 RAG 引擎（向后兼容）"""
    return get_enhanced_rag_engine()