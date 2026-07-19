"""
RAG核心引擎 - 检索增强生成
融合向量检索和知识图谱检索

此文件已重构为 EnhancedRAGEngine 的兼容包装
实际实现请参见 enhanced_rag_engine.py
"""
# 导入增强版引擎保持向后兼容
from app.services.enhanced_rag_engine import (
    EnhancedRAGEngine,
    get_rag_engine as get_enhanced_rag_engine,
    Reranker
)

# 为了向后兼容，保留原有类名
RAGEngine = EnhancedRAGEngine

# 全局单例 - 指向增强版
rag_engine = None

def get_rag_engine():
    """获取 RAG 引擎单例（使用增强版）"""
    global rag_engine
    if rag_engine is None:
        rag_engine = EnhancedRAGEngine()
    return rag_engine
