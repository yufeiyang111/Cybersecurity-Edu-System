# -*- coding: utf-8 -*-
"""从真实语料导出快照生成生产级 RAG 评测集规格模块。

输入：``backend/data/rag_corpus_export.json``（由 ``export_rag_eval_corpus``
生成的只读导出，含 knowledge_items 正文与 Qdrant 分块 payload）。

输出：``app/services/rag_core/datasets/production_rag_eval_v1.py``——
可提交的版本化评测规格。每条用例锚定真实索引中的真实分块：

- gold evidence 直接取自导出 payload 的 chunk_id / start_line / end_line，
  与线上检索索引一字不差；
- 只保存小型 ``must_contain`` 锚句（逐字片段）用于人工审计，
  绝不把知识库正文复制进仓库；
- 抽样与提问模板完全确定性（按 doc id 等距抽样），可复现。

用法（在 backend/ 下）::

    venv\\Scripts\\python.exe -m app.scripts.generate_rag_eval_from_corpus
    venv\\Scripts\\python.exe -m app.scripts.generate_rag_eval_from_corpus --limit 500
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT_PATH = BACKEND_ROOT / "data" / "rag_corpus_export.json"
DEFAULT_OUTPUT_PATH = (
    BACKEND_ROOT / "app" / "services" / "rag_core" / "datasets" / "production_rag_eval_v1.py"
)

CORPUS_VERSION = "knowledge_embeddings-v1"
CASE_KEY_PREFIX = "prag"
DEFAULT_LIMIT = 300

# 锚句评分关键词：命中越多越适合作为「可被提问」的证据句。
_KEYWORD_PATTERN = re.compile(
    r"是|包括|分为|原则|措施|防御|防护|攻击|检测|监测|加固|配置|建议|需要|"
    r"支持|提供|使用|实现|确保|避免|防止|识别|验证|授权|加密|备份|审计|应急"
)
_DEFINITION_PATTERN = re.compile(r"^([^，。；：（()\"']{2,24})是")
_ADVICE_PATTERN = re.compile(r"防御|防护|措施|建议|加固|配置|设置|检查|检测|防范|应对|处理")
_LIST_PATTERN = re.compile(r"包括|分为|类型|种类|步骤|阶段|要素")
_CODE_FENCE_PATTERN = re.compile(r"^\s*```")
_BULLET_PATTERN = re.compile(
    r"^(?:\s*(?:[#>*\-+]+|\d+[.、)]|\[[^\]]*\]))*\s*"
)
_CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]")

MIN_ANCHOR_LEN = 14
MAX_ANCHOR_LEN = 90


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从语料导出快照生成生产级 RAG 评测集规格模块",
    )
    parser.add_argument("--export", default=None, help="导出 JSON 路径（默认 backend/data/rag_corpus_export.json）")
    parser.add_argument("--output", default=None, help="输出规格模块路径")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="目标用例数（默认 300）")
    return parser


def _clean_display(line: str) -> str:
    """去掉 markdown 前缀符号，仅用于启发判断，不影响 must_contain 原文。"""
    return _BULLET_PATTERN.sub("", line).strip()


def _iter_candidate_lines(text: str):
    """遍历分块文本中的正文候选行，跳过代码围栏与无中文行。"""
    inside_fence = False
    for raw_line in text.splitlines():
        if _CODE_FENCE_PATTERN.match(raw_line):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        if "#" in raw_line:
            continue
        cleaned = _clean_display(raw_line)
        if not (MIN_ANCHOR_LEN <= len(cleaned) <= MAX_ANCHOR_LEN):
            continue
        if not _CHINESE_PATTERN.search(cleaned):
            continue
        yield cleaned, raw_line.strip()


def _anchor_score(cleaned: str) -> int:
    score = len(_KEYWORD_PATTERN.findall(cleaned))
    if _DEFINITION_PATTERN.match(cleaned):
        score += 3
    if _ADVICE_PATTERN.search(cleaned):
        score += 2
    if _LIST_PATTERN.search(cleaned):
        score += 1
    return score


def _pick_anchor(
    doc_chunks: List[Dict[str, Any]],
    exclude_anchors: Optional[set] = None,
) -> Optional[Dict[str, Any]]:
    """选出一篇文档中最具信息量的锚句，返回 {chunk, cleaned, raw} 或 None。

    exclude_anchors：跨文档去重用的已占用锚句集合（原文片段），
    命中排除后继续找次优候选，保证评测集内锚句唯一。
    """
    exclude = exclude_anchors or set()
    best = None
    best_score = 0
    for chunk in doc_chunks:
        for cleaned, raw in _iter_candidate_lines(chunk.get("text") or ""):
            if raw in exclude or cleaned in exclude:
                continue
            score = _anchor_score(cleaned)
            if score > best_score:
                best_score = score
                best = {"chunk": chunk, "cleaned": cleaned, "raw": raw}
    return best


def _difficulty_of(cleaned: str) -> str:
    if len(cleaned) > 60:
        return "hard"
    if len(cleaned) >= 24 or re.search(r"\d", cleaned):
        return "medium"
    return "easy"


def _strip_md(fragment: str) -> str:
    """去掉强调/代码标记，仅用于生成提问文本，不影响 must_contain 原文。"""
    return re.sub(r"[*`]+", "", fragment).strip()


def _query_of(title: str, cleaned: str) -> str:
    definition = _DEFINITION_PATTERN.match(cleaned)
    if definition:
        subject = _strip_md(definition.group(1))
        if subject and subject != title.strip():
            return f"什么是{subject}？"
    full_lead = _strip_md(re.split(r"[：:，,。]", cleaned)[0])
    lead = full_lead[:20]
    if (
        lead
        and len(full_lead) <= 20
        and lead != title.strip()
        and _ADVICE_PATTERN.search(cleaned)
    ):
        return f"关于{title}，{lead}应该怎么做？"
    if _LIST_PATTERN.search(cleaned):
        return f"{title}主要涉及哪些方面？"
    return f"{title}的核心要点是什么？"


def select_cases(export: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    """确定性抽样并构造规格条目（等距抽样覆盖全部 doc id 区间）。"""
    chunks_by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for chunk in export.get("chunks", []):
        chunks_by_doc.setdefault(str(chunk["doc_id"]), []).append(chunk)

    doc_ids = sorted(chunks_by_doc, key=lambda value: int(value))
    if not doc_ids:
        raise ValueError("导出文件中没有可用分块")
    if limit <= 0:
        raise ValueError("limit must be positive")

    stride = max(1, len(doc_ids) // limit)
    picked_ids = doc_ids[::stride][:limit]

    specs: List[Dict[str, Any]] = []
    seen_queries = set()
    seen_anchors: set = set()
    for doc_id in picked_ids:
        anchor = _pick_anchor(chunks_by_doc[doc_id], exclude_anchors=seen_anchors)
        if anchor is None:
            continue
        chunk = anchor["chunk"]
        title = str(chunk.get("title") or "")
        query = _query_of(title, anchor["cleaned"])
        if query in seen_queries:
            continue
        seen_queries.add(query)
        seen_anchors.add(anchor["raw"])
        specs.append(
            {
                "case_key": f"{CASE_KEY_PREFIX}-{len(specs) + 1:04d}",
                "category": "retrieval_supported",
                "difficulty": _difficulty_of(anchor["cleaned"]),
                "query": query,
                "expected_status": "supported",
                "evidence": [
                    {
                        "document_id": doc_id,
                        "title": title,
                        "chunk_id": str(chunk["point_id"]),
                        "start_line": int(chunk["start_line"]),
                        "end_line": int(chunk["end_line"]),
                        "corpus_version": CORPUS_VERSION,
                        "role": "primary",
                    }
                ],
                "must_contain": anchor["raw"],
                "tags": ["auto_generated", "production_corpus"],
                "rationale": (
                    f"自动生成：锚定真实分块 {chunk['point_id']}"
                    f"（第 {chunk['start_line']}-{chunk['end_line']} 行）。"
                ),
            }
        )
    return specs


def render_module(specs: List[Dict[str, Any]], export_meta: Dict[str, Any]) -> str:
    """把规格渲染为可提交的 Python 模块源码。"""
    lines: List[str] = []
    lines.append("# -*- coding: utf-8 -*-")
    lines.append('r"""生产公共知识库 RAG 评测集 v1（真实语料快照锚定）。')
    lines.append("")
    lines.append("来源快照：")
    lines.append(f"- 导出时间：{export_meta.get('exported_at')}")
    lines.append(f"- collection：{export_meta.get('collection')}")
    lines.append(f"- 语料规模：{export_meta.get('document_count')} 篇文档 / "
                 f"{export_meta.get('chunk_count')} 个分块")
    lines.append(f"- 本集用例：{len(specs)} 条（等距抽样，确定性可复现）")
    lines.append("")
    lines.append("约束：")
    lines.append("- gold evidence 的 chunk_id/start_line/end_line 直接来自真实索引 payload；")
    lines.append("- must_contain 为语料中的逐字短句，仅用于人工审计，不含大段正文；")
    lines.append("- 再生成命令：venv\\Scripts\\python.exe -m "
                 "app.scripts.generate_rag_eval_from_corpus")
    lines.append('"""')
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from typing import Any, Dict, List, Tuple")
    lines.append("")
    lines.append("from app.services.rag_core.evaluation_contracts import EvaluationCase")
    lines.append("")
    lines.append(f"PRODUCTION_CORPUS_VERSION = \"{CORPUS_VERSION}\"")
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
        lines.append(f"                \"title\": {json.dumps(evidence['title'], ensure_ascii=False)},")
        lines.append(f"                \"chunk_id\": \"{evidence['chunk_id']}\",")
        lines.append(f"                \"start_line\": {evidence['start_line']},")
        lines.append(f"                \"end_line\": {evidence['end_line']},")
        lines.append(f"                \"corpus_version\": \"{evidence['corpus_version']}\",")
        lines.append(f"                \"role\": \"{evidence['role']}\",")
        lines.append(f"                \"must_contain\": "
                     f"{json.dumps(spec['must_contain'], ensure_ascii=False)},")
        lines.append("            }")
        lines.append("        ],")
        lines.append(f"        \"tags\": {[str(tag) for tag in spec['tags']]},")
        lines.append(f"        \"rationale\": {json.dumps(spec['rationale'], ensure_ascii=False)},")
        lines.append("    },")
    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append("def build_production_evaluation_cases() -> Tuple[EvaluationCase, ...]:")
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
    lines.append("PRODUCTION_EVALUATION_CASES: Tuple[EvaluationCase, ...] = (")
    lines.append("    build_production_evaluation_cases()")
    lines.append(")")
    lines.append("")
    lines.append("__all__ = [")
    lines.append("    \"PRODUCTION_CORPUS_VERSION\",")
    lines.append("    \"RAW_SPECS\",")
    lines.append("    \"build_production_evaluation_cases\",")
    lines.append("    \"PRODUCTION_EVALUATION_CASES\",")
    lines.append("]")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = build_argument_parser().parse_args()
    export_path = Path(args.export).resolve() if args.export else DEFAULT_EXPORT_PATH
    output_path = Path(args.output).resolve() if args.output else DEFAULT_OUTPUT_PATH

    export = json.loads(export_path.read_text(encoding="utf-8"))
    specs = select_cases(export, args.limit)
    source = render_module(specs, export)
    output_path.write_text(source, encoding="utf-8", newline="\n")

    difficulties: Dict[str, int] = {}
    for spec in specs:
        difficulties[spec["difficulty"]] = difficulties.get(spec["difficulty"], 0) + 1
    print(
        json.dumps(
            {
                "output": str(output_path),
                "cases": len(specs),
                "distinct_documents": len({s["evidence"][0]["document_id"] for s in specs}),
                "difficulties": difficulties,
                "generated_at": datetime.utcnow().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
