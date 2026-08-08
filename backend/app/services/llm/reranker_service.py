"""
真实 rerank 服务：基于 cross-encoder 的排序模型（默认 bge-reranker-v2-m3）。

- 输入 (query, passage) 对，输出相关性分数（sigmoid 归一化）；
- 模型加载失败时返回 None 调用方降级（保持原有伪重排行为）；
- 懒加载：首次使用时才加载模型，避免拖慢应用启动。
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from app.config import Config

logger = logging.getLogger(__name__)

# 默认模型：与 bge-m3 同目录的本地模型（D 盘）
DEFAULT_RERANKER_MODEL = "D:/rag-medical/models/bge-reranker-v2-m3"


class RerankerService:
    """基于 cross-encoder 的排序服务。"""

    _instance: Optional["RerankerService"] = None

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or Config.RERANKER_MODEL
        self.tokenizer = None
        self.model = None
        self.device = "cpu"

    def _load(self) -> bool:
        """加载模型（幂等）。失败返回 False，调用方降级。"""
        if self.model is not None:
            return True
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            os.environ.setdefault("HF_ENDPOINT", Config.HF_ENDPOINT)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            dtype = torch.float16 if Config.RERANKER_HALF_PRECISION else torch.float32
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                dtype=dtype,
            )
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            self.model.eval()
            logger.info("reranker loaded: %s (device=%s)", self.model_name, self.device)
            return True
        except Exception as exc:
            logger.warning("reranker 加载失败，将降级为伪重排: %s", exc)
            self.model = None
            return False

    def score(self, query: str, passage: str) -> float:
        """对 (query, passage) 打分，返回 [0,1] 相关性。失败返回 -1。"""
        if not self._load():
            return -1.0
        try:
            import torch

            encoded = self.tokenizer(
                [query],
                [passage],
                padding=True,
                truncation=True,
                max_length=Config.RERANKER_MAX_LENGTH,
                return_tensors="pt",
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            with torch.no_grad():
                logits = self.model(**encoded).logits
            probs = torch.sigmoid(logits)[0, 0].item()
            return float(probs)
        except Exception as exc:
            logger.warning("rerank score 失败: %s", exc)
            return -1.0

    def rerank(
        self,
        query: str,
        documents: List[dict],
        top_k: int,
    ) -> List[dict]:
        """对文档列表批量重排，返回 top_k 个（保持原字典结构，附加 rerank_score）。

        documents: [{"text": str, ...}] 或 [{"id":..., "text":...}]
        """
        if not documents:
            return []
        if not self._load():
            return documents[:top_k]

        texts = [
            str(doc.get("text") if isinstance(doc, dict) else doc)
            for doc in documents
        ]
        scores = self._batch_score(query, texts)
        if scores is None:
            return documents[:top_k]

        scored = [
            {**doc, "rerank_score": score}
            for doc, score in zip(documents, scores)
        ]
        scored.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
        return scored[:top_k]

    def _batch_score(self, query: str, passages: List[str]) -> Optional[List[float]]:
        """一次前向计算 query 与多个 passage 的相关性分数。"""
        try:
            import torch

            if not passages:
                return []
            encoded = self.tokenizer(
                [query] * len(passages),
                passages,
                padding=True,
                truncation=True,
                max_length=Config.RERANKER_MAX_LENGTH,
                return_tensors="pt",
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            with torch.no_grad():
                logits = self.model(**encoded).logits
            probs = torch.sigmoid(logits)[:, 0].tolist()
            return [float(p) for p in probs]
        except Exception as exc:
            logger.warning("rerank batch 打分失败: %s", exc)
            return None

    @classmethod
    def get(cls) -> "RerankerService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


reranker_service = None


def get_reranker_service() -> RerankerService:
    global reranker_service
    if reranker_service is None:
        reranker_service = RerankerService()
    return reranker_service
