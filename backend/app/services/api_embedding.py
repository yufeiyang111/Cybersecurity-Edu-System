"""
硅基流动 API embedding 服务（OpenAI 兼容 /v1/embeddings）。

- 免费 BAAI/bge-m3，1024 维，与本地模型同维（Qdrant 库无需重建）；
- 接口与 SecBERTEmbedding 保持一致（encode / encode_query / is_degraded / dimension）；
- API 不可用（key 缺失或请求失败）时标记降级，检索侧自动改走 BM25 词法路。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Union

import numpy as np
import requests

from app.config import Config

logger = logging.getLogger(__name__)


class ApiEmbedding:
    """基于硅基流动 API 的向量化模型。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = 32,
    ) -> None:
        self.base_url = (base_url or Config.EMBEDDING_API_BASE).rstrip("/")
        self.api_key = api_key if api_key is not None else Config.EMBEDDING_API_KEY
        self.model = model or Config.EMBEDDING_API_MODEL
        self.batch_size = batch_size
        self._api_failed = False

    @property
    def dimension(self) -> int:
        return Config.EMBEDDING_DIMENSION

    @property
    def is_degraded(self) -> bool:
        """key 缺失或 API 曾失败 → 降级（检索走词法）。"""
        if not self.api_key:
            return True
        return self._api_failed

    def _request(self, texts: List[str]) -> np.ndarray:
        """调用 /v1/embeddings，返回 (n, dim) 归一化向量。"""
        response = requests.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": self.model, "encoding_format": "float"},
            timeout=(5, 60),
        )
        if response.status_code != 200:
            logger.warning(
                "siliconflow embeddings 请求失败 status=%s detail=%s",
                response.status_code,
                response.text[:300],
            )
            self._api_failed = True
            raise RuntimeError(f"embeddings api status={response.status_code}")
        body = response.json()
        data = body.get("data") or []
        if len(data) != len(texts):
            logger.warning("siliconflow embeddings 返回数量不一致")
            self._api_failed = True
            raise RuntimeError("embeddings api count mismatch")
        vectors = np.asarray(
            [item.get("embedding") for item in sorted(data, key=lambda d: d.get("index", 0))],
            dtype=np.float32,
        )
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return vectors / norms

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: Optional[int] = None,
        show_progress: bool = False,
    ) -> np.ndarray:
        """将文本编码为向量（L2 归一化）。"""
        if isinstance(texts, str):
            texts = [texts]
        texts = [str(t) for t in texts]
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        batch_size = batch_size or self.batch_size
        all_embeddings: List[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            all_embeddings.append(self._request(batch))
        return np.vstack(all_embeddings)

    def encode_query(self, query: str) -> np.ndarray:
        """编码查询文本（BGE 系模型追加查询指令，文档编码不加）。"""
        prefix = Config.EMBEDDING_QUERY_PREFIX.strip()
        if prefix:
            query = f"{prefix}{query}"
        return self.encode(query)

    def encode_documents(self, documents: List[str], **kwargs) -> np.ndarray:
        return self.encode(documents, **kwargs)

    def compute_similarity(self, query: str, documents: List[str]) -> List[float]:
        """计算查询与多个文档的相似度。"""
        query_emb = self.encode_query(query)
        if not documents:
            return []
        text_embs = self.encode(documents)
        similarities = np.dot(text_embs, query_emb.T).flatten()
        return similarities.tolist()

    def similarity(self, text1: str, text2: str) -> float:
        return float(np.dot(self.encode(text1), self.encode(text2).T)[0, 0])

    def similarities(self, query: str, texts: List[str]) -> List[float]:
        return self.compute_similarity(query, texts)

    def get_embedding_dimension(self) -> int:
        return self.dimension
