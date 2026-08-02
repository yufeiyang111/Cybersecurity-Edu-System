"""旧版 VectorStore 兼容实现。

保留 add_document / add_documents_batch / search / delete_document / delete_all /
count 公开接口，内部委托给 VectorBackend（Chroma 或 Qdrant），embedding 由
本层调用 SecBERT 完成。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import Config
from app.services.secbert_embedding import get_embedding_service
from app.services.vector_stores.contracts import VectorBackend, to_2d_list


class VectorStore:
    """向量存储和检索服务（兼容原公开接口）。"""

    def __init__(self, *, backend: Optional[VectorBackend] = None):
        self._backend = backend
        self.embedding_service = get_embedding_service()

    @property
    def backend(self) -> VectorBackend:
        if self._backend is None:
            from app.services.vector_stores.factory import create_vector_backend

            self._backend = create_vector_backend()
        return self._backend

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """添加文档到向量库。"""
        try:
            vectors = to_2d_list(self.embedding_service.encode(text))
            written = self.backend.upsert(
                ids=[str(doc_id)],
                vectors=vectors,
                texts=[text],
                metadatas=[metadata or {}],
            )
            return written == 1
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False

    def add_documents_batch(self, documents: List[Dict[str, Any]]) -> int:
        """批量添加文档，返回成功条数。"""
        success_count = 0
        for doc in documents:
            if self.add_document(
                doc_id=str(doc["id"]),
                text=doc["text"],
                metadata=doc.get("metadata", {}),
            ):
                success_count += 1
        return success_count

    def search(
        self,
        query: str,
        top_k: int = None,
        filters: Dict = None,
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索，返回按相似度降序的文档列表。"""
        top_k = top_k or Config.VECTOR_TOP_K
        vector = to_2d_list(self.embedding_service.encode_query(query))[0]
        hits = self.backend.search(vector=vector, where=filters or None, top_k=top_k)
        threshold = Config.SIMILARITY_THRESHOLD
        results = [hit.to_dict() for hit in hits if hit.similarity >= threshold]
        return sorted(results, key=lambda item: item["similarity"], reverse=True)

    def delete_document(self, doc_id: str) -> bool:
        """删除文档。"""
        try:
            self.backend.delete_by_ids(ids=[str(doc_id)])
            return True
        except Exception:
            return False

    def delete_all(self) -> bool:
        """清空向量库。"""
        return self.backend.delete_all()

    def count(self) -> int:
        """获取文档数量。"""
        return self.backend.count()


# 全局单例
vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global vector_store
    if vector_store is None:
        vector_store = VectorStore()
    return vector_store
