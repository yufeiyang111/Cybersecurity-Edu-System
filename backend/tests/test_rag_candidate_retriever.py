# -*- coding: utf-8 -*-
from app.services.rag_core.candidate_retriever import CandidateRetriever, QueryNormalizer
from app.services.vector_stores.contracts import VectorHit


def test_normalizer_handles_security_identifiers_and_mixed_language():
    result = QueryNormalizer().normalize("  CVE-2024-1234 的 443端口 nginx.conf --proxy  怎么配？ ")
    assert "cve-2024-1234" in result.identifiers
    assert "port:443" in result.identifiers
    assert "nginx.conf" in result.identifiers


def test_candidate_trace_excludes_content_and_handles_degraded_and_errors():
    class Backend:
        def hybrid_search(self, **kwargs):
            assert kwargs["vector"] is None
            return [
                VectorHit(
                    id="chunk-1",
                    text="secret evidence text",
                    metadata={"doc_id": "doc-1", "title": "标题"},
                    similarity=None,
                    distance=1.0,
                    retrieval_metadata={
                        "retrieval_path": "lexical_only_degraded",
                        "bm25_rank": 1,
                        "bm25_score": 2.0,
                    },
                )
            ]
    retrieved = CandidateRetriever(Backend()).retrieve("CWE-79 80端口", vector=[0.1], embedding_degraded=True)
    assert retrieved.degraded is True
    assert retrieved.candidates[0].document_id == "doc-1"
    assert "secret evidence text" not in str(retrieved.trace_summary())
    assert CandidateRetriever(Backend()).retrieve("   ", vector=[0.1]).warnings == ("EMPTY_QUERY",)
    class Broken:
        def hybrid_search(self, **kwargs):
            raise RuntimeError("down")
    assert CandidateRetriever(Broken()).retrieve("CWE-79", vector=[0.1]).warnings == ("QDRANT_UNAVAILABLE",)