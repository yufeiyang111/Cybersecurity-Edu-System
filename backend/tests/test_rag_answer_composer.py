# -*- coding: utf-8 -*-
"""结构化 RAG 回答解析、兼容与 citation 验证测试。"""
import json

import pytest

from app.services.rag_core.answer_composer import AnswerComposer
from app.services.rag_core.contracts import CitationManifest, EvidenceReference


def _manifest() -> CitationManifest:
    return CitationManifest(
        references=(
            EvidenceReference(
                citation_id="C-valid",
                document_id="doc-1",
                title="SQL 注入防护",
                start_line=10,
                end_line=14,
                chunk_id="chunk-1",
                corpus_version="knowledge_embeddings-v1",
            ),
        )
    )


def _supported_payload(citation_id: str = "C-valid") -> str:
    return json.dumps(
        {
            "answer_status": "supported",
            "answer": "应使用参数化查询处理用户输入。",
            "claims": [
                {
                    "text": "参数化查询可降低 SQL 注入风险。",
                    "citation_ids": [citation_id],
                }
            ],
            "uncertainty": [],
        },
        ensure_ascii=False,
    )


def test_composer_accepts_valid_structured_answer_and_binds_claim_to_manifest():
    result = AnswerComposer().compose(
        _supported_payload(),
        citation_manifest=_manifest(),
        strict_citations=True,
    )

    assert result.answer_status == "supported"
    assert result.answer == "应使用参数化查询处理用户输入。"
    assert result.warnings == ()
    assert result.citations.claim_citations == {
        "参数化查询可降低 SQL 注入风险。": ("C-valid",)
    }


def test_composer_degrades_parse_failures_without_claiming_supported_answer():
    raw_legacy_text = "模型没有按 JSON 格式回答，但这段文本应只在兼容模式展示。"

    non_strict = AnswerComposer().compose(
        raw_legacy_text,
        citation_manifest=_manifest(),
        strict_citations=False,
    )
    strict = AnswerComposer().compose(
        raw_legacy_text,
        citation_manifest=_manifest(),
        strict_citations=True,
    )

    assert non_strict.answer == raw_legacy_text
    assert non_strict.answer_status == "degraded"
    assert set(non_strict.warnings) == {
        "STRUCTURED_RESPONSE_PARSE_FAILED",
        "UNVERIFIED_LEGACY_RESPONSE",
    }
    assert strict.answer_status == "degraded"
    assert strict.answer != raw_legacy_text
    assert "STRICT_CITATION_REJECTED" in strict.warnings
    assert strict.citations.claim_citations == {}


def test_composer_rejects_forged_citation_in_strict_mode_and_warns_in_compat_mode():
    strict = AnswerComposer().compose(
        _supported_payload("C-forged"),
        citation_manifest=_manifest(),
        strict_citations=True,
    )
    non_strict = AnswerComposer().compose(
        _supported_payload("C-forged"),
        citation_manifest=_manifest(),
        strict_citations=False,
    )

    assert strict.answer_status == "degraded"
    assert strict.citations.claim_citations == {}
    assert "CITATION_VALIDATION_FAILED" in strict.warnings
    assert "STRICT_CITATION_REJECTED" in strict.warnings
    assert non_strict.answer_status == "degraded"
    assert non_strict.answer == "应使用参数化查询处理用户输入。"
    assert non_strict.citations.claim_citations == {}
    assert "UNVERIFIED_LEGACY_RESPONSE" in non_strict.warnings


def test_composer_handles_fenced_json_and_rejects_missing_or_malformed_claim_citations():
    fenced = "```json\n" + _supported_payload() + "\n```"
    missing_citation = json.dumps(
        {
            "answer_status": "supported",
            "answer": "未附引用的回答。",
            "claims": [{"text": "未引用主张", "citation_ids": []}],
            "uncertainty": [],
        },
        ensure_ascii=False,
    )
    malformed_claims = json.dumps(
        {
            "answer_status": "supported",
            "answer": "结构错误。",
            "claims": {"text": "不是数组"},
            "uncertainty": [],
        },
        ensure_ascii=False,
    )

    accepted = AnswerComposer().compose(
        fenced,
        citation_manifest=_manifest(),
        strict_citations=True,
    )
    missing = AnswerComposer().compose(
        missing_citation,
        citation_manifest=_manifest(),
        strict_citations=True,
    )
    malformed = AnswerComposer().compose(
        malformed_claims,
        citation_manifest=_manifest(),
        strict_citations=True,
    )

    assert accepted.answer_status == "supported"
    assert missing.answer_status == "degraded"
    assert missing.validation.errors == ("SUPPORTED_CLAIM_WITHOUT_CITATION",)
    assert malformed.answer_status == "degraded"
    assert "STRUCTURED_RESPONSE_PARSE_FAILED" in malformed.warnings

@pytest.mark.parametrize(
    "answer_status",
    ("insufficient_evidence", "conflicting_evidence", "degraded"),
)
def test_composer_preserves_valid_non_supported_answer_statuses(answer_status):
    raw_response = json.dumps(
        {
            "answer_status": answer_status,
            "answer": "当前证据不能形成可完全验证的结论。",
            "claims": [],
            "uncertainty": ["需要补充可定位资料。"],
        },
        ensure_ascii=False,
    )

    result = AnswerComposer().compose(
        raw_response,
        citation_manifest=_manifest(),
        strict_citations=True,
    )

    assert result.answer_status == answer_status
    assert result.citations.claim_citations == {}
    assert result.uncertainty == ("需要补充可定位资料。",)
