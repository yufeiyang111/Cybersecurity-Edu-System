# -*- coding: utf-8 -*-
"""Observation 校验器（A6）：拒绝伪造行号、非法路径、无证据结论。"""
from __future__ import annotations

import posixpath
import re

from app.models.agent_review import ObservationConfidence

MAX_TITLE_CHARS = 500
MAX_SUMMARY_CHARS = 8000
MAX_CWE_CHARS = 32
MAX_LOCATIONS = 20
MAX_PROOF_GAPS = 10

_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._~@()\[\]-]+$")


class ObservationValidationError(ValueError):
    pass


def validate_observation(
    payload: dict,
    *,
    allowed_code_slices: tuple[object, ...] | None = None,
    require_code_evidence: bool = False,
) -> dict:
    """校验并规范化 observation 输入；返回规整后的字典或抛异常。

    Deep Review 可传入本次 Context Pack 的代码切片，以拒绝模型伪造路径或行号。
    """
    if not isinstance(payload, dict):
        raise ObservationValidationError("observation 必须是对象")

    title = str(payload.get("title") or "").strip()
    if not title:
        raise ObservationValidationError("title 不能为空")
    if len(title) > MAX_TITLE_CHARS:
        raise ObservationValidationError(f"title 不能超过 {MAX_TITLE_CHARS} 字符")

    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise ObservationValidationError("summary 不能为空")
    if len(summary) > MAX_SUMMARY_CHARS:
        raise ObservationValidationError(f"summary 不能超过 {MAX_SUMMARY_CHARS} 字符")

    confidence = str(payload.get("confidence") or ObservationConfidence.LOW.value)
    if confidence not in {item.value for item in ObservationConfidence}:
        raise ObservationValidationError("confidence 必须是 low/medium/high")

    cwe_id = str(payload.get("cwe_id") or "").strip() or None
    if cwe_id is not None and len(cwe_id) > MAX_CWE_CHARS:
        raise ObservationValidationError(f"cwe_id 不能超过 {MAX_CWE_CHARS} 字符")

    locations_raw = payload.get("locations") or []
    if not isinstance(locations_raw, list):
        raise ObservationValidationError("locations 必须是数组")
    if len(locations_raw) > MAX_LOCATIONS:
        raise ObservationValidationError(f"locations 不能超过 {MAX_LOCATIONS} 个")

    citations_raw = payload.get("citations") or []
    if not isinstance(citations_raw, list):
        raise ObservationValidationError("citations 必须是数组")
    if not locations_raw and not citations_raw and not require_code_evidence:
        raise ObservationValidationError("缺少证据：必须至少提供一个受影响位置或引用")

    locations = [_validate_location(item) for item in locations_raw]
    if allowed_code_slices is not None:
        _validate_locations_within_scope(locations, allowed_code_slices)

    proof_gaps = payload.get("proof_gaps") or []
    if not isinstance(proof_gaps, list):
        raise ObservationValidationError("proof_gaps 必须是数组")
    if len(proof_gaps) > MAX_PROOF_GAPS:
        raise ObservationValidationError(f"proof_gaps 不能超过 {MAX_PROOF_GAPS} 个")
    proof_gaps = [str(item)[:500] for item in proof_gaps]

    needs_more_evidence = False
    if require_code_evidence and not locations:
        if confidence != ObservationConfidence.LOW.value:
            raise ObservationValidationError("缺少代码位置时 confidence 必须为 low")
        if not proof_gaps:
            raise ObservationValidationError("缺少代码位置时必须说明 proof_gaps")
        needs_more_evidence = True

    return {
        "title": title,
        "summary": summary,
        "confidence": confidence,
        "cwe_id": cwe_id,
        "locations": locations,
        "citations": citations_raw,
        "proof_gaps": proof_gaps,
        "needs_more_evidence": needs_more_evidence,
        "detail": payload.get("detail") if isinstance(payload.get("detail"), dict) else {},
    }

def _validate_location(item) -> dict:
    if not isinstance(item, dict):
        raise ObservationValidationError("location 必须是对象")
    file_path = str(item.get("file_path") or "").strip()
    if not file_path:
        raise ObservationValidationError("location.file_path 不能为空")
    _reject_unsafe_path(file_path)
    try:
        start_line = int(item.get("start_line"))
    except (TypeError, ValueError):
        raise ObservationValidationError("location.start_line 必须是正整数")
    if start_line <= 0:
        raise ObservationValidationError("location.start_line 必须是正整数")
    end_line = None
    if item.get("end_line") is not None:
        try:
            end_line = int(item["end_line"])
        except (TypeError, ValueError):
            raise ObservationValidationError("location.end_line 必须是正整数")
        if end_line < start_line:
            raise ObservationValidationError("location.end_line 不能小于 start_line")
    role = str(item.get("role") or "evidence").strip()[:32] or "evidence"
    return {
        "file_path": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "role": role,
    }


def _reject_unsafe_path(file_path: str) -> None:
    if file_path.startswith("/") or "\\" in file_path or file_path.startswith("~"):
        raise ObservationValidationError(f"location.file_path 非法：{file_path[:80]}")
    normalized = posixpath.normpath(file_path)
    if normalized.startswith("..") or "/../" in f"/{normalized}":
        raise ObservationValidationError(f"location.file_path 非法（路径逃逸）：{file_path[:80]}")
    for segment in normalized.split("/"):
        if segment and not _PATH_SEGMENT.match(segment):
            raise ObservationValidationError(f"location.file_path 含非法字符：{file_path[:80]}")


def _validate_locations_within_scope(
    locations: list[dict], allowed_code_slices: tuple[object, ...]
) -> None:
    """确保模型位置完全落在本次 Context Pack 授权的代码切片中。"""
    allowed_ranges: list[tuple[str, int, int]] = []
    for evidence in allowed_code_slices:
        file_path = str(getattr(evidence, "file_path", "") or "").strip()
        start_line = getattr(evidence, "start_line", None)
        end_line = getattr(evidence, "end_line", None)
        if not file_path:
            continue
        try:
            start_line = int(start_line)
            end_line = int(end_line)
        except (TypeError, ValueError):
            continue
        if start_line > 0 and end_line >= start_line:
            allowed_ranges.append((file_path, start_line, end_line))

    for location in locations:
        location_end = location["end_line"] or location["start_line"]
        is_allowed = any(
            file_path == location["file_path"]
            and scope_start <= location["start_line"]
            and location_end <= scope_end
            for file_path, scope_start, scope_end in allowed_ranges
        )
        if not is_allowed:
            raise ObservationValidationError(
                "location 不在本次授权代码证据范围内："
                f"{location['file_path']} 第 {location['start_line']}-{location_end} 行"
            )
