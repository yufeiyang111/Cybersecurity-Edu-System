# -*- coding: utf-8 -*-
"""LLM 供应商响应的编码安全解码（mojibake 检测与自动修复）。

背景：部分网关/供应商（opencode zen、MiniMax 等）响应头缺 charset 时，
requests 的 iter_lines(decode_unicode=True) 按 ISO-8859-1 解码，UTF-8 中文
会被解成乱码（如 "å¼æ·"）。本模块提供两层防护：

1. UTF-8 直解失败（出现替换符）→ 回退 GB18030（覆盖 GBK/GB2312）再试；
2. UTF-8 直解"成功"但文本明显是 Latin-1 误读 UTF-8 的乱码 → 反向修复。

所有供应商适配器（openai_compatible / minimax）的字节解码统一走 safe_decode。
"""
from __future__ import annotations

# Latin-1 误读 UTF-8 时常见的高频产物字符（mojibake 特征）
_MOJIBAKE_CHARS = frozenset(
    "ÃÂÀÁÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝÞß"
    "àáâãäåæçèéêëìíîïñòóôõöùúûüýÿ"
)
_MOJIBAKE_RATIO_THRESHOLD = 0.12
_CJK_MIN = 0.30


def _cjk_ratio(text: str) -> float:
    """文本中 CJK（含扩展区）字符占比。"""
    if not text:
        return 0.0
    count = 0
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf":
            count += 1
    return count / len(text)


def _mojibake_ratio(text: str) -> float:
    """非 ASCII 字符中 mojibake 特征字符占比（避免 JSON 结构 ASCII 稀释）。"""
    non_ascii = [ch for ch in text if ord(ch) > 127]
    if not non_ascii:
        return 0.0
    count = sum(1 for ch in non_ascii if ch in _MOJIBAKE_CHARS)
    return count / len(non_ascii)


def _repair_mojibake(text: str) -> str | None:
    """尝试反向修复 Latin-1 误读 UTF-8/GBK 的乱码文本。

    返回修复后文本；无法可靠修复时返回 None（保持原样）。
    """
    before = _mojibake_ratio(text)
    if before < _MOJIBAKE_RATIO_THRESHOLD:
        return None

    candidates: list[str] = []
    for enc in ("latin-1", "cp1252"):
        try:
            raw = text.encode(enc)
        except UnicodeEncodeError:
            continue
        for target in ("utf-8", "gb18030"):
            try:
                fixed = raw.decode(target)
            except UnicodeDecodeError:
                continue
            if "\ufffd" not in fixed:
                candidates.append(fixed)

    if not candidates:
        return None
    best = min(candidates, key=lambda item: _mojibake_ratio(item))
    if _mojibake_ratio(best) < before * 0.5:
        return best
    return None


def safe_decode(raw: bytes | bytearray | str, *, fallback: str = "gb18030") -> str:
    """把供应商响应内容安全解码为正常文本。

    - bytes/bytearray：先按 UTF-8 解，失败回退 GB18030 等编码；
    - str（可能已是误读的乱码文本）：特征检测后自动反向修复。
    """
    if isinstance(raw, str):
        repaired = _repair_mojibake(raw)
        return repaired if repaired is not None else raw

    text = bytes(raw).decode("utf-8", errors="replace")
    if "\ufffd" not in text:
        repaired = _repair_mojibake(text)
        return repaired if repaired is not None else text
    for enc in (fallback, "gbk", "latin-1"):
        try:
            candidate = bytes(raw).decode(enc)
        except UnicodeDecodeError:
            continue
        if "\ufffd" not in candidate and _cjk_ratio(candidate) >= _CJK_MIN:
            return candidate
    return text
