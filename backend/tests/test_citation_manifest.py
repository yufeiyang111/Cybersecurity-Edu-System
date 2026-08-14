# -*- coding: utf-8 -*-
"""Citation Manifest 的稳定标识与脱敏输出测试。"""
from app.services.rag_core.citation_manifest import CitationManifestBuilder
from app.services.rag_core.contracts import EvidencePack, EvidenceReference


def _reference(
    *,
    chunk_id: str = "chunk-7",
    start_line: int = 10,
    end_line: int = 20,
    content: str = "敏感证据正文不应影响 citation ID",
) -> EvidenceReference:
    return EvidenceReference(
        citation_id="temporary",
        document_id="doc-42",
        title="SQL 注入防护",
        source="公开安全知识库",
        start_line=start_line,
        end_line=end_line,
        chunk_id=chunk_id,
        corpus_version="knowledge_embeddings-v1",
        title_path="Web安全/SQL注入",
        content=content,
    )


def test_manifest_citation_id_is_stable_without_using_evidence_content():
    builder = CitationManifestBuilder()
    original = _reference()
    changed_content = _reference(content="正文更新后也不得改变引用身份")
    changed_chunk = _reference(chunk_id="chunk-8")
    changed_lines = _reference(start_line=21, end_line=30)

    original_manifest = builder.build(EvidencePack((original,), 3, 10))
    changed_content_manifest = builder.build(EvidencePack((changed_content,), 3, 10))
    changed_chunk_manifest = builder.build(EvidencePack((changed_chunk,), 3, 10))
    changed_lines_manifest = builder.build(EvidencePack((changed_lines,), 3, 10))

    citation_id = original_manifest.references[0].citation_id
    assert citation_id.startswith("C-")
    assert citation_id == changed_content_manifest.references[0].citation_id
    assert citation_id != changed_chunk_manifest.references[0].citation_id
    assert citation_id != changed_lines_manifest.references[0].citation_id
    payload = original_manifest.to_dict()
    assert payload["citations"][0]["chunk_id"] == "chunk-7"
    assert payload["citations"][0]["corpus_version"] == "knowledge_embeddings-v1"
    assert "敏感证据正文" not in str(payload)


def test_manifest_deduplicates_same_identity_and_uses_line_fallback_without_content():
    builder = CitationManifestBuilder()
    first = _reference(content="first body")
    duplicate = _reference(content="second body")
    line_only = EvidenceReference(
        citation_id="temporary",
        document_id="doc-line-only",
        title="行号回退来源",
        start_line=40,
        end_line=45,
        content="正文不能影响身份",
    )

    manifest = builder.build(EvidencePack((first, duplicate, line_only), 5, 10))

    assert len(manifest.references) == 2
    assert manifest.references[1].chunk_id == "lines-40-45"
    assert manifest.references[1].corpus_version == "knowledge_embeddings-v1"
    assert "正文不能影响身份" not in str(manifest.to_dict())

def test_manifest_identity_changes_when_only_end_line_changes():
    builder = CitationManifestBuilder()
    first = _reference(start_line=10, end_line=20)
    changed_end_line = _reference(start_line=10, end_line=21)

    first_id = builder.build(EvidencePack((first,), 3, 10)).references[0].citation_id
    changed_id = builder.build(
        EvidencePack((changed_end_line,), 3, 10),
    ).references[0].citation_id

    assert first_id != changed_id
