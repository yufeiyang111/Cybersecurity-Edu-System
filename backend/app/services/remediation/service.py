"""Persistence orchestration for human-reviewable remediation suggestions."""
from __future__ import annotations

from typing import Iterable

from app import db
from app.models.security import EvidenceType, FindingEvidence, RemediationSuggestion, SecurityFinding
from app.services.public_knowledge import PublicKnowledgeRetriever
from app.services.security_knowledge import KnowledgeCitation, SecurityKnowledgeRetriever

from .context import _extract_code_context, _value
from .fallback_rules import _rule_based_fallback
from .provider import _call_provider, _provider_attribute, _provider_patch_if_safe, configured_provider
from .settings import _config_bool, _config_int

class RemediationService:
    """Generate a persisted, human-reviewable suggestion for one Finding.

    The service only flushes persistence changes so the authenticated route can
    atomically add its audit record before committing the transaction. It never
    stores prompts, provider response bodies, or unredacted snapshot material.
    """

    def __init__(
        self,
        *,
        retriever: SecurityKnowledgeRetriever | None = None,
        public_retriever: PublicKnowledgeRetriever | None = None,
        provider: object | None = None,
    ) -> None:
        self.retriever = retriever or SecurityKnowledgeRetriever()
        self.public_retriever = public_retriever or PublicKnowledgeRetriever()
        self.provider = provider

    def generate(self, finding_id: int, actor_id: int) -> RemediationSuggestion:
        if not isinstance(finding_id, int) or finding_id <= 0:
            raise ValueError("finding_id 必须是正整数")
        if not isinstance(actor_id, int) or actor_id <= 0:
            raise ValueError("actor_id 必须是正整数")

        finding = db.session.get(SecurityFinding, finding_id)
        if finding is None:
            raise ValueError("Finding 不存在")

        snapshot = finding.task.snapshot
        workspace_id = snapshot.project.workspace_id
        max_context_chars = _config_int("REMEDIATION_MAX_CONTEXT_CHARS", 12_000)
        max_output_chars = _config_int("REMEDIATION_MAX_OUTPUT_CHARS", 8_000)
        max_patch_lines = _config_int("REMEDIATION_PATCH_MAX_LINES", 500)
        max_patch_chars = _config_int("REMEDIATION_PATCH_MAX_CHARS", 50_000)
        context = _extract_code_context(snapshot.storage_path, finding, max_context_chars)
        citations = self._merged_citations(
            workspace_id,
            _retrieval_query(finding),
            _config_int("REMEDIATION_RETRIEVAL_TOP_K", 5),
        )
        warning_codes = list(context.warning_codes)
        citation_payloads = [_citation_dict(citation) for citation in citations]
        safe_citation_payloads = [
            payload
            for payload, citation in zip(citation_payloads, citations)
            if not citation.injection_flags
        ]
        if len(safe_citation_payloads) != len(citation_payloads):
            warning_codes.append("CITATION_INJECTION_FILTERED")
        provider = configured_provider(self.provider)
        if provider is None:
            warning_codes.append(
                "LLM_PROVIDER_UNAVAILABLE" if _config_bool("REMEDIATION_LLM_ENABLED") else "LLM_DISABLED"
            )
            payload = _fallback_payload(
                finding,
                snapshot.storage_path,
                context,
                max_patch_lines=max_patch_lines,
                max_patch_chars=max_patch_chars,
            )
            warning_codes.extend(payload[4])
            provider_name = "rule-based"
            model_name = None
            model_version = "rules-v1"
            confidence = 0.85
        else:
            generated = _call_provider(
                provider,
                finding,
                context,
                safe_citation_payloads,
                max_output_chars=max_output_chars,
            )
            if generated.payload is None:
                warning_codes.append(generated.warning_code or "LLM_PROVIDER_FAILED")
                payload = _fallback_payload(
                    finding,
                    snapshot.storage_path,
                    context,
                    max_patch_lines=max_patch_lines,
                    max_patch_chars=max_patch_chars,
                )
                warning_codes.extend(payload[4])
                provider_name = "rule-based"
                model_name = None
                model_version = "rules-v1"
                confidence = 0.85
            else:
                parsed = generated.payload
                patch_diff = _provider_patch_if_safe(
                    finding,
                    snapshot.storage_path,
                    context,
                    parsed.get("patch_diff"),
                    max_patch_lines=max_patch_lines,
                    max_patch_chars=max_patch_chars,
                    warning_codes=warning_codes,
                )
                payload = (
                    parsed["rationale"],
                    parsed["remediation_steps"],
                    patch_diff,
                    [],
                    [],
                )
                provider_name = _provider_attribute(provider, "provider_name", "minimax")
                model_name = _provider_attribute(provider, "model", None)
                model_version = _provider_attribute(provider, "model_version", None)
                confidence = parsed["confidence"]

        rationale, steps, patch_diff, _unused, _payload_warnings = payload
        suggestion = RemediationSuggestion(
            finding_id=finding.id,
            rationale=rationale,
            remediation_steps_json=steps,
            patch_diff=patch_diff,
            citations_json=citation_payloads,
            warning_codes_json=_unique(warning_codes),
            provider=provider_name,
            model=model_name,
            model_version=model_version,
            confidence=confidence,
        )
        db.session.add(suggestion)
        _persist_rag_references(finding.id, citations)
        db.session.flush()
        return suggestion

    def _merged_citations(self, workspace_id: int, query: str, top_k: int) -> list[KnowledgeCitation]:
        """公共知识库优先，工作区私有知识叠加，按数据源归属去重。

        同一 document_id 可能同时出现在公共库与工作区私有库，按 citation_id 去重
        保留排序靠前的版本，避免重复引用同一篇文档。
        """
        public_citations = self.public_retriever.retrieve(workspace_id, query, top_k)
        private_citations = self.retriever.retrieve(workspace_id, query, top_k)
        seen: set[str] = set()
        merged: list[KnowledgeCitation] = []
        for citation in [*public_citations, *private_citations]:
            if citation.citation_id in seen:
                continue
            seen.add(citation.citation_id)
            merged.append(citation)
            if len(merged) >= top_k:
                break
        return merged
def _retrieval_query(finding: SecurityFinding) -> str:
    return " ".join(
        part
        for part in (
            finding.rule_id,
            _value(finding.category),
            finding.cwe_id or "",
            finding.cve_id or "",
            finding.message,
        )
        if part
    )[:2000]



def _fallback_payload(
    finding: SecurityFinding,
    snapshot_storage_path: str | None,
    context: _CodeContext,
    *,
    max_patch_lines: int,
    max_patch_chars: int,
) -> tuple[str, list[str], str | None, list[str], list[str]]:
    rationale, steps, patch_diff, warnings = _rule_based_fallback(
        finding,
        snapshot_storage_path,
        context,
        max_patch_lines=max_patch_lines,
        max_patch_chars=max_patch_chars,
    )
    return rationale, steps, patch_diff, [], warnings


def _citation_dict(citation: object) -> dict:
    return {
        "citation_id": citation.citation_id,
        "document_id": citation.document_id,
        "source_id": citation.source_id,
        "title": citation.title,
        "source_name": citation.source_name,
        "version": citation.version,
        "snippet": citation.snippet,
        "score": citation.score,
        "trust_score": citation.trust_score,
        "injection_flags": list(citation.injection_flags),
    }


def _persist_rag_references(finding_id: int, citations: Iterable[object]) -> None:
    for citation in citations:
        source_uri = f"knowledge://{citation.source_id}/{citation.document_id}"
        existing = FindingEvidence.query.filter_by(
            finding_id=finding_id,
            evidence_type=EvidenceType.RAG_REFERENCE.value,
            source_uri=source_uri,
        ).one_or_none()
        if existing is None:
            db.session.add(
                FindingEvidence(
                    finding_id=finding_id,
                    evidence_type=EvidenceType.RAG_REFERENCE.value,
                    content_redacted=citation.citation_id,
                    source_uri=source_uri,
                    score=float(citation.score),
                )
            )


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
