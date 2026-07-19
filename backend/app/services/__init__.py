"""
Services 模块
提供文档解析、文本分块、向量化、图谱存储、RAG引擎等服务
"""

# 文档解析服务
from app.services.document_parser import (
    DocumentParserFactory,
    TextCleaner,
    parse_document,
    parse_documents_batch,
    PDFParser,
    DocxParser,
    HTMLParser,
    MarkdownParser,
    TextParser
)

# 文本分块服务
from app.services.text_chunker import (
    TextChunker,
    HybridChunker,
    chunk_text,
    chunk_documents_batch,
    TextChunk
)

# 向量化服务 (SecBERT)
from app.services.secbert_embedding import (
    SecBERTEmbedding,
    EmbeddingService,
    get_embedding_service,
    encode_texts,
    compute_text_similarity
)

# 向量存储服务
from app.services.vector_store import VectorStore, get_vector_store

# Neo4j 知识图谱服务
from app.services.neo4j_graph import (
    Neo4jKnowledgeGraph,
    Neo4jConfig,
    get_neo4j_graph,
    NEO4J_AVAILABLE
)

# NetworkX 知识图谱服务 (兼容层)
from app.services.graph_store import KnowledgeGraph, get_knowledge_graph

# RAG 引擎
from app.services.enhanced_rag_engine import (
    EnhancedRAGEngine,
    Reranker,
    get_enhanced_rag_engine,
    get_rag_engine
)

# MiniMax LLM
from app.services.minimax_llm import (
    MiniMaxLLM,
    get_minimax_llm,
    generate_with_minimax,
    chat_with_minimax
)

# 数据处理和导入
from app.services.data_processor import (
    DataProcessor,
    KnowledgeGraphBuilder,
    ProcessingResult,
    BatchProcessingResult,
    get_data_processor,
    get_kg_builder,
    process_document,
    process_directory,
    import_knowledge,
    build_knowledge_graph
)

__all__ = [
    # 文档解析
    "DocumentParserFactory",
    "TextCleaner",
    "parse_document",
    "parse_documents_batch",

    # 文本分块
    "TextChunker",
    "HybridChunker",
    "chunk_text",
    "chunk_documents_batch",
    "TextChunk",

    # 向量化
    "SecBERTEmbedding",
    "EmbeddingService",
    "get_embedding_service",
    "encode_texts",
    "compute_text_similarity",

    # 向量存储
    "VectorStore",
    "get_vector_store",

    # 知识图谱
    "Neo4jKnowledgeGraph",
    "Neo4jConfig",
    "get_neo4j_graph",
    "NEO4J_AVAILABLE",
    "KnowledgeGraph",
    "get_knowledge_graph",

    # RAG 引擎
    "EnhancedRAGEngine",
    "Reranker",
    "get_enhanced_rag_engine",
    "get_rag_engine",

    # 数据处理
    "DataProcessor",
    "KnowledgeGraphBuilder",
    "ProcessingResult",
    "BatchProcessingResult",
    "get_data_processor",
    "get_kg_builder",
    "process_document",
    "process_directory",
    "import_knowledge",
    "build_knowledge_graph"
]