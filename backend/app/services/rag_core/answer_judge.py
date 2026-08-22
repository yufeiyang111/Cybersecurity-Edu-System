# -*- coding: utf-8 -*-
"""LLM-as-judge：对 RAG 评测回答做忠实度与相关性评分（1-5 整数制）。

评审只依据当次证据片段，不使用外部知识；输出强制 JSON，
解析失败会标记 ok=False 并保留原始文本供人工复核。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from app.services.llm.contracts import LLMRequest

MAX_EVIDENCE_CHARS = 400
MAX_REFERENCES = 6
_MAX_ANSWER_CHARS = 2000
_SCORE_KEYS = ("faithfulness", "relevancy")

_JUDGE_SYSTEM = (
    "你是严格的 RAG 质量评审员。只依据给出的证据片段评估回答，"
    "不使用任何外部知识。必须只输出一个 JSON 对象，不要输出其他文字。"
)


@dataclass(frozen=True)
class JudgeVerdict:
    """单题评审结果；分数已归一化到 0~1，raw 为模型原始 1-5 整数。"""

    faithfulness: float | None
    relevancy: float | None
    faithfulness_raw: int | None = None
    relevancy_raw: int | None = None
    reason: str = ""
    ok: bool = False

    def to_payload(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "faithfulness": self.faithfulness,
            "relevancy": self.relevancy,
            "faithfulness_raw": self.faithfulness_raw,
            "relevancy_raw": self.relevancy_raw,
            "reason": self.reason,
        }


def _ref_field(ref: Any, name: str, default: Any = None) -> Any:
    """兼容两种引用形态：EvidenceReference 对象 / 序列化后的 dict。"""
    if isinstance(ref, dict):
        return ref.get(name, default)
    return getattr(ref, name, default)


def build_judge_request(
    query: str,
    answer: str,
    references: Sequence[Any],
) -> LLMRequest:
    """构造评审请求：问题 + 回答 + 截断后的证据片段（引用编号/标题/行号）。"""
    lines: list[str] = []
    for ref in list(references)[:MAX_REFERENCES]:
        content = re.sub(r"\s+", " ", _ref_field(ref, "content", "") or "").strip()
        if len(content) > MAX_EVIDENCE_CHARS:
            content = content[:MAX_EVIDENCE_CHARS] + "…"
        if not content:
            continue
        lines.append(
            f"[{_ref_field(ref, 'citation_id', '')}|"
            f"{_ref_field(ref, 'title', '')}|"
            f"{_ref_field(ref, 'start_line', None)}-{_ref_field(ref, 'end_line', None)}] {content}"
        )
    evidence_block = "\n".join(lines) if lines else "（无证据片段）"

    answer_text = re.sub(r"\s+", " ", answer or "").strip()
    if len(answer_text) > _MAX_ANSWER_CHARS:
        answer_text = answer_text[:_MAX_ANSWER_CHARS] + "…"

    user_prompt = (
        f"## 问题\n{query}\n\n"
        f"## 回答\n{answer_text}\n\n"
        f"## 证据片段\n{evidence_block}\n\n"
        "## 评分标准（1-5 整数）\n"
        "faithfulness 忠实度：5=全部断言有证据支持；3=部分断言无据或夸大；"
        "1=主要结论与证据相悖或凭空编造\n"
        "relevancy 相关性：5=完整切题并覆盖问题要点；3=部分切题；1=答非所问\n\n"
        '只输出 JSON：{"faithfulness": <1-5>, "relevancy": <1-5>, '
        '"reason": "<=40字"}'
    )
    return LLMRequest(
        prompt=user_prompt,
        system_prompt=_JUDGE_SYSTEM,
        temperature=0.0,
        # 思考型模型（如 MiniMax-M2.x）会先输出推理再给结论，预算需留足。
        max_tokens=2048,
    )


def parse_verdict(text: str) -> JudgeVerdict:
    """从模型输出解析评审 JSON；失败返回 ok=False 的占位结果。"""
    raw = (text or "").strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        try:
            payload = json.loads(match.group(0))
            scores: dict[str, int | None] = {}
            for key in _SCORE_KEYS:
                value = payload.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    scores[key] = None
                else:
                    scores[key] = max(1, min(5, round(float(value))))
            reason = str(payload.get("reason") or "").strip()[:80]
            ok = all(scores[key] is not None for key in _SCORE_KEYS)
            if ok:
                return JudgeVerdict(
                    faithfulness=round(scores["faithfulness"] / 5, 3),
                    relevancy=round(scores["relevancy"] / 5, 3),
                    faithfulness_raw=scores["faithfulness"],
                    relevancy_raw=scores["relevancy"],
                    reason=reason,
                    ok=True,
                )
            return JudgeVerdict(reason="missing_score_fields", ok=False)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return JudgeVerdict(reason="parse_error", ok=False)


def judge_answer(
    query: str,
    answer: str,
    references: Sequence[Any],
    provider: Any,
) -> dict[str, Any]:
    """调用 Provider 完成单题评审；异常与失败都折叠进可序列化结果。"""
    try:
        request = build_judge_request(query, answer, references)
        response = provider.generate(request)
    except Exception as exc:  # noqa: BLE001 - 调用方仅依赖返回结构
        return {"ok": False, "error": f"{type(exc).__name__}"}
    if not getattr(response, "is_success", False):
        warning = getattr(response, "warning_code", None) or getattr(response, "status_code", None)
        return {"ok": False, "error": f"llm_{warning}"}
    verdict = parse_verdict(response.text or "")
    payload = verdict.to_payload()
    payload["model"] = getattr(response, "model", None)
    return payload


def aggregate(verdicts: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总一批评审结果：均值、分布与成功率。"""
    rows = [v for v in verdicts if v.get("ok")]
    total = len(list(verdicts)) if not isinstance(verdicts, list) else len(verdicts)

    def _mean(key: str) -> float | None:
        values = [v[key] for v in rows if isinstance(v.get(key), (int, float))]
        return round(sum(values) / len(values), 4) if values else None

    distribution: dict[str, int] = {}
    for v in rows:
        bucket = str(v.get("faithfulness_raw"))
        distribution[bucket] = distribution.get(bucket, 0) + 1
    return {
        "judged_total": total,
        "judged_ok": len(rows),
        "faithfulness_mean": _mean("faithfulness"),
        "relevancy_mean": _mean("relevancy"),
        "faithfulness_distribution": distribution,
    }
