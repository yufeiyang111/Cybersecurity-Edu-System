# -*- coding: utf-8 -*-
"""CitationValidator 对伪造、缺失与不可定位引用的边界测试。"""
from app.services.rag_core.citation_validator import (
    CitationClaim,
    CitationValidator,
)
from app.services.rag_core.contracts import CitationManifest, EvidenceReference


def _manifest() -> CitationManifest:
    return CitationManifest(
        references=(
            EvidenceReference(
                citation_id="C-valid",
                document_id="doc-1",
                title="有效来源",
                start_line=10,
                end_line=12,
                chunk_id="chunk-1",
                corpus_version="knowledge_embeddings-v1",
            ),
            EvidenceReference(
                citation_id="C-unlocatable",
                document_id="doc-2",
                title="不可定位来源",
                chunk_id="chunk-2",
                corpus_version="knowledge_embeddings-v1",
            ),
        )
    )


def test_validator_requires_current_locatable_citations_for_supported_claims():
    validator = CitationValidator()

    valid = validator.validate(
        answer_status="supported",
        claims=(CitationClaim("参数化查询可防 SQL 注入", ("C-valid",)),),
        citation_manifest=_manifest(),
    )
    missing = validator.validate(
        answer_status="supported",
        claims=(CitationClaim("没有引用的关键主张", ()),),
        citation_manifest=_manifest(),
    )
    forged = validator.validate(
        answer_status="supported",
        claims=(CitationClaim("伪造引用", ("C-forged",)),),
        citation_manifest=_manifest(),
    )
    unlocatable = validator.validate(
        answer_status="supported",
        claims=(CitationClaim("不可定位引用", ("C-unlocatable",)),),
        citation_manifest=_manifest(),
    )

    assert valid.is_valid is True
    assert valid.errors == ()
    assert missing.is_valid is False
    assert missing.errors == ("SUPPORTED_CLAIM_WITHOUT_CITATION",)
    assert forged.is_valid is False
    assert forged.errors == ("UNKNOWN_CITATION",)
    assert unlocatable.is_valid is False
    assert unlocatable.errors == ("UNLOCATABLE_CITATION",)


def test_validator_rejects_supported_answer_without_claims_and_duplicate_manifest_ids():
    validator = CitationValidator()
    duplicate_manifest = CitationManifest(
        references=(
            EvidenceReference(
                citation_id="C-duplicate",
                document_id="doc-1",
                title="第一条",
                start_line=1,
                end_line=2,
            ),
            EvidenceReference(
                citation_id="C-duplicate",
                document_id="doc-2",
                title="第二条",
                start_line=3,
                end_line=4,
            ),
        )
    )

    no_claims = validator.validate(
        answer_status="supported",
        claims=(),
        citation_manifest=_manifest(),
    )
    duplicate = validator.validate(
        answer_status="supported",
        claims=(CitationClaim("有引用", ("C-duplicate",)),),
        citation_manifest=duplicate_manifest,
    )
    insufficient = validator.validate(
        answer_status="insufficient_evidence",
        claims=(),
        citation_manifest=_manifest(),
    )

    assert no_claims.errors == ("SUPPORTED_WITHOUT_CLAIMS",)
    assert duplicate.errors == ("DUPLICATE_MANIFEST_CITATION",)
    assert insufficient.is_valid is True
