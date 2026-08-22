# -*- coding: utf-8 -*-
"""只读导出公共知识库语料与向量分块元数据，用于离线生成企业 RAG 评测集。

用途：
- 导出 ``knowledge_items`` 的正文与元数据（评测集 gold evidence 的唯一事实来源）；
- 导出 ``knowledge_embeddings`` collection 的分块 payload（chunk_id / doc_id /
  start_line / end_line / title / text），使评测行号与真实检索索引完全一致。

安全约束（必须遵守）：
- 只读：仅执行 SELECT 与 Qdrant scroll/count，不调用任何写接口；
  刻意不走 ``QdrantVectorBackend.__init__``（其 ``_ensure_collection`` 存在写路径），
  而是按同一份 Config 直接构建只读客户端；
- 静默：不打印任何环境变量、连接串、密钥或配置值；异常先脱敏再输出；
- 出口：默认写入 ``backend/data/``（已在 .gitignore 中，运行时数据不入库）。

用法（在 backend/ 下）::

    venv\\Scripts\\python.exe -m app.scripts.export_rag_eval_corpus
    venv\\Scripts\\python.exe -m app.scripts.export_rag_eval_corpus --output D:\\tmp\\corpus.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app import create_app, db

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# 匹配 URL 中的 userinfo 段（scheme://user:pass@host），输出前统一打码。
_SECRET_URL_PATTERN = re.compile(r"(\w+://)[^/@\s]+:[^@\s]+@")

SCROLL_PAGE_SIZE = 256


def _sanitize(message: Any) -> str:
    """把可能内嵌凭据的异常信息打码后返回。"""
    return _SECRET_URL_PATTERN.sub(r"\1***@...", str(message))


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="只读导出公共知识库语料与向量分块元数据（评测集生成用）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="导出 JSON 路径；默认 backend/data/rag_corpus_export.json（已 gitignore）",
    )
    parser.add_argument(
        "--collection",
        default="knowledge_embeddings",
        help="Qdrant collection 名称（默认公共知识库）",
    )
    parser.add_argument(
        "--no-chunk-text",
        action="store_true",
        help="不导出分块正文（仅元数据），显著减小文件体积",
    )
    return parser


def resolve_output_path(raw: Optional[str]) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    return BACKEND_ROOT / "data" / "rag_corpus_export.json"


def export_documents() -> List[Dict[str, Any]]:
    """读取 knowledge_items 全量正文与元数据（只读 SELECT）。"""
    from app.models.knowledge import KnowledgeItem

    items = (
        db.session.query(KnowledgeItem)
        .order_by(KnowledgeItem.id.asc())
        .all()
    )
    documents: List[Dict[str, Any]] = []
    for item in items:
        documents.append(
            {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "summary": item.summary,
                "source": item.source,
                "difficulty": item.difficulty,
                "status": item.status,
                "category_id": item.category_id,
                "category_name": item.category.name if item.category else "",
                "tags": [tag.tag_name for tag in item.tags],
            }
        )
    return documents


def _build_readonly_client():
    """按项目 Config 直连 Qdrant，绕开任何可能建集合的初始化路径。"""
    from qdrant_client import QdrantClient

    from app.config import Config
    from app.services.vector_stores.qdrant import _ensure_local_no_proxy

    _ensure_local_no_proxy()
    url = str(getattr(Config, "QDRANT_URL", "") or "").strip()
    if url:
        return QdrantClient(url=url, timeout=30)
    path = str(getattr(Config, "QDRANT_PATH", "") or "").strip()
    return QdrantClient(path=path, timeout=30)


def export_chunks(
    collection: str,
    *,
    include_text: bool = True,
) -> List[Dict[str, Any]]:
    """scroll 全量分块 payload（with_vectors=False，纯只读）。"""
    client = _build_readonly_client()
    total = int(client.count(collection_name=collection, exact=True).count)
    chunks: List[Dict[str, Any]] = []
    offset: Any = None
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            limit=SCROLL_PAGE_SIZE,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points or []:
            payload = dict(point.payload or {})
            record: Dict[str, Any] = {
                "point_id": str(payload.get("id", point.id)),
                "doc_id": payload.get("doc_id"),
                "chunk_index": payload.get("chunk_index"),
                "start_line": payload.get("start_line"),
                "end_line": payload.get("end_line"),
                "title": payload.get("title"),
            }
            if include_text:
                record["text"] = payload.get("text")
            chunks.append(record)
        if next_offset is None:
            break
        offset = next_offset
    if total != len(chunks):
        # 数量不一致仅提示，不中断：scroll 期间并发写入可能导致轻微偏差。
        print(
            json.dumps(
                {"warning": "count_mismatch", "count": total, "scrolled": len(chunks)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
    return chunks


def run_export(output: Path, collection: str, *, include_text: bool) -> Dict[str, Any]:
    documents: List[Dict[str, Any]] = []
    chunks: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        documents = export_documents()
    except Exception as exc:  # noqa: BLE001 - 输出前已脱敏
        errors.append(f"documents: {type(exc).__name__}: {_sanitize(exc)}")

    try:
        chunks = export_chunks(collection, include_text=include_text)
    except Exception as exc:  # noqa: BLE001 - 输出前已脱敏
        errors.append(f"chunks: {type(exc).__name__}: {_sanitize(exc)}")

    payload = {
        "exported_at": datetime.utcnow().isoformat(),
        "collection": collection,
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "includes_chunk_text": include_text,
        "errors": errors,
        "documents": documents,
        "chunks": chunks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "output": str(output),
        "documents": len(documents),
        "chunks": len(chunks),
        "errors": errors,
    }


def main() -> None:
    args = build_argument_parser().parse_args()
    output = resolve_output_path(args.output)
    app = create_app()
    with app.app_context():
        summary = run_export(
            output,
            args.collection,
            include_text=not args.no_chunk_text,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
