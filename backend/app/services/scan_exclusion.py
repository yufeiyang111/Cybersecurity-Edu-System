"""项目级扫描排除规则：gitignore 风格匹配器（无外部依赖）。

规则按声明顺序逐条匹配，最后匹配的规则决定结果（与 .gitignore 一致）。
支持：注释行、空行、`!` 取反、尾部 `/` 目录规则、前导/内含 `/` 锚定根、
`*`/`?`/`[...]` 通配符与 `**` 跨目录。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

_STARSTAR_ANY_LEVEL = "\x00"
_STARSTAR_DIR_PREFIX = "\x01"
_STARSTAR_DIR_SUFFIX = "\x02"


@dataclass(frozen=True)
class _CompiledRule:
    regex: re.Pattern[str]
    negated: bool


class GitignoreMatcher:
    """把规则列表编译为相对路径排除判定器。"""

    def __init__(self, rules: Sequence[_CompiledRule]) -> None:
        self._rules = tuple(rules)

    @classmethod
    def from_patterns(cls, patterns: Iterable[str]) -> "GitignoreMatcher":
        """从原始规则行构建；空行、注释和无效行被忽略。"""
        compiled: list[_CompiledRule] = []
        for pattern in patterns:
            rule = _compile_pattern(pattern)
            if rule is not None:
                compiled.append(rule)
        return cls(compiled)

    def is_excluded(self, relative_path: str) -> bool:
        """按最后匹配规则判定路径是否应被排除。"""
        result = False
        for rule in self._rules:
            if rule.regex.match(relative_path):
                result = not rule.negated
        return result

    def excluded_paths(self, relative_paths: Iterable[str]) -> list[str]:
        return [path for path in relative_paths if self.is_excluded(path)]

    @property
    def rule_count(self) -> int:
        return len(self._rules)


def compile_patterns(patterns: Iterable[str]) -> list[str]:
    """返回过滤掉空行/注释后的有效规则行，供存储层做校验。"""
    return [
        pattern
        for pattern in patterns
        if _compile_pattern(pattern) is not None
    ]


def _compile_pattern(pattern: str) -> _CompiledRule | None:
    line = pattern.strip()
    if not line or line.startswith("#"):
        return None

    negated = False
    if line.startswith("!"):
        negated = True
        line = line[1:]
        if not line or line.startswith("#"):
            return None

    is_directory = line.endswith("/")
    line = line.rstrip("/")
    if not line:
        return None

    anchored = line.startswith("/")
    line = line.lstrip("/")
    anchored = anchored or "/" in line

    regex = _pattern_to_regex(line, anchored=anchored, is_directory=is_directory)
    return _CompiledRule(regex=regex, negated=negated)


def _pattern_to_regex(pattern: str, *, anchored: bool, is_directory: bool) -> re.Pattern[str]:
    normalized = (
        pattern.replace("**/", _STARSTAR_DIR_PREFIX)
        .replace("/**", _STARSTAR_DIR_SUFFIX)
        .replace("**", _STARSTAR_ANY_LEVEL)
    )
    inner = _translate_segment(normalized)
    if is_directory:
        inner = f"{inner}(?:/.*)?"
    prefix = "^" if anchored else r"(?:^|.*/)"
    return re.compile(prefix + inner + "$")


def _translate_segment(segment: str) -> str:
    """把含 * ? [...] 的路径段转换为正则（* 与 ? 不跨越 /）。"""
    parts: list[str] = []
    index = 0
    while index < len(segment):
        character = segment[index]
        if character == _STARSTAR_ANY_LEVEL:
            parts.append(".*")
        elif character == _STARSTAR_DIR_PREFIX:
            parts.append(r"(?:.*/)?")
        elif character == _STARSTAR_DIR_SUFFIX:
            parts.append(r"(?:/.*)?")
        elif character == "*":
            parts.append("[^/]*")
        elif character == "?":
            parts.append("[^/]")
        elif character == "[":
            closing = segment.find("]", index + 1)
            if closing == -1:
                parts.append(re.escape(character))
            else:
                char_class = segment[index + 1 : closing]
                parts.append("[" + char_class + "]")
                index = closing
        elif character == "\\":
            index += 1
            parts.append(re.escape(segment[index]) if index < len(segment) else "\\\\")
        else:
            parts.append(re.escape(character))
        index += 1
    return "".join(parts)
