"""
数据预处理和导入服务
将文档解析、文本分块、向量化存储、知识图谱构建串联起来
"""
import os
import json
import time
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.document_parser import (
    DocumentParserFactory,
    TextCleaner,
    parse_document,
    parse_documents_batch
)
from app.services.text_chunker import (
    TextChunker,
    HybridChunker,
    chunk_text,
    chunk_documents_batch
)
from app.services.vector_store import get_vector_store
from app.services.graph_store import get_knowledge_graph
from app.services.secbert_embedding import get_embedding_service


@dataclass
class ProcessingResult:
    """处理结果"""
    success: bool
    file_path: str
    chunks_created: int = 0
    error: str = ""
    processing_time: float = 0.0


@dataclass
class BatchProcessingResult:
    """批量处理结果"""
    total_files: int
    success_count: int
    failure_count: int
    total_chunks: int
    total_time: float
    errors: List[str]


class DataProcessor:
    """数据预处理和导入处理器"""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        batch_size: int = 32,
        language: str = "zh"
    ):
        """
        初始化数据处理器

        Args:
            chunk_size: 每个文本块的最大token数
            chunk_overlap: 相邻块之间的重叠token数
            batch_size: 批处理大小
            language: 语言 "zh" 或 "en"
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.batch_size = batch_size
        self.language = language

        # 初始化各组件
        self.document_parser = DocumentParserFactory()
        self.text_cleaner = TextCleaner()
        self.text_chunker = TextChunker(
            chunk_size=chunk_size,
            overlap=chunk_overlap,
            language=language
        )
        self.hybrid_chunker = HybridChunker(
            chunk_size=chunk_size,
            overlap=chunk_overlap,
            language=language
        )
        self.vector_store = None
        self.knowledge_graph = None
        self.embedding_service = None

    def _init_services(self):
        """延迟初始化服务"""
        if self.vector_store is None:
            self.vector_store = get_vector_store()
        if self.knowledge_graph is None:
            self.knowledge_graph = get_knowledge_graph()
        if self.embedding_service is None:
            self.embedding_service = get_embedding_service()

    def process_document(
        self,
        file_path: str,
        metadata: Dict[str, Any] = None,
        chunk_strategy: str = "smart",
        clean_text: bool = True
    ) -> ProcessingResult:
        """
        处理单个文档

        Args:
            file_path: 文件路径
            metadata: 元数据（会与解析出的元数据合并）
            chunk_strategy: 分块策略 "sentence", "paragraph", "smart"
            clean_text: 是否清洗文本

        Returns:
            ProcessingResult
        """
        start_time = time.time()
        metadata = metadata or {}

        try:
            # 1. 解析文档
            doc_result = parse_document(file_path, clean_text=clean_text)

            if not doc_result.get("content"):
                return ProcessingResult(
                    success=False,
                    file_path=file_path,
                    error="文档内容为空",
                    processing_time=time.time() - start_time
                )

            # 合并元数据
            combined_metadata = {**metadata, **doc_result.get("metadata", {})}
            combined_metadata["source"] = doc_result.get("source", os.path.basename(file_path))
            combined_metadata["format"] = doc_result.get("format", "")

            # 2. 文本分块
            doc_id = str(metadata.get("id", os.path.splitext(os.path.basename(file_path))[0]))
            chunks = chunk_text(
                text=doc_result["content"],
                doc_id=doc_id,
                metadata=combined_metadata,
                strategy=chunk_strategy
            )

            if not chunks:
                return ProcessingResult(
                    success=False,
                    file_path=file_path,
                    error="分块失败",
                    processing_time=time.time() - start_time
                )

            # 3. 添加到向量库
            self._init_services()
            vector_count = self.vector_store.add_documents_batch(chunks)

            # 4. 添加到知识图谱
            kg_node = {
                "id": doc_id,
                "title": combined_metadata.get("title", doc_result["source"]),
                "content": doc_result["content"][:500],
                "category": combined_metadata.get("category", ""),
                "tags": combined_metadata.get("tags", [])
            }
            self.knowledge_graph.add_entities_from_knowledge([kg_node])

            return ProcessingResult(
                success=True,
                file_path=file_path,
                chunks_created=len(chunks),
                processing_time=time.time() - start_time
            )

        except FileNotFoundError as e:
            return ProcessingResult(
                success=False,
                file_path=file_path,
                error=f"文件不存在: {e}",
                processing_time=time.time() - start_time
            )
        except ValueError as e:
            return ProcessingResult(
                success=False,
                file_path=file_path,
                error=f"不支持的文件格式: {e}",
                processing_time=time.time() - start_time
            )
        except Exception as e:
            return ProcessingResult(
                success=False,
                file_path=file_path,
                error=f"处理失败: {str(e)}",
                processing_time=time.time() - start_time
            )

    def process_directory(
        self,
        directory: str,
        recursive: bool = True,
        file_extensions: List[str] = None,
        chunk_strategy: str = "smart",
        max_workers: int = 4
    ) -> BatchProcessingResult:
        """
        批量处理目录中的文档

        Args:
            directory: 目录路径
            recursive: 是否递归处理子目录
            file_extensions: 限定的文件扩展名，如 [".pdf", ".docx"]
            chunk_strategy: 分块策略
            max_workers: 最大并行工作线程数

        Returns:
            BatchProcessingResult
        """
        file_extensions = file_extensions or [".pdf", ".docx", ".doc", ".html", ".htm", ".md", ".txt"]

        # 收集文件
        dir_path = Path(directory)
        if not dir_path.exists():
            return BatchProcessingResult(
                total_files=0,
                success_count=0,
                failure_count=0,
                total_chunks=0,
                total_time=0.0,
                errors=[f"目录不存在: {directory}"]
            )

        files = []
        if recursive:
            for ext in file_extensions:
                files.extend(dir_path.rglob(f"*{ext}"))
        else:
            for ext in file_extensions:
                files.extend(dir_path.glob(f"*{ext}"))

        if not files:
            return BatchProcessingResult(
                total_files=0,
                success_count=0,
                failure_count=0,
                total_chunks=0,
                total_time=0.0,
                errors=[f"目录中没有找到支持的文件: {directory}"]
            )

        start_time = time.time()
        results = []
        errors = []

        # 并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(
                    self.process_document,
                    str(file_path),
                    {"source": str(file_path.relative_to(dir_path))},
                    chunk_strategy
                ): file_path
                for file_path in files
            }

            for future in as_completed(future_to_file):
                result = future.result()
                results.append(result)
                if not result.success:
                    errors.append(f"{result.file_path}: {result.error}")

        # 统计结果
        success_results = [r for r in results if r.success]
        return BatchProcessingResult(
            total_files=len(files),
            success_count=len(success_results),
            failure_count=len(results) - len(success_results),
            total_chunks=sum(r.chunks_created for r in success_results),
            total_time=time.time() - start_time,
            errors=errors
        )

    def import_knowledge_items(
        self,
        items: List[Dict[str, Any]],
        chunk_strategy: str = "smart"
    ) -> Dict[str, int]:
        """
        导入知识条目（数据库中的知识）

        Args:
            items: 知识条目列表，每项包含 id, title, content, category 等
            chunk_strategy: 分块策略

        Returns:
            导入统计
        """
        self._init_services()

        # 批量分块
        chunks = chunk_documents_batch(
            [{"id": item["id"], "text": f"{item['title']}。{item.get('content', '')}", "metadata": item}
             for item in items],
            strategy=chunk_strategy
        )

        # 添加到向量库
        vector_count = self.vector_store.add_documents_batch(chunks)

        # 添加到知识图谱
        graph_count = self.knowledge_graph.add_entities_from_knowledge(items)

        return {
            "total_items": len(items),
            "chunks_created": len(chunks),
            "vectors_indexed": vector_count,
            "graph_nodes": graph_count
        }


class KnowledgeGraphBuilder:
    """知识图谱构建器 - 从文本中抽取实体和关系"""

    def __init__(self):
        self.knowledge_graph = None
        self.embedding_service = None

    def _init_services(self):
        if self.knowledge_graph is None:
            self.knowledge_graph = get_knowledge_graph()
        if self.embedding_service is None:
            self.embedding_service = get_embedding_service()

    def extract_entities(
        self,
        text: str,
        entity_types: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        从文本中抽取实体（使用基于规则的方法）

        Args:
            text: 输入文本
            entity_types: 要抽取的实体类型列表

        Returns:
            实体列表 [{"type": str, "name": str, "start": int, "end": int}, ...]
        """
        entity_types = entity_types or ["concept", "technique", "tool", "vulnerability"]

        import re

        # 网络安全相关的正则模式
        patterns = {
            "technique": [
                r'(SQL注入|XSS|跨站脚本|CSRF|跨站请求伪造|SSRF|远程代码执行|RCE|文件上传|webshell|反弹shell)',
                r'(暴力破解|社工|钓鱼|嗅探|ARP欺骗|DNS劫持|DoS|DDoS|中间人攻击)',
                r'(提权|权限维持|内网渗透|横向移动|信息收集|端口扫描)'
            ],
            "vulnerability": [
                r'(缓冲区溢出|栈溢出|堆溢出|格式化字符串|空指针|越界访问)',
                r'(注入漏洞|文件包含|代码执行|命令执行|路径遍历)'
            ],
            "tool": [
                r'(Nmap|Metasploit|Burp Suite|SQLMap|OWASP ZAP|Nessus|Acunetix)',
                r'(Wireshark|tcpdump|hydra|john|hashcat|AWVS|Nmap)'
            ],
            "concept": [
                r'(TCP|IP|UDP|HTTP|HTTPS|DNS|DHCP|ARP|ICMP|SMTP|POP3|IMAP)',
                r'(加密|解密|哈希|签名|证书|公钥|私钥|对称加密|非对称加密)',
                r'(防火墙|IDS|IPS|WAF|VPN|堡垒机|安全审计)'
            ]
        }

        entities = []
        for entity_type, type_patterns in patterns.items():
            if entity_types and entity_type not in entity_types:
                continue

            for pattern in type_patterns:
                for match in re.finditer(pattern, text):
                    entities.append({
                        "type": entity_type,
                        "name": match.group(),
                        "start": match.start(),
                        "end": match.end()
                    })

        # 去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e["type"], e["name"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        return unique_entities

    def build_relations_from_entities(
        self,
        text: str,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        从实体列表中推断关系

        Args:
            text: 原始文本
            entities: 实体列表

        Returns:
            关系列表 [{"source": str, "target": str, "type": str}, ...]
        """
        import re

        relations = []

        # 获取所有实体名称（去重）
        entity_names = list(set(e["name"] for e in entities))

        # 策略: 基于共现的关系 - 同一知识条目中的实体认为它们有关系
        if len(entity_names) >= 2:
            # 按类型分组
            entities_by_type = {}
            for e in entities:
                if e["name"] not in entities_by_type:
                    entities_by_type[e["name"]] = e["type"]

            # 实体两两之间建立关系（限制最多10个关系避免过于密集）
            max_relations = 10
            count = 0
            for i, source in enumerate(entity_names):
                if count >= max_relations:
                    break
                for target in entity_names[i+1:]:
                    if count >= max_relations:
                        break
                    source_type = entities_by_type.get(source, "concept")
                    target_type = entities_by_type.get(target, "concept")

                    # 确定关系类型
                    if source_type == target_type:
                        rel_type = "related_to"
                    elif source_type == "technique" or target_type == "technique":
                        rel_type = "uses"
                    else:
                        rel_type = "related_to"

                    relations.append({
                        "source": source,
                        "target": target,
                        "type": rel_type
                    })
                    count += 1

        return relations

    def build_knowledge_graph(
        self,
        knowledge_items: List[Dict[str, Any]],
        build_relations: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        从知识条目构建知识图谱

        Args:
            knowledge_items: 知识条目列表
            build_relations: 是否构建实体关系
            progress_callback: 可选进度回调 (processed, total)，每处理一个条目调用一次

        Returns:
            构建统计
        """
        self._init_services()

        # 初始化分块器
        chunker = TextChunker(chunk_size=256, overlap=30)

        nodes_added = 0
        edges_added = 0

        # 跨条目同名实体分组（实体消歧：同名同类型实体建立关联边）
        entities_by_name: Dict[Tuple[str, str], List[str]] = {}

        total_items = len(knowledge_items)
        for item_index, item in enumerate(knowledge_items, start=1):
            item_id = str(item["id"])
            title = item.get("title", "")
            content = item.get("content", "")

            # 添加知识节点
            self.knowledge_graph.add_knowledge_node(
                knowledge_id=item_id,
                title=title,
                content=content[:500],
                category=item.get("category") or item.get("category_name") or "",
                tags=item.get("tags", [])
            )
            nodes_added += 1

            if not content:
                continue

            # 先对内容进行语义分块
            chunks = chunker.chunk_document(content, item_id, metadata={"title": title})
            print(f"[DEBUG] Item {item_id} '{title}': {len(chunks)} chunks")

            # 收集所有实体（去重）
            all_entity_names = set()

            # 对每个块分别提取实体并建立关系
            for chunk in chunks:
                # chunk 可以是 TextChunk 对象或字典
                if hasattr(chunk, 'text'):
                    chunk_text = chunk.text
                    chunk_id = chunk.id
                else:
                    chunk_text = chunk.get("text", "")
                    chunk_id = chunk.get("id", "")

                if not chunk_text:
                    continue

                # 从当前块提取实体
                entities = self.extract_entities(chunk_text)

                # 建立知识与实体的关系
                for entity in entities:
                    entity_id = f"{item_id}_{entity['name']}"
                    all_entity_names.add(entity["name"])

                    # 记录同名实体（跨条目时用于建立关联边）
                    entity_key = (entity["type"], entity["name"])
                    if entity_key not in entities_by_name:
                        entities_by_name[entity_key] = []
                    if entity_id not in entities_by_name[entity_key]:
                        entities_by_name[entity_key].append(entity_id)

                    # 添加实体节点
                    self.knowledge_graph.add_entity(
                        entity_id=entity_id,
                        name=entity["name"],
                        entity_type=entity["type"],
                        properties={"source_item": item_id, "chunk_id": chunk_id}
                    )
                    nodes_added += 1

                    # 建立知识与实体的关系
                    self.knowledge_graph.add_relation(
                        source_id=item_id,
                        target_id=entity_id,
                        relation_type="contains"
                    )
                    edges_added += 1

                # 在同一块内的实体之间建立关系
                if build_relations and len(entities) >= 2:
                    relations = self.build_relations_from_entities(chunk_text, entities)
                    for rel in relations:
                        source_entity_id = f"{item_id}_{rel['source']}"
                        target_entity_id = f"{item_id}_{rel['target']}"

                        self.knowledge_graph.add_relation(
                            source_id=source_entity_id,
                            target_id=target_entity_id,
                            relation_type=rel["type"]
                        )
                        edges_added += 1

            print(f"[DEBUG] Item {item_id}: {len(all_entity_names)} unique entities")

            # 进度回调（每处理完一个条目调用一次）
            if progress_callback is not None:
                progress_callback(item_index, total_items)

        # 跨条目同名实体关联：同名实体在不同知识条目中互相关联（related_to）
        cross_item_edges = 0
        for (entity_type, entity_name), entity_ids in entities_by_name.items():
            if len(entity_ids) < 2:
                continue
            for index in range(len(entity_ids) - 1):
                self.knowledge_graph.add_relation(
                    source_id=entity_ids[index],
                    target_id=entity_ids[index + 1],
                    relation_type="related_to"
                )
                cross_item_edges += 1

        return {
            "nodes_added": nodes_added,
            "edges_added": edges_added,
            "cross_item_edges": cross_item_edges,
            "items_processed": len(knowledge_items)
        }


# 全局处理器实例
data_processor = None

def get_data_processor() -> DataProcessor:
    global data_processor
    if data_processor is None:
        data_processor = DataProcessor()
    return data_processor

def get_kg_builder() -> KnowledgeGraphBuilder:
    return KnowledgeGraphBuilder()


# 便捷函数
def process_document(file_path: str, **kwargs) -> ProcessingResult:
    """处理单个文档"""
    return get_data_processor().process_document(file_path, **kwargs)

def process_directory(directory: str, **kwargs) -> BatchProcessingResult:
    """批量处理目录"""
    return get_data_processor().process_directory(directory, **kwargs)

def import_knowledge(items: List[Dict[str, Any]], **kwargs) -> Dict[str, int]:
    """导入知识条目"""
    return get_data_processor().import_knowledge_items(items, **kwargs)

def build_knowledge_graph(items: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    """构建知识图谱"""
    return get_kg_builder().build_knowledge_graph(items, **kwargs)