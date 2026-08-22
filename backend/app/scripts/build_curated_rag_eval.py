# -*- coding: utf-8 -*-
"""校验人工策展查询表并生成全覆盖的真实证据评测集模块。

流程：
1. 读取 ``datasets/curated_query_map.py`` 中 LLM 为全部真实文档手写的
   查询表（目标：覆盖 ``rag_corpus_export.json`` 里的每一篇文档）；
2. 为每篇文档确定 gold evidence 锚句（三级策略，全部逐字机械校验，
   杜绝编造）：
   a) ``OPTIONAL_ANCHOR_OVERRIDES`` 里人工指定的原文片段；
   b) ``generate_rag_eval_from_corpus._pick_anchor`` 启发式挑出的信息句；
   c) 宽松兜底（面向代码块为主、启发式选不出句子的文档）；
3. 回填真实 chunk_id / start_line / end_line / title，输出
   ``datasets/production_rag_eval_curated_v1.py``。

用法（在 backend/ 下）::

    venv\\Scripts\\python.exe -m app.scripts.build_curated_rag_eval
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.scripts.generate_rag_eval_from_corpus import _pick_anchor
from app.services.rag_core.datasets.curated_query_map import (
    CURATED_QUERY_MAP,
    OPTIONAL_ANCHOR_OVERRIDES,
)
from app.services.rag_core.citation_manifest import DEFAULT_PUBLIC_CORPUS_VERSION

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT_PATH = BACKEND_ROOT / "data" / "rag_corpus_export.json"
DEFAULT_OUTPUT_PATH = (
    BACKEND_ROOT
    / "app"
    / "services"
    / "rag_core"
    / "datasets"
    / "production_rag_eval_curated_v1.py"
)

_BULLET_PATTERN = re.compile(r"^(?:\s*(?:[#>*\-+]+|\d+[.、)]|\[[^\]]*\]))*\s*")
_ALNUM_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
_KEYWORD_PATTERN = re.compile(
    r"是|包括|分为|原则|措施|防御|攻击|检测|配置|使用|支持|需要|确保|避免"
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="校验策展查询表并生成全覆盖真实证据评测集",
    )
    parser.add_argument("--export", default=None, help="导出 JSON 路径")
    parser.add_argument("--output", default=None, help="输出模块路径")
    return parser


def locate_override(doc_chunks: List[Dict[str, Any]], must_contain: str) -> Dict[str, Any]:
    """人工指定锚句的逐字定位；找不到即失败。"""
    hits = [
        chunk
        for chunk in doc_chunks
        if must_contain in (chunk.get("text") or "")
    ]
    if not hits:
        raise ValueError(f"人工指定锚句未在真实分块中找到：{must_contain!r}")
    hits.sort(key=lambda chunk: int(chunk.get("chunk_index") or 0))
    return hits[0]


def _fallback_candidate_score(cleaned: str) -> int:
    score = 0
    if re.search(r"[\u4e00-\u9fff]", cleaned):
        score += 3
    score += len(_KEYWORD_PATTERN.findall(cleaned))
    if 16 <= len(cleaned) <= 90:
        score += 2
    return score


def pick_fallback_anchor(
    doc_chunks: List[Dict[str, Any]],
    exclude_anchors: Optional[set] = None,
) -> Optional[Tuple[Dict[str, Any], str]]:
    """宽松兜底锚句（面向代码块为主、无中文正文句的文档），确定性选取。"""
    exclude = exclude_anchors or set()
    best: Optional[Tuple[Dict[str, Any], str]] = None
    best_score = 1  # 至少要有正分才采纳
    for chunk in doc_chunks:
        for raw_line in (chunk.get("text") or "").splitlines():
            raw = raw_line.strip()
            if raw in exclude:
                continue
            cleaned = _BULLET_PATTERN.sub("", raw_line).strip()
            if len(cleaned) < 10 or len(cleaned) > 120:
                continue
            if not _ALNUM_PATTERN.search(cleaned):
                continue
            score = _fallback_candidate_score(cleaned)
            if score > best_score:
                best_score = score
                best = (chunk, raw)
    return best


def resolve_anchor(
    doc_id: str,
    doc_chunks: List[Dict[str, Any]],
    exclude_anchors: Optional[set] = None,
) -> Tuple[Dict[str, Any], str, str]:
    """三级锚句策略：人工指定 → 启发式 → 宽松兜底；全部为原文逐字片段。

    exclude_anchors 为跨文档已占用锚句集合（保证评测集内锚句唯一）。
    返回（chunk, 锚句, 层级）。
    """
    exclude = exclude_anchors or set()
    override = OPTIONAL_ANCHOR_OVERRIDES.get(doc_id)
    if override and override not in exclude:
        return locate_override(doc_chunks, override), override, "override"
    picked = _pick_anchor(doc_chunks, exclude_anchors=exclude)
    if picked is not None:
        return picked["chunk"], picked["raw"], "heuristic"
    fallback = pick_fallback_anchor(doc_chunks, exclude_anchors=exclude)
    if fallback is None:
        raise ValueError(f"文档 {doc_id} 找不到任何可用锚句")
    return fallback[0], fallback[1], "fallback"


def compile_specs(export: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    """编译全部策展用例；返回（规格列表, 兜底锚句使用数, 无分块跳过的文档）。"""
    chunks_by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for chunk in export.get("chunks", []):
        chunks_by_doc.setdefault(str(chunk["doc_id"]), []).append(chunk)

    no_chunks = sorted(
        (k for k in CURATED_QUERY_MAP if k not in chunks_by_doc), key=int
    )

    ordered_ids = [
        k
        for k in sorted(CURATED_QUERY_MAP, key=lambda v: int(v))
        if k not in set(no_chunks)
    ]
    compiled: List[Dict[str, Any]] = []
    anchor_tiers: Dict[str, int] = {"override": 0, "heuristic": 0, "fallback": 0}
    seen_anchors: set = set()
    skipped_anchor_dup: List[str] = []
    for index, doc_id in enumerate(ordered_ids):
        entry = CURATED_QUERY_MAP[doc_id]
        chunk, must_contain, tier = resolve_anchor(
            doc_id, chunks_by_doc[doc_id], exclude_anchors=seen_anchors
        )
        # 统一上限：超长锚句截断后仍为 chunk 文本的逐字子串，保证可校验。
        if len(must_contain) > 120:
            must_contain = must_contain[:120]
        if must_contain in seen_anchors:
            # 截断等极端情况下仍撞车：跳过该文档并留痕，保证锚句全局唯一。
            skipped_anchor_dup.append(doc_id)
            continue
        seen_anchors.add(must_contain)
        anchor_tiers[tier] += 1
        compiled.append(
            {
                "case_key": f"curag-{len(compiled) + 1:04d}",
                "category": "retrieval_supported",
                "difficulty": entry["difficulty"],
                "query": entry["query"],
                "expected_status": "supported",
                "evidence": [
                    {
                        "document_id": doc_id,
                        "title": str(chunk.get("title") or ""),
                        "chunk_id": str(chunk["point_id"]),
                        "start_line": int(chunk["start_line"]),
                        "end_line": int(chunk["end_line"]),
                        "corpus_version": DEFAULT_PUBLIC_CORPUS_VERSION,
                        "role": "primary",
                        "must_contain": must_contain,
                    }
                ],
                "tags": ["llm_curated", "production_corpus"],
                "rationale": (
                    f"LLM 手写 query，锚定文档 {doc_id} 的真实分块 "
                    f"{chunk['point_id']}（第 {chunk['start_line']}-"
                    f"{chunk['end_line']} 行）。"
                ),
            }
        )
    return compiled, anchor_tiers, no_chunks, skipped_anchor_dup


def render_module(specs: List[Dict[str, Any]], export_meta: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# -*- coding: utf-8 -*-")
    lines.append('r"""人工策展的全覆盖生产语料 RAG 评测集 v1（LLM 逐篇手写 query）。')
    lines.append("")
    lines.append("来源快照：")
    lines.append(f"- 导出时间：{export_meta.get('exported_at')}")
    lines.append(f"- collection：{export_meta.get('collection')}")
    lines.append(f"- 语料规模：{export_meta.get('document_count')} 篇文档 / "
                 f"{export_meta.get('chunk_count')} 个分块")
    lines.append(f"- 本集用例：{len(specs)} 条（每篇真实文档一条）")
    lines.append("")
    lines.append("约束：")
    lines.append("- query 全部由 LLM 阅读真实文档后手写，非模板生成；")
    lines.append("- 每条锚句经 build_curated_rag_eval 对照真实分块逐字校验；")
    lines.append("- chunk_id/start_line/end_line 直接来自真实索引 payload；")
    lines.append("- 再生成命令：venv\\Scripts\\python.exe -m "
                 "app.scripts.build_curated_rag_eval")
    lines.append('"""')
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from typing import Any, Dict, List, Tuple")
    lines.append("")
    lines.append("from app.services.rag_core.evaluation_contracts import EvaluationCase")
    lines.append("")
    lines.append("RAW_SPECS: List[Dict[str, Any]] = [")
    for spec in specs:
        lines.append("    {")
        lines.append(f"        \"case_key\": \"{spec['case_key']}\",")
        lines.append(f"        \"category\": \"{spec['category']}\",")
        lines.append(f"        \"difficulty\": \"{spec['difficulty']}\",")
        lines.append(f"        \"query\": {json.dumps(spec['query'], ensure_ascii=False)},")
        lines.append(f"        \"expected_status\": \"{spec['expected_status']}\",")
        lines.append("        \"evidence\": [")
        evidence = spec["evidence"][0]
        lines.append("            {")
        lines.append(f"                \"document_id\": \"{evidence['document_id']}\",")
        lines.append(
            f"                \"title\": {json.dumps(evidence['title'], ensure_ascii=False)},"
        )
        lines.append(f"                \"chunk_id\": \"{evidence['chunk_id']}\",")
        lines.append(f"                \"start_line\": {evidence['start_line']},")
        lines.append(f"                \"end_line\": {evidence['end_line']},")
        lines.append(f"                \"corpus_version\": \"{evidence['corpus_version']}\",")
        lines.append(f"                \"role\": \"{evidence['role']}\",")
        lines.append(
            f"                \"must_contain\": "
            f"{json.dumps(evidence['must_contain'], ensure_ascii=False)},"
        )
        lines.append("            }")
        lines.append("        ],")
        lines.append(f"        \"tags\": {[str(tag) for tag in spec['tags']]},")
        lines.append(
            f"        \"rationale\": {json.dumps(spec['rationale'], ensure_ascii=False)},"
        )
        lines.append("    },")
    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append("def build_production_curated_evaluation_cases() -> Tuple[EvaluationCase, ...]:")
    lines.append("    \"\"\"把预定位的真实证据编译为 EvaluationCase（不重新分块）。\"\"\"")
    lines.append("    cases: List[EvaluationCase] = []")
    lines.append("    for index, spec in enumerate(RAW_SPECS):")
    lines.append("        cases.append(")
    lines.append("            EvaluationCase(")
    lines.append("                case_id=index + 1,")
    lines.append("                case_key=spec[\"case_key\"],")
    lines.append("                category=spec[\"category\"],")
    lines.append("                difficulty=spec[\"difficulty\"],")
    lines.append("                expected_document_ids=tuple(")
    lines.append("                    ev[\"document_id\"] for ev in spec[\"evidence\"]")
    lines.append("                ),")
    lines.append("                expected_status=spec[\"expected_status\"],")
    lines.append("                review_note=spec[\"rationale\"],")
    lines.append("                query=spec[\"query\"],")
    lines.append("                expected_evidence=tuple(spec[\"evidence\"]),")
    lines.append("                tags=tuple(spec.get(\"tags\", [])),")
    lines.append("            )")
    lines.append("        )")
    lines.append("    return tuple(cases)")
    lines.append("")
    lines.append("")
    lines.append("PRODUCTION_CURATED_EVALUATION_CASES: Tuple[EvaluationCase, ...] = (")
    lines.append("    build_production_curated_evaluation_cases()")
    lines.append(")")
    lines.append("")
    lines.append("__all__ = [")
    lines.append("    \"RAW_SPECS\",")
    lines.append("    \"build_production_curated_evaluation_cases\",")
    lines.append("    \"PRODUCTION_CURATED_EVALUATION_CASES\",")
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = build_argument_parser().parse_args()
    export_path = Path(args.export).resolve() if args.export else DEFAULT_EXPORT_PATH
    output_path = Path(args.output).resolve() if args.output else DEFAULT_OUTPUT_PATH

    export = json.loads(export_path.read_text(encoding="utf-8"))
    specs, anchor_tiers, no_chunks, skipped_anchor_dup = compile_specs(export)
    output_path.write_text(
        render_module(specs, export),
        encoding="utf-8",
        newline="\n",
    )

    difficulties: Dict[str, int] = {}
    for spec in specs:
        difficulties[spec["difficulty"]] = difficulties.get(spec["difficulty"], 0) + 1
    print(
        json.dumps(
            {
                "output": str(output_path),
                "cases": len(specs),
                "distinct_documents": len(
                    {s["evidence"][0]["document_id"] for s in specs}
                ),
                "difficulties": difficulties,
                "anchor_tiers": anchor_tiers,
                "skipped_no_chunks": no_chunks,
                "skipped_anchor_dup": skipped_anchor_dup,
                "generated_at": datetime.utcnow().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
