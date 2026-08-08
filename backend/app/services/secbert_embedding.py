"""
SecBERT 向量化服务
使用网络安全领域专用的 SecBERT 模型进行文本向量化
"""
import torch
from typing import List, Dict, Any, Optional, Union
import numpy as np

try:
    from transformers import AutoTokenizer, AutoModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

from app.config import Config


class SecBERTEmbedding:
    """向量化模型"""

    # 模型名称或路径；默认 bge-m3（本地 D 盘），可通过 Config.EMBEDDING_MODEL 覆盖
    DEFAULT_MODEL_NAME = "shibing624/text2vec-base-chinese"
    SECBERT_MODEL_NAME = "SecBERT"  # 实际项目中应替换为真实的 SecBERT 模型

    def __init__(
        self,
        model_name: str = None,
        device: str = None,
        max_length: int = None,
        batch_size: int = 32
    ):
        """
        初始化向量化模型

        Args:
            model_name: 模型名称或本地路径
            device: 计算设备 "cuda" 或 "cpu"
            max_length: 最大序列长度
            batch_size: 批处理大小
        """
        self.model_name = model_name or self.DEFAULT_MODEL_NAME
        self.max_length = max_length or Config.EMBEDDING_MAX_LENGTH
        self.batch_size = batch_size

        # 自动选择设备
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.tokenizer = None
        self.model = None
        self._load_model()

    @staticmethod
    def _system_memory_mb() -> Optional[int]:
        """获取系统当前可用物理内存（MB）；非 Windows 或失败返回 None"""
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullAvailPhys / 1024 / 1024)
        except Exception:
            return None
        return None

    def _load_model(self):
        """加载模型：主模型 → 轻量备选模型 → 词袋兜底"""
        if not TRANSFORMERS_AVAILABLE:
            print("警告: transformers 库未安装，将使用备用向量化方案")
            return

        available_mb = self._system_memory_mb()
        main_min_mb = getattr(Config, "EMBEDDING_MIN_FREE_MEMORY_MB", 4096)
        fallback_min_mb = getattr(Config, "EMBEDDING_FALLBACK_MIN_FREE_MEMORY_MB", 1500)

        # 先尝试主模型（内存充足时）
        if available_mb is None or available_mb >= main_min_mb:
            if self._try_load(self.model_name):
                return

        # 主模型内存不足或加载失败：尝试轻量备选模型
        fallback_model = getattr(Config, "EMBEDDING_FALLBACK_MODEL", None)
        if fallback_model and fallback_model != self.model_name:
            if available_mb is not None and available_mb < fallback_min_mb:
                print(
                    f"警告: 可用内存不足（{available_mb}MB < {fallback_min_mb}MB），"
                    "跳过备选模型加载，使用词袋兜底"
                )
            elif self._try_load(fallback_model):
                print(f"已降级使用轻量备选模型: {fallback_model}")
                return

        self.model = None
        print("警告: 模型加载失败，使用备用向量化方案（词袋）")

    def _try_load(self, model_name: str) -> bool:
        """尝试加载指定模型；成功返回 True，失败返回 False"""
        try:
            import os

            os.environ['HF_ENDPOINT'] = Config.HF_ENDPOINT

            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True
            )
            self.model = AutoModel.from_pretrained(
                model_name,
                trust_remote_code=True
            )
            self.model.to(self.device)
            self.model.eval()
            self.model_name = model_name
            print(f"成功加载模型: {model_name}")
            return True
        except MemoryError:
            print("警告: 模型加载内存不足（MemoryError），尝试下一备选")
            self.model = None
            return False
        except Exception as e:
            print(f"加载模型失败: {e}")
            self.model = None
            return False

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = None,
        show_progress: bool = False
    ) -> np.ndarray:
        """
        将文本编码为向量

        Args:
            texts: 单个文本或文本列表
            batch_size: 批处理大小
            show_progress: 是否显示进度

        Returns:
            numpy 数组形式的向量
        """
        if isinstance(texts, str):
            texts = [texts]

        batch_size = batch_size or self.batch_size

        # 如果模型未加载，使用备用方案
        if self.model is None:
            print("使用备用向量化方案（基于词袋）")
            return self._fallback_encode(texts)

        try:
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]

                # tokenize
                encoded = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt"
                )

                encoded = {k: v.to(self.device) for k, v in encoded.items()}

                # 前向传播
                with torch.no_grad():
                    outputs = self.model(**encoded)
                    # 使用 [CLS] token 的输出作为句子表示
                    embeddings = outputs.last_hidden_state[:, 0, :]

                # L2 归一化
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                all_embeddings.append(embeddings.cpu().numpy())

                if show_progress and (i // batch_size) % 10 == 0:
                    print(f"处理进度: {min(i + batch_size, len(texts))}/{len(texts)}")

            return np.vstack(all_embeddings)
        except Exception as e:
            print(f"向量化失败: {e}，使用备用方案")
            return self._fallback_encode(texts)

    def _fallback_encode(self, texts: List[str]) -> np.ndarray:
        """备用向量化方案（当模型加载失败时）"""
        # 简单的词袋 + 随机投影作为临时方案
        # 实际生产环境应该确保模型正确加载
        from sklearn.feature_extraction.text import HashingVectorizer

        vectorizer = HashingVectorizer(
            n_features=Config.EMBEDDING_DIMENSION,
            norm=None,
            alternate_sign=False
        )

        embeddings = vectorizer.transform(texts).toarray()

        # L2 归一化
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        embeddings = embeddings / norms

        return embeddings

    def similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            相似度分数 (0-1)
        """
        emb1 = self.encode(text1)
        emb2 = self.encode(text2)

        # 余弦相似度
        similarity = np.dot(emb1, emb2.T)[0, 0]
        return float(similarity)

    def similarities(self, query: str, texts: List[str]) -> List[float]:
        """
        计算查询与多个文本的相似度

        Args:
            query: 查询文本
            texts: 文本列表

        Returns:
            相似度分数列表
        """
        query_emb = self.encode(query)
        text_embs = self.encode(texts)

        # 余弦相似度
        similarities = np.dot(text_embs, query_emb.T).flatten()
        return similarities.tolist()

    def get_embedding_dimension(self) -> int:
        """获取向量维度"""
        if self.model is not None:
            return self.model.config.hidden_size
        return Config.EMBEDDING_DIMENSION

    @property
    def is_degraded(self) -> bool:
        """是否处于降级状态。

        模型未加载（词袋伪向量）或加载的是轻量备选模型（维度与主模型/
        库中索引不同）都视为降级：检索侧必须跳过向量路（改走 BM25 词法），
        否则查询向量与库中索引维度错配或语义空间不一致。
        轻量模型仍可用于相似度/语义重排（不依赖索引维度的场景）。
        """
        if self.model is None:
            return True
        return self.model_name != getattr(Config, "EMBEDDING_MODEL", self.model_name)


class EmbeddingService:
    """统一的向量化服务"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = None):
        if self._initialized:
            return

        self.model_name = model_name or Config.EMBEDDING_MODEL
        # 硅基流动 API 模式优先（免费 bge-m3，1024 维与本地一致，库无需重建）
        if Config.EMBEDDING_API_ENABLED and Config.EMBEDDING_API_KEY:
            from app.services.api_embedding import ApiEmbedding

            self.embedding_model = ApiEmbedding()
        else:
            self.embedding_model = SecBERTEmbedding(model_name=self.model_name)
        self._initialized = True

    def encode(self, texts: Union[str, List[str]], **kwargs) -> np.ndarray:
        """编码文本"""
        return self.embedding_model.encode(texts, **kwargs)

    def encode_query(self, query: str) -> np.ndarray:
        """编码查询文本（BGE 系模型追加查询指令，文档编码不加）"""
        prefix = Config.EMBEDDING_QUERY_PREFIX.strip()
        if prefix:
            query = f"{prefix}{query}"
        return self.encode(query)

    def encode_documents(self, documents: List[str], **kwargs) -> np.ndarray:
        """编码文档列表"""
        return self.encode(documents, **kwargs)

    def compute_similarity(self, query: str, documents: List[str]) -> List[float]:
        """计算查询与文档的相似度"""
        return self.embedding_model.similarities(query, documents)

    @property
    def dimension(self) -> int:
        """向量维度"""
        return self.embedding_model.get_embedding_dimension()

    @property
    def is_degraded(self) -> bool:
        """向量模型是否降级（词袋伪向量），检索侧应改走词法路。"""
        return self.embedding_model.is_degraded


# 全局单例
embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """获取向量化服务单例"""
    global embedding_service
    if embedding_service is None:
        embedding_service = EmbeddingService()
    return embedding_service


def encode_texts(texts: Union[str, List[str]], **kwargs) -> np.ndarray:
    """便捷的编码函数"""
    return get_embedding_service().encode(texts, **kwargs)


def compute_text_similarity(query: str, documents: List[str]) -> List[float]:
    """便捷的相似度计算函数"""
    return get_embedding_service().compute_similarity(query, documents)