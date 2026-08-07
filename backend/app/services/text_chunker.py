"""
基于语义的文本分块服务
将长文本切割为语义完整的文本片段，支持真实 tokenizer 计数、行号定位与标题路径元数据。

设计要点（对齐工业级 RAG 分块实践）：
- token 计数使用 embedding 模型同款 AutoTokenizer（精确），加载失败降级为字符估算；
- 块携带 start_line/end_line，支持输出引用精确到行；
- 支持 title_path（标题层级），为结构化检索/父子窗口预留元数据。
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

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
    start_line: int = 0
    end_line: int = 0


class TextChunker:
    """基于语义的文本分块器"""

    def __init__(
        self,
        model_name: str = None,
        chunk_size: int = 384,
        overlap: int = 50,
        language: str = "zh"
    ):
        """
        初始化分块器

        Args:
            model_name: tokenizer 模型名或本地路径（与 embedding 模型一致）
            chunk_size: 每个块的最大 token 数
            overlap: 相邻块之间的重叠 token 数
            language: 语言类型 "zh" 或 "en"
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.language = language
        self.nlp = None
        self.model_name = model_name
        self._tokenizer = None
        self._tokenizer_failed = False

        if SPACY_AVAILABLE:
            self._load_model()

    def _load_model(self):
        """加载 spaCy 模型"""
        if not self.model_name:
            print("警告: 未配置 spaCy 模型名，将使用简单的分句方法")
            return
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

    def _get_tokenizer(self):
        """懒加载与 embedding 模型同款的 tokenizer（真实计数）。"""
        if self._tokenizer is not None or self._tokenizer_failed:
            return self._tokenizer
        try:
            from transformers import AutoTokenizer
            from app.config import Config

            model_name = self.model_name or Config.EMBEDDING_MODEL
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        except Exception as e:
            print(f"加载 tokenizer 失败，降级为字符估算: {e}")
            self._tokenizer_failed = True
        return self._tokenizer

    def count_tokens(self, text: str) -> int:
        """估算 token 数量（优先真实 tokenizer，降级字符估算）。"""
        tokenizer = self._get_tokenizer()
        if tokenizer is not None:
            try:
                return len(tokenizer.encode(text, add_special_tokens=False))
            except Exception:
                pass
        if self.language == "zh":
            return len(text) // 2
        return len(text.split())

    def _line_starts(self, text: str) -> List[int]:
        """构建行起始字符偏移数组（第 i 行从 starts[i] 开始，1-based 行号）。"""
        starts = [0]
        for index, char in enumerate(text):
            if char == "\n":
                starts.append(index + 1)
        return starts

    def _char_to_line(self, starts: List[int], char_pos: int) -> int:
        """把字符位置映射为 1-based 行号。"""
        lo, hi = 0, len(starts)
        while lo < hi:
            mid = (lo + hi) // 2
            if starts[mid] <= char_pos:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def chunk_by_sentence(
        self,
        text: str,
        metadata: Dict[str, Any] = None,
        char_offset: int = 0,
        line_starts: List[int] = None
    ) -> List[TextChunk]:
        """
        按句子分块（使用 spaCy sentencizer，降级正则分句）

        Args:
            text: 待分块文本
            metadata: 元数据
            char_offset: 子文本在整文档中的字符偏移（默认 0）
            line_starts: 整文档行起始数组（缺省用子文本计算）

        Returns:
            TextChunk 列表
        """
        metadata = metadata or {}
        chunks: List[TextChunk] = []
        line_starts = line_starts or self._line_starts(text)

        if not text or not text.strip():
            return chunks

        if self.nlp is None:
            return self._chunk_by_simple_sentence(text, metadata, line_starts, char_offset)

        doc = self.nlp(text)

        current_chunk_texts: List[str] = []
        current_tokens = 0
        current_start_char = 0
        chunk_id_prefix = metadata.get("chunk_id_prefix", "chunk")

        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue

            sent_tokens = self.count_tokens(sent_text)

            # 单个句子超过 chunk_size，进一步分块
            if sent_tokens > self.chunk_size:
                if current_chunk_texts:
                    chunks.append(self._create_chunk(
                        text=text,
                        chunks=current_chunk_texts,
                        start_char=current_start_char + char_offset,
                        end_char=sent.start_char + char_offset,
                        line_starts=line_starts,
                        metadata=metadata,
                        chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
                    ))
                    current_chunk_texts = []
                    current_tokens = 0

                sub_chunks = self._chunk_long_sentence(
                    text=text,
                    sent_text=sent.text,
                    start_char=sent.start_char + char_offset,
                    line_starts=line_starts,
                    metadata=metadata,
                    chunk_id_prefix=chunk_id_prefix,
                    existing_count=len(chunks)
                )
                chunks.extend(sub_chunks)
                current_start_char = sent.end_char
                continue

            if current_tokens + sent_tokens > self.chunk_size and current_chunk_texts:
                chunks.append(self._create_chunk(
                    text=text,
                    chunks=current_chunk_texts,
                    start_char=current_start_char + char_offset,
                    end_char=sent.start_char + char_offset,
                    line_starts=line_starts,
                    metadata=metadata,
                    chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
                ))

                # 重叠：从尾部句子累积，直到达到目标 overlap token 数
                overlap_texts = self._get_overlap_texts(current_chunk_texts)
                current_chunk_texts = overlap_texts
                current_tokens = self.count_tokens(_join_texts(overlap_texts, self.language))
                if current_chunk_texts:
                    joined = _join_texts(current_chunk_texts, self.language)
                    current_start_char = sent.start_char - len(joined)

            current_chunk_texts.append(sent_text)
            current_tokens += sent_tokens

        if current_chunk_texts:
            chunks.append(self._create_chunk(
                text=text,
                chunks=current_chunk_texts,
                start_char=current_start_char + char_offset,
                end_char=len(text) + char_offset,
                line_starts=line_starts,
                metadata=metadata,
                chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
            ))

        return chunks

    def _chunk_by_simple_sentence(
        self,
        text: str,
        metadata: Dict[str, Any],
        line_starts: List[int],
        char_offset: int = 0
    ) -> List[TextChunk]:
        """使用简单规则进行分句（保留分隔符，字符定位精确）"""
        chunks: List[TextChunk] = []

        # 按常见句子结束符分句，保留分隔符以精确累计字符偏移
        parts = re.split(r'([。！？\n]+)', text)
        sentences_with_pos: List[Tuple[str, int]] = []
        cursor = 0
        index = 0
        while index < len(parts):
            seg = parts[index]
            if seg:
                sentences_with_pos.append((seg, cursor))
            cursor += len(seg)
            if index + 1 < len(parts):
                cursor += len(parts[index + 1])
            index += 2

        current_chunk_texts: List[str] = []
        current_tokens = 0
        current_start_char = 0
        chunk_id_prefix = metadata.get("chunk_id_prefix", "chunk")

        for sent_text, sent_start in sentences_with_pos:
            sent = sent_text.strip()
            if not sent:
                continue

            sent_tokens = self.count_tokens(sent)

            if current_tokens + sent_tokens > self.chunk_size and current_chunk_texts:
                chunk_text = _join_texts(current_chunk_texts, self.language)
                chunks.append(self._create_chunk(
                    text=text,
                    chunks=current_chunk_texts,
                    start_char=current_start_char + char_offset,
                    end_char=current_start_char + len(chunk_text) + char_offset,
                    line_starts=line_starts,
                    metadata=metadata,
                    chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
                ))

                # 重叠（按 token 精确）
                overlap_texts = self._get_overlap_texts(current_chunk_texts)
                retained = _join_texts(overlap_texts, self.language)
                current_start_char = current_start_char + len(chunk_text) - len(retained)
                current_chunk_texts = overlap_texts
                current_tokens = self.count_tokens(retained)

            if not current_chunk_texts:
                current_start_char = sent_start

            current_chunk_texts.append(sent)
            current_tokens += sent_tokens

        if current_chunk_texts:
            chunks.append(self._create_chunk(
                text=text,
                chunks=current_chunk_texts,
                start_char=current_start_char + char_offset,
                end_char=len(text) + char_offset,
                line_starts=line_starts,
                metadata=metadata,
                chunk_id=f"{chunk_id_prefix}_{len(chunks)}"
            ))

        return chunks

    def _chunk_long_sentence(
        self,
        text: str,
        sent_text: str,
        start_char: int,
        line_starts: List[int],
        metadata: Dict[str, Any],
        chunk_id_prefix: str,
        existing_count: int
    ) -> List[TextChunk]:
        """对长句子进一步分块（滑动窗口 + token 精确重叠）"""
        chunks: List[TextChunk] = []

        if self.language == "zh":
            if JIEBA_AVAILABLE:
                words = list(jieba.cut(sent_text))
            else:
                words = list(sent_text)
        else:
            words = sent_text.split()

        index = 0
        consumed_chars = 0

        while index < len(words):
            # 收集窗口直到超过 chunk_size
            window: List[str] = []
            window_tokens = 0
            while index < len(words):
                word_tokens = self.count_tokens(words[index])
                if window and window_tokens + word_tokens > self.chunk_size:
                    break
                window.append(words[index])
                window_tokens += word_tokens
                index += 1

            if not window:
                break

            chunk_text = _join_texts(window, self.language)
            chunk_start = start_char + consumed_chars
            chunk_end = chunk_start + len(chunk_text)
            chunks.append(TextChunk(
                id=f"{chunk_id_prefix}_{existing_count + len(chunks)}",
                text=chunk_text,
                start_char=chunk_start,
                end_char=chunk_end,
                start_token=0,
                end_token=window_tokens,
                metadata=metadata.copy(),
                start_line=self._char_to_line(line_starts, chunk_start),
                end_line=self._char_to_line(line_starts, max(chunk_end - 1, chunk_start))
            ))

            # token 精确重叠：窗口尾部保留 overlap token 的词，index 回退
            keep: List[str] = []
            keep_tokens = 0
            for word in reversed(window):
                keep.append(word)
                keep_tokens += self.count_tokens(word)
                if keep_tokens >= self.overlap:
                    break
            keep.reverse()
            retained = _join_texts(keep, self.language)
            consumed_chars += len(chunk_text) - len(retained)
            index -= len(keep)

        return chunks

    def _get_overlap_texts(self, texts: List[str]) -> List[str]:
        """从尾部累积句子，直到达到目标 overlap token 数。"""
        if not texts:
            return []
        total = 0
        count = 1
        for item in reversed(texts):
            total += self.count_tokens(item)
            if total >= self.overlap:
                break
            count += 1
        return texts[-count:]

    def _create_chunk(
        self,
        text: str,
        chunks: List[str],
        start_char: int,
        end_char: int,
        line_starts: List[int],
        metadata: Dict[str, Any],
        chunk_id: str
    ) -> TextChunk:
        """创建 TextChunk 对象（含行号定位）。"""
        chunk_text = _join_texts(chunks, self.language)
        safe_end = max(end_char - 1, start_char)
        return TextChunk(
            id=chunk_id,
            text=chunk_text,
            start_char=start_char,
            end_char=end_char,
            start_token=0,
            end_token=self.count_tokens(chunk_text),
            metadata={
                **metadata,
                "char_length": len(chunk_text),
                "token_count": self.count_tokens(chunk_text)
            },
            start_line=self._char_to_line(line_starts, start_char),
            end_line=self._char_to_line(line_starts, safe_end)
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

        return [self._chunk_to_dict(chunk, doc_id, metadata) for chunk in chunks]

    def _chunk_to_dict(
        self,
        chunk: TextChunk,
        doc_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """TextChunk 转字典（含行号与公共元数据）。"""
        return {
            "id": chunk.id,
            "text": chunk.text,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "metadata": {
                **chunk.metadata,
                "doc_id": doc_id,
                "source": metadata.get("source", ""),
                "title": metadata.get("title", ""),
                "category": metadata.get("category", ""),
                "title_path": metadata.get("title_path", "")
            }
        }


class HybridChunker:
    """混合分块器：结合多种策略"""

    def __init__(
        self,
        chunk_size: int = 384,
        overlap: int = 50,
        language: str = "zh"
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.language = language

        self.sentence_chunker = TextChunker(
            chunk_size=chunk_size,
            overlap=overlap,
            language=language
        )

    def chunk_by_paragraph(
        self,
        text: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """按段落分块（块起点精确跟踪，支持行号与 title_path 元数据）"""
        metadata = metadata or {}

        paragraphs = re.split(r'\n{2,}', text)

        chunks: List[Dict[str, Any]] = []
        chunk_id_prefix = metadata.get("chunk_id_prefix", "chunk")
        line_starts = self.sentence_chunker._line_starts(text)

        current_paragraphs: List[str] = []
        current_size = 0
        chunk_start_char = 0

        for para in paragraphs:
            para = para.strip("\n")
            if not para.strip():
                continue

            para_tokens = self.sentence_chunker.count_tokens(para)

            if current_size + para_tokens > self.chunk_size and current_paragraphs:
                chunk_text = "\n\n".join(current_paragraphs)
                chunk_start = chunk_start_char
                chunk_end = chunk_start + len(chunk_text)
                chunks.append({
                    "id": f"{chunk_id_prefix}_{len(chunks)}",
                    "text": chunk_text,
                    "start_char": chunk_start,
                    "end_char": chunk_end,
                    "start_line": self.sentence_chunker._char_to_line(line_starts, chunk_start),
                    "end_line": self.sentence_chunker._char_to_line(
                        line_starts, max(chunk_end - 1, chunk_start)
                    ),
                    "metadata": {
                        **metadata,
                        "token_count": self.sentence_chunker.count_tokens(chunk_text),
                        "paragraph_indices": [
                            len(chunks) + i for i in range(len(current_paragraphs))
                        ]
                    }
                })

                # 重叠（按 token 精确）
                overlap_paras = self._get_overlap_paragraphs(current_paragraphs)
                retained = "\n\n".join(overlap_paras)
                chunk_start_char = chunk_end - len(retained)
                current_paragraphs = overlap_paras
                current_size = self.sentence_chunker.count_tokens(retained)

            if not current_paragraphs:
                pos = text.find(para, chunk_start_char)
                if pos >= 0:
                    chunk_start_char = pos

            current_paragraphs.append(para)
            current_size += para_tokens

        if current_paragraphs:
            chunk_text = "\n\n".join(current_paragraphs)
            chunk_end = chunk_start_char + len(chunk_text)
            chunks.append({
                "id": f"{chunk_id_prefix}_{len(chunks)}",
                "text": chunk_text,
                "start_char": chunk_start_char,
                "end_char": chunk_end,
                "start_line": self.sentence_chunker._char_to_line(
                    line_starts, chunk_start_char
                ),
                "end_line": self.sentence_chunker._char_to_line(
                    line_starts, max(chunk_end - 1, chunk_start_char)
                ),
                "metadata": {
                    **metadata,
                    "token_count": self.sentence_chunker.count_tokens(chunk_text),
                    "paragraph_indices": list(
                        range(len(chunks), len(chunks) + len(current_paragraphs))
                    )
                }
            })

        return chunks

    def _get_overlap_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """从尾部累积段落，直到达到目标 overlap token 数。"""
        if not paragraphs:
            return []
        total = 0
        count = 1
        for item in reversed(paragraphs):
            total += self.sentence_chunker.count_tokens(item)
            if total >= self.overlap:
                break
            count += 1
        return paragraphs[-count:]

    def smart_chunk(
        self,
        text: str,
        doc_id: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        智能分块：优先按段落，在段落过长时按句子（子块行号为整文档坐标）

        Args:
            text: 文档文本
            doc_id: 文档ID
            metadata: 文档元数据（支持 title_path 标题层级）

        Returns:
            分块结果列表
        """
        metadata = metadata or {}
        metadata["doc_id"] = doc_id

        line_starts = self.sentence_chunker._line_starts(text)

        para_chunks = self.chunk_by_paragraph(
            text, {**metadata, "chunk_id_prefix": f"doc_{doc_id}_para"}
        )

        final_chunks: List[Dict[str, Any]] = []

        for chunk in para_chunks:
            chunk_tokens = self.sentence_chunker.count_tokens(chunk["text"])

            # 段落过长时按句子切分（传入整文档坐标，保证行号正确）
            if chunk_tokens > self.chunk_size * 1.5:
                sub_chunks = self.sentence_chunker.chunk_by_sentence(
                    chunk["text"],
                    {
                        **metadata,
                        "parent_chunk": chunk["id"],
                        "chunk_id_prefix": f"doc_{doc_id}_chunk",
                    },
                    char_offset=chunk.get("start_char", 0),
                    line_starts=line_starts,
                )
                for sub in sub_chunks:
                    # 父块 = 所属段落全文（检索小块、合成大块）
                    sub.metadata["parent_text"] = chunk["text"]
                final_chunks.extend(
                    self.sentence_chunker._chunk_to_dict(sub, doc_id, metadata)
                    for sub in sub_chunks
                )
            else:
                # 段落块自身就是父块
                chunk["metadata"]["parent_text"] = chunk["text"]
                final_chunks.append(chunk)

        return final_chunks


def _join_texts(texts: List[str], language: str) -> str:
    """按语言用正确分隔符拼接。"""
    separator = "" if language == "zh" else " "
    return separator.join(texts)


# 全局实例
text_chunker = TextChunker()
hybrid_chunker = HybridChunker()


def chunk_text(
    text: str,
    doc_id: str,
    metadata: Dict[str, Any] = None,
    strategy: str = "smart"
) -> List[Dict[str, Any]]:
    """
    便捷的分块函数

    Args:
        text: 待分块文本
        doc_id: 文档ID
        metadata: 元数据
        strategy: 分块策略 "sentence", "paragraph", "smart"

    Returns:
        分块结果列表（id 全局唯一：doc_{doc_id}_chunk_{序号}）
    """
    if strategy == "sentence":
        chunks = text_chunker.chunk_document(text, doc_id, metadata)
    elif strategy == "paragraph":
        chunks = hybrid_chunker.chunk_by_paragraph(text, {**(metadata or {}), "doc_id": doc_id})
    else:  # smart
        chunks = hybrid_chunker.smart_chunk(text, doc_id, metadata)

    for index, chunk in enumerate(chunks):
        chunk["id"] = f"doc_{doc_id}_chunk_{index}"

    return chunks


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
    all_chunks: List[Dict[str, Any]] = []

    for doc in documents:
        chunks = chunk_text(
            text=doc["text"],
            doc_id=str(doc["id"]),
            metadata=doc.get("metadata"),
            strategy=strategy
        )
        all_chunks.extend(chunks)

    return all_chunks
