"""
向量数据库服务 - 使用ChromaDB实现向量检索
支持 SecBERT 中文安全领域向量化模型
"""
import chromadb
from chromadb.config import Settings
import numpy as np
from typing import List, Dict, Any, Optional
from app.config import Config
from app.services.secbert_embedding import get_embedding_service, EmbeddingService

class VectorStore:
    """向量存储和检索服务"""

    def __init__(self):
        self.client = chromadb.PersistentClient(path=Config.CHROMA_PERSIST_DIRECTORY)
        self.collection = self.client.get_or_create_collection(
            name="knowledge_embeddings",
            metadata={"description": "网络安全知识库向量索引"}
        )
        # 使用 SecBERT 向量化服务
        self.embedding_service: EmbeddingService = get_embedding_service()

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """添加文档到向量库"""
        try:
            embedding = self.embedding_service.encode(text)

            # 确保是 2D 数组 (batch_size, embedding_dim)
            if embedding.ndim == 1:
                embedding = embedding.reshape(1, -1)
            elif embedding.ndim == 2:
                if embedding.shape[0] > 1:
                    embedding = embedding[0:1, :]
            elif embedding.ndim == 3:
                # (batch, seq, dim) -> 取第一个
                embedding = embedding[0, 0, :].reshape(1, -1)
            else:
                embedding = embedding.flatten().reshape(1, -1)

            embedding = embedding.tolist()

            self.collection.add(
                ids=[doc_id],
                embeddings=embedding,  # 直接用，已经是 [[...]] 格式
                documents=[text],
                metadatas=[metadata]
            )
            return True
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False

    def add_documents_batch(self, documents: List[Dict[str, Any]]) -> int:
        """批量添加文档"""
        success_count = 0
        for doc in documents:
            if self.add_document(
                doc_id=str(doc["id"]),
                text=doc["text"],
                metadata=doc.get("metadata", {})
            ):
                success_count += 1
        return success_count

    def search(self, query: str, top_k: int = None, filters: Dict = None) -> List[Dict]:
        """向量相似度搜索"""
        top_k = top_k or Config.VECTOR_TOP_K

        query_embedding = self.embedding_service.encode_query(query)

        # 调试：打印原始形状
        print(f"[向量检索] 原始shape: {query_embedding.shape}, dtype: {query_embedding.dtype}")

        # 确保变成 2D 数组 (batch_size, embedding_dim)
        # 多种可能输入: (768,), (1, 768), (1, 1, 768), (seq, 768) 等
        if query_embedding.ndim == 1:
            # (768,) -> (1, 768)
            query_embedding = query_embedding.reshape(1, -1)
        elif query_embedding.ndim == 2:
            # (1, 768) 或 (seq, 768) -> 如果第一个维度>1，取第一行；否则保持
            if query_embedding.shape[0] == 1:
                pass  # 已经是 (1, 768)，OK
            else:
                query_embedding = query_embedding[0:1, :]  # 取第一行
        elif query_embedding.ndim == 3:
            # (batch, seq, dim) -> 取 (0, 0, :)
            if query_embedding.shape[0] == 1 and query_embedding.shape[1] == 1:
                query_embedding = query_embedding[0, 0, :].reshape(1, -1)
            elif query_embedding.shape[0] == 1:
                query_embedding = query_embedding[0, 0, :].reshape(1, -1)
            else:
                query_embedding = query_embedding[0, 0, :].reshape(1, -1)
        else:
            # 其他情况，flatten后reshape
            query_embedding = query_embedding.flatten().reshape(1, -1)

        print(f"[向量检索] 处理后shape: {query_embedding.shape}")

        # 转成 Python list: [[0.1, 0.2, ..., 768]]
        embeddings_list = query_embedding.tolist()
        print(f"[向量检索] 转换后list: type={type(embeddings_list)}, len={len(embeddings_list)}, inner_len={len(embeddings_list[0]) if embeddings_list else 0}")

        results = self.collection.query(
            query_embeddings=embeddings_list,
            n_results=top_k,
            where=filters,
            include=["documents", "metadatas", "distances"]
        )

        search_results = []
        if results["ids"] and len(results["ids"]) > 0:
            for i in range(len(results["ids"][0])):
                distance = results["distances"][0][i]
                similarity = 1 / (1 + distance)
                if similarity >= Config.SIMILARITY_THRESHOLD:
                    search_results.append({
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": similarity,
                        "distance": distance
                    })

        return sorted(search_results, key=lambda x: x["similarity"], reverse=True)

    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def delete_all(self) -> bool:
        """清空向量库"""
        try:
            self.client.delete_collection("knowledge_embeddings")
            self.collection = self.client.get_or_create_collection(
                name="knowledge_embeddings",
                metadata={"description": "网络安全知识库向量索引"}
            )
            return True
        except Exception:
            return False

    def count(self) -> int:
        """获取文档数量"""
        return self.collection.count()


# 全局单例
vector_store = None

def get_vector_store() -> VectorStore:
    global vector_store
    if vector_store is None:
        vector_store = VectorStore()
    return vector_store
