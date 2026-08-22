# -*- coding: utf-8 -*-
"""公共知识库 RAG 离线评测集包（版本化、可复现、可审计）。"""
from __future__ import annotations

from app.services.rag_core.datasets.public_rag_eval_v1 import (
    ALLOWED_CATEGORIES,
    ALLOWED_DIFFICULTY,
    ALLOWED_STATUS,
    CORPUS_VERSION,
    EVALUATION_CASES,
    RAW_SPECS,
    build_evaluation_cases,
)
from app.services.rag_core.datasets.production_rag_eval_v1 import (
    PRODUCTION_CORPUS_VERSION,
    PRODUCTION_EVALUATION_CASES,
    build_production_evaluation_cases,
)
from app.services.rag_core.datasets.production_rag_eval_curated_v1 import (
    PRODUCTION_CURATED_EVALUATION_CASES,
    build_production_curated_evaluation_cases,
)
from app.services.rag_core.datasets.corpus_fixture import (
    build_sample_corpus,
    chunk_corpus,
    locate_evidence,
)

__all__ = [
    "ALLOWED_CATEGORIES",
    "ALLOWED_DIFFICULTY",
    "ALLOWED_STATUS",
    "CORPUS_VERSION",
    "EVALUATION_CASES",
    "RAW_SPECS",
    "build_evaluation_cases",
    "PRODUCTION_CORPUS_VERSION",
    "PRODUCTION_EVALUATION_CASES",
    "build_production_evaluation_cases",
    "PRODUCTION_CURATED_EVALUATION_CASES",
    "build_production_curated_evaluation_cases",
    "build_sample_corpus",
    "chunk_corpus",
    "locate_evidence",
]
