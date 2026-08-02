"""
向量数据库服务兼容入口。

真实实现已迁移到 app.services.vector_stores 包（协议 + Chroma/Qdrant 双后端）。
此文件保留原导入路径 `from app.services.vector_store import get_vector_store`，
避免改动调用方。
"""
from app.services.vector_stores.legacy import VectorStore, get_vector_store, vector_store
from app.services.vector_stores.factory import get_vector_backend

__all__ = ["VectorStore", "vector_store", "get_vector_store", "get_vector_backend"]
