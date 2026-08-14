# -*- coding: utf-8 -*-
"""分块管线测试：token 计数、行号、重叠、id 唯一性、smart 策略"""
from app.services.text_chunker import (
    HybridChunker,
    TextChunker,
    chunk_documents_batch,
    chunk_text,
)


def _sample_long_text() -> str:
    para = (
        "SQL注入是一种常见的Web安全漏洞，攻击者在输入中插入恶意SQL代码。"
        "它通常发生在未正确过滤用户输入的场景。\n"
    )
    long_para = (
        "参数化查询会把用户输入当作数据处理，而不是可执行的SQL代码，"
        "这是防御SQL注入最有效的措施，开发者应该始终使用预编译语句。"
    ) * 20
    return para * 40 + "\n\n" + long_para + "\n\n" + para * 30


def test_chunk_ids_are_unique_and_stable():
    chunks = chunk_text(_sample_long_text(), doc_id="42", strategy="smart")

    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(cid.startswith("doc_42_chunk_") for cid in ids)


def test_chunk_tokens_stay_below_limit():
    chunks = chunk_text(_sample_long_text(), doc_id="1", strategy="smart")

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["metadata"]["token_count"] <= 384


def test_chunk_line_numbers_are_document_wide():
    chunks = chunk_text(_sample_long_text(), doc_id="1", strategy="smart")

    for chunk in chunks:
        assert chunk["start_line"] >= 1
        assert chunk["end_line"] >= chunk["start_line"]
    # 最后一个块应覆盖文档末尾附近的行
    assert chunks[-1]["end_line"] > chunks[0]["start_line"]


def test_chunk_overlap_is_present():
    chunks = chunk_text(_sample_long_text(), doc_id="1", strategy="smart")

    prev_end = 0
    saw_overlap = False
    for chunk in chunks:
        if chunk["start_char"] < prev_end:
            saw_overlap = True
            break
        prev_end = chunk["end_char"]
    assert saw_overlap


def test_chunk_metadata_keeps_doc_fields():
    chunks = chunk_text(
        _sample_long_text(),
        doc_id="7",
        metadata={"title": "SQL注入", "category": "Web安全", "title_path": "Web安全/SQL注入"},
        strategy="smart",
    )

    for chunk in chunks:
        assert chunk["metadata"]["doc_id"] == "7"
        assert chunk["metadata"]["title"] == "SQL注入"
        assert chunk["metadata"]["title_path"] == "Web安全/SQL注入"


def test_short_text_single_chunk():
    chunks = chunk_text("这是一个很短的文档。", doc_id="9", strategy="smart")

    assert len(chunks) == 1
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 1


def test_chunk_documents_batch_matches_chunk_text():
    docs = [
        {"id": "1", "text": _sample_long_text(), "metadata": {"title": "a"}},
        {"id": "2", "text": "短文档。", "metadata": {"title": "b"}},
    ]

    batch = chunk_documents_batch(docs, strategy="smart")
    single = chunk_text(docs[0]["text"], doc_id="1", metadata={"title": "a"}, strategy="smart")

    assert len(batch) == len(single) + 1
    assert {c["id"] for c in single} <= {c["id"] for c in batch}


def test_tokenizer_fallback_keeps_working():
    chunker = TextChunker(model_name="")
    # 无 tokenizer 时按字符估算，仍能返回正数
    assert chunker.count_tokens("测试文本") >= 1
    assert chunker.count_tokens("hello world") >= 1


def test_paragraph_chunker_line_numbers():
    text = "第一段。\n\n第二段内容较长，" + "很长" * 50 + "。\n\n第三段。"
    chunker = HybridChunker(chunk_size=64, overlap=10)

    chunks = chunker.chunk_by_paragraph(text, {"title": "t"})

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk["start_line"] >= 1
        assert chunk["end_line"] >= chunk["start_line"]
        assert chunk["metadata"]["token_count"] > 0


def test_token_count_mode_distinguishes_tokenizer_and_estimate_without_loading_models():
    class FakeTokenizer:
        def encode(self, text, add_special_tokens):
            assert add_special_tokens is False
            return [1, 2, 3]

    class FailingTokenizer:
        def encode(self, text, add_special_tokens):
            raise RuntimeError("tokenizer unavailable")

    chunker = object.__new__(TextChunker)
    chunker.language = "en"
    chunker._tokenizer_failed = False
    chunker._tokenizer = FakeTokenizer()

    assert chunker.count_tokens_with_mode("one two") == (3, "tokenizer")

    chunker._tokenizer = FailingTokenizer()
    assert chunker.count_tokens_with_mode("one two") == (2, "estimate")
    assert chunker._tokenizer is None
    assert chunker._tokenizer_failed is True
