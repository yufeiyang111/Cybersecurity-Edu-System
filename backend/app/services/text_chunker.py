"""
基于 spaCy 的文本语义分块服务
将长文本切割为语义完整的文本片段
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# spaCy 相关
try:
    import spacy
    from spacy.language import Language
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# 中文分词
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


@dataclass
class TextChunk:
    """文本块数据结构"""
    id: str
    text: str
    start_char: int
    end_char: int
    start_token: int
    end_token: int
    metadata: Dict[str, Any]


class TextChunker:
    """基于语义的文本分块器"""

    def __init__(
        self,
        model_name: str = "zh_core_web_sm",
        chunk_size: int = 512,
        overlap: int = 50,
        language: str = "zh"
    ):
        """
        初始化分块器

        Args:
            model_name: spaCy 模型名称
            chunk_size: 每个块的最大token数
            overlap: 相邻块之间的重叠token数
            language: 语言类型 "zh" 或 "en"
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.language = language
        self.nlp = None
        self.model_name = model_name

        if SPACY_AVAILABLE:
            self._load_model()

    def _load_model(self):
        """加载 spaCy 模型"""
        try:
            if spacy.util.is_package(self.model_name):
                self.nlp = spacy.load(self.model_name)
            else:
                # 尝试加载中文模型
                if self.language == "zh":
                    # 尝试多个可能的中文模型名
                    for model_name in ["zh_core_web_sm", "zh_core_web_md", "zh_core_web_lg"]:
                        try:
                            self.nlp = spacy.load(model_name)
                            print(f"成功加载 spaCy 模型: {model_name}")
                            return
                        except Exception:
                            continue
                else:
                    try:
                        self.nlp = spacy.load("en_core_web_sm")
                    except Exception:
                        pass
            if self.nlp is None:
                print("警告: spaCy 模型不可用，将使用简单的分句方法")
        except Exception as e:
            print(f"加载 spaCy 模型失败: {e}")
            self.nlp = None

    def count_tokens(self, text: str) -> int:
        """估算token数量（简单按字符计）"""
        if self.language == "zh":
            # 中文：大致按字符数估算，1 token ≈ 1-2 个中文字符
            return len(text) // 2
        else:
            # 英文：按单词数估算
            return len(text.split())

    def chunk_by_sentence(self, text: str, metadata: Dict[str, Any] = None) -> List[TextChunk]:
        """
        按句子分块（使用 spaCy sentencizer）

        Args:
            text: 待分块文本
            metadata: 元数据

        Returns:
            TextChunk 列表
        """
        metadata = metadata or {}
        chunks = []

        if not text or not text.strip():
            return chunks

        if self.nlp is None:
            # 无 spaCy 模型，使用简单分句
            return self._chunk_by_simple_sentence(text, metadata)

        # 使用 spaCy 分句
        doc = self.nlp(text)

        current_chunk_texts = []
        current_tokens = 0
        current_start_char = 0
        chunk_id_prefix = metadata.get("chunk_id_prefix", "chunk")

        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue

            sent_tokens = self.count_tokens(sent_text)

            # 如果单个句子超过 chunk_size，尝试进一步分块
            if sent_tokens > self.chunk_size:
                if current_chunk_texts:
                    # 先保存当前的块
                    chunks.append(self._create_chunk(
                        chunks=current_chunk_texts,
                        start_char=current_start_char,
                        end_char=sent.start_char,
                        metadata=metadata,
                        chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
                    ))
                    current_chunk_texts = []
                    current_tokens = 0

                # 对长句子进行进一步分块
                sub_chunks = self._chunk_long_sentence(sent.text, sent.start_char, metadata, chunk_id_prefix, len(chunks))
                chunks.extend(sub_chunks)
                current_start_char = sent.end_char
                continue

            # 检查添加当前句子是否会超过限制
            if current_tokens + sent_tokens > self.chunk_size and current_chunk_texts:
                # 保存当前块
                chunks.append(self._create_chunk(
                    chunks=current_chunk_texts,
                    start_char=current_start_char,
                    end_char=sent.start_char,
                    metadata=metadata,
                    chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
                ))

                # 处理重叠
                overlap_texts = self._get_overlap_texts(current_chunk_texts)
                current_chunk_texts = overlap_texts
                current_tokens = self.count_tokens(" ".join(overlap_texts))
                current_start_char = sent.start_char - sum(len(t) for t in overlap_texts) - 1

            current_chunk_texts.append(sent_text)
            current_tokens += sent_tokens

        # 保存最后一个块
        if current_chunk_texts:
            chunks.append(self._create_chunk(
                chunks=current_chunk_texts,
                start_char=current_start_char,
                end_char=len(text),
                metadata=metadata,
                chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
            ))

        return chunks

    def _chunk_by_simple_sentence(self, text: str, metadata: Dict[str, Any]) -> List[TextChunk]:
        """使用简单规则进行分句"""
        chunks = []

        # 按常见句子结束符分句
        sentence_endings = r'[。！？\n]+'
        sentences = re.split(sentence_endings, text)

        current_chunk_texts = []
        current_tokens = 0
        chunk_id_prefix = metadata.get("chunk_id_prefix", "chunk")

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue

            sent_tokens = self.count_tokens(sent)

            if current_tokens + sent_tokens > self.chunk_size and current_chunk_texts:
                chunks.append(self._create_chunk(
                    chunks=current_chunk_texts,
                    start_char=0,  # 简化处理
                    end_char=len(" ".join(current_chunk_texts)),
                    metadata=metadata,
                    chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
                ))

                # 简单重叠处理
                overlap_size = max(1, len(current_chunk_texts) // 3)
                current_chunk_texts = current_chunk_texts[-overlap_size:]
                current_tokens = sum(self.count_tokens(t) for t in current_chunk_texts)

            current_chunk_texts.append(sent)
            current_tokens += sent_tokens

        if current_chunk_texts:
            chunks.append(self._create_chunk(
                chunks=current_chunk_texts,
                start_char=0,
                end_char=len(text),
                metadata=metadata,
                chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
            ))

        return chunks

    def _chunk_long_sentence(
        self,
        text: str,
        start_char: int,
        metadata: Dict[str, Any],
        chunk_id_prefix: str,
        existing_count: int
    ) -> List[TextChunk]:
        """对长句子进一步分块"""
        chunks = []

        if self.language == "zh":
            # 使用 jieba 进行分词后再组句
            if JIEBA_AVAILABLE:
                words = list(jieba.cut(text))
            else:
                words = list(text)
        else:
            words = text.split()

        current_words = []
        current_tokens = 0

        for word in words:
            word_tokens = self.count_tokens(word)

            if current_tokens + word_tokens > self.chunk_size and current_words:
                chunk_text = "".join(current_words) if self.language == "zh" else " ".join(current_words)
                chunks.append(TextChunk(
                    id=f"{chunk_id_prefix}_{existing_count + len(chunks)}",
                    text=chunk_text,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    start_token=0,
                    end_token=current_tokens,
                    metadata=metadata.copy()
                ))

                # 重叠
                overlap_size = max(1, len(current_words) // 5)
                current_words = current_words[-overlap_size:]
                current_tokens = sum(self.count_tokens(w) for w in current_words)
                start_char = start_char + len(chunk_text) - sum(len(w) for w in current_words)

            current_words.append(word)
            current_tokens += word_tokens

        # 处理剩余部分
        if current_words:
            chunk_text = "".join(current_words) if self.language == "zh" else " ".join(current_words)
            chunks.append(TextChunk(
                id=f"{chunk_id_prefix}_{existing_count + len(chunks)}",
                text=chunk_text,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                start_token=0,
                end_token=current_tokens,
                metadata=metadata.copy()
            ))

        return chunks

    def _get_overlap_texts(self, texts: List[str]) -> List[str]:
        """获取重叠的文本"""
        if len(texts) <= 2:
            return texts[-1:] if texts else []

        last_token_count = self.count_tokens(texts[-1])
        if last_token_count == 0:
            return texts[-1:] if texts else []

        overlap_count = max(1, self.overlap // last_token_count)
        return texts[-overlap_count:]

    def _create_chunk(
        self,
        chunks: List[str],
        start_char: int,
        end_char: int,
        metadata: Dict[str, Any],
        chunk_id: str
    ) -> TextChunk:
        """创建 TextChunk 对象"""
        separator = "" if self.language == "zh" else " "
        text = separator.join(chunks)

        return TextChunk(
            id=chunk_id,
            text=text,
            start_char=start_char,
            end_char=end_char,
            start_token=0,
            end_token=self.count_tokens(text),
            metadata={
                **metadata,
                "char_length": len(text),
                "token_count": self.count_tokens(text)
            }
        )

    def chunk_document(
        self,
        text: str,
        doc_id: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        对文档进行分块

        Args:
            text: 文档文本
            doc_id: 文档ID
            metadata: 文档元数据

        Returns:
            分块结果列表
        """
        metadata = metadata or {}
        metadata["doc_id"] = doc_id
        metadata["chunk_id_prefix"] = f"doc_{doc_id}_chunk"

        chunks = self.chunk_by_sentence(text, metadata)

        return [
            {
                "id": chunk.id,
                "text": chunk.text,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "metadata": {
                    **chunk.metadata,
                    "doc_id": doc_id,
                    "source": metadata.get("source", ""),
                    "title": metadata.get("title", ""),
                    "category": metadata.get("category", "")
                }
            }
            for chunk in chunks
        ]


class HybridChunker:
    """混合分块器：结合多种策略"""

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 50,
        language: str = "zh"
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.language = language

        # 初始化各种分块器
        self.sentence_chunker = TextChunker(
            chunk_size=chunk_size,
            overlap=overlap,
            language=language
        )

    def chunk_by_paragraph(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """按段落分块"""
        metadata = metadata or {}

        # 按换行分割段落
        if self.language == "zh":
            paragraphs = re.split(r'\n{2,}', text)
        else:
            paragraphs = re.split(r'\n{2,}', text)

        chunks = []
        chunk_id_prefix = metadata.get("chunk_id_prefix", "chunk")

        current_paragraphs = []
        current_size = 0

        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue

            para_tokens = len(para) // 2 if self.language == "zh" else len(para.split())

            if current_size + para_tokens > self.chunk_size and current_paragraphs:
                chunk_text = "\n\n".join(current_paragraphs)
                chunks.append({
                    "id": f"{chunk_id_prefix}_{len(chunks)}",
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "paragraph_indices": [j for j in range(len(chunks), len(chunks) + len(current_paragraphs))]
                    }
                })

                # 重叠
                overlap_size = max(1, len(current_paragraphs) // 3)
                current_paragraphs = current_paragraphs[-overlap_size:]
                current_size = sum(len(p) // 2 for p in current_paragraphs) if self.language == "zh" else sum(len(p.split()) for p in current_paragraphs)

            current_paragraphs.append(para)
            current_size += para_tokens

        if current_paragraphs:
            chunk_text = "\n\n".join(current_paragraphs)
            chunks.append({
                "id": f"{chunk_id_prefix}_{len(chunks)}",
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "paragraph_indices": list(range(len(chunks), len(chunks) + len(current_paragraphs)))
                }
            })

        return chunks

    def smart_chunk(self, text: str, doc_id: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        智能分块：优先按段落，在段落过长时按句子

        Args:
            text: 文档文本
            doc_id: 文档ID
            metadata: 元数据

        Returns:
            分块结果
        """
        metadata = metadata or {}
        metadata["doc_id"] = doc_id

        # 先尝试按段落分块
        para_chunks = self.chunk_by_paragraph(text, {**metadata, "chunk_id_prefix": f"doc_{doc_id}_para"})

        final_chunks = []

        for chunk in para_chunks:
            chunk_tokens = len(chunk["text"]) // 2 if self.language == "zh" else len(chunk["text"].split())

            # 如果段落过长，使用句子分块器进一步处理
            if chunk_tokens > self.chunk_size * 1.5:
                sub_chunks = self.sentence_chunker.chunk_document(
                    chunk["text"],
                    chunk["id"],
                    {**metadata, "parent_chunk": chunk["id"]}
                )
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)

        return final_chunks


# 全局实例
text_chunker = TextChunker()
hybrid_chunker = HybridChunker()


def chunk_text(text: str, doc_id: str, metadata: Dict[str, Any] = None, strategy: str = "smart") -> List[Dict[str, Any]]:
    """
    便捷的分块函数

    Args:
        text: 待分块文本
        doc_id: 文档ID
        metadata: 元数据
        strategy: 分块策略 "sentence", "paragraph", "smart"

    Returns:
        分块结果列表
    """
    if strategy == "sentence":
        return text_chunker.chunk_document(text, doc_id, metadata)
    elif strategy == "paragraph":
        return hybrid_chunker.chunk_by_paragraph(text, {**(metadata or {}), "doc_id": doc_id})
    else:  # smart
        return hybrid_chunker.smart_chunk(text, doc_id, metadata)


def chunk_documents_batch(
    documents: List[Dict[str, Any]],
    strategy: str = "smart"
) -> List[Dict[str, Any]]:
    """
    批量分块

    Args:
        documents: [{"id": str, "text": str, "metadata": dict}, ...]
        strategy: 分块策略

    Returns:
        所有文档的分块结果
    """
    all_chunks = []

    for doc in documents:
        chunks = chunk_text(
            text=doc["text"],
            doc_id=str(doc["id"]),
            metadata=doc.get("metadata"),
            strategy=strategy
        )
        all_chunks.extend(chunks)

    return all_chunks