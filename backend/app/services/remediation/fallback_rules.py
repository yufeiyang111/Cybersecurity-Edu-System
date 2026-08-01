"""Deterministic, evidence-constrained remediation fallbacks."""
from __future__ import annotations

from difflib import unified_diff
import re

from app.models.security import SecurityFinding
from app.services.security_knowledge import _redact_text

from .context import _value
from .patch_validator import validate_unified_patch
from .types import _CodeContext

def _rule_based_fallback(
    finding: SecurityFinding,
    snapshot_storage_path: str | None,
    context: _CodeContext,
    *,
    max_patch_lines: int,
    max_patch_chars: int,
) -> tuple[str, list[str], str | None, list[str]]:
    rule_id = finding.rule_id
    if rule_id == "PY-FLASK-DEBUG":
        patch_diff, patch_warnings = _generate_local_patch(
            snapshot_storage_path,
            context,
            replacement=lambda line: re.sub(r"\bdebug\s*=\s*True\b", "debug=False", line, count=1),
        )
        warnings = list(patch_warnings)
        if patch_diff is None:
            warnings.append("RULE_BASED_NO_PATCH")
        return (
            "该调用在代码中显式启用了 Flask 调试模式；生产环境应关闭调试器并通过受控配置管理运行参数。",
            [
                "将 app.run 的 debug 参数设置为 False。",
                "在部署配置中显式设置生产环境，并确认调试器不会对外暴露。",
                "在预发布环境验证应用启动、错误处理和日志行为。",
            ],
            _validated_patch(
                snapshot_storage_path,
                context.file_path,
                patch_diff,
                max_patch_lines,
                max_patch_chars,
                warnings,
            ),
            warnings,
        )
    if rule_id == "PY-YAML-UNSAFE-LOAD":
        patch_diff, patch_warnings = _generate_local_patch(
            snapshot_storage_path,
            context,
            replacement=lambda line: re.sub(r"\byaml\.load\s*\(", "yaml.safe_load(", line, count=1),
        )
        warnings = list(patch_warnings)
        if patch_diff is None:
            warnings.append("RULE_BASED_NO_PATCH")
        return (
            "yaml.load 未指定安全 Loader，反序列化不可信内容时可能执行危险构造。",
            [
                "优先使用 yaml.safe_load 解析不可信 YAML。",
                "若确需自定义类型，显式使用受限 Loader 并验证输入来源。",
                "为恶意 YAML 样本补充回归测试。",
            ],
            _validated_patch(
                snapshot_storage_path,
                context.file_path,
                patch_diff,
                max_patch_lines,
                max_patch_chars,
                warnings,
            ),
            warnings,
        )

    return (
        "该发现需要结合业务语义和调用链人工确认；系统不会生成可能改变业务行为的自动补丁。",
        [
            "核对 Finding 对应的代码、依赖或配置证据。",
            "结合业务输入边界评估可利用性与修复影响。",
            "在独立分支编写、审查并测试修复后再合并。",
        ],
        None,
        ["RULE_BASED_NO_PATCH"],
    )


def _generate_local_patch(
    snapshot_storage_path: str | None,
    context: _CodeContext,
    *,
    replacement: callable,
) -> tuple[str | None, tuple[str, ...]]:
    if not context.raw_lines or not context.file_path:
        return None, ("PATCH_CONTEXT_UNAVAILABLE",)
    if any(_redact_text(line) != line for line in context.raw_lines):
        return None, ("PATCH_CONTEXT_SENSITIVE",)

    before = list(context.raw_lines)
    after = list(before)
    changed = False
    for index, line in enumerate(after):
        replacement_line = replacement(line)
        if replacement_line != line:
            after[index] = replacement_line
            changed = True
            break
    if not changed:
        return None, ("PATCH_TARGET_PATTERN_NOT_FOUND",)

    diff_lines = list(
        unified_diff(
            before,
            after,
            fromfile=f"a/{context.file_path}",
            tofile=f"b/{context.file_path}",
            n=2,
            lineterm="",
        )
    )
    hunk_index = next((index for index, line in enumerate(diff_lines) if line.startswith("@@ ")), None)
    if hunk_index is None:
        return None, ("PATCH_FORMAT_INVALID",)
    old_count = len(before)
    new_count = len(after)
    diff_lines[hunk_index] = (
        f"@@ -{_hunk_range(context.first_line, old_count)} "
        f"+{_hunk_range(context.first_line, new_count)} @@"
    )
    return "\n".join(diff_lines) + "\n", ()


def _hunk_range(start: int, count: int) -> str:
    return str(start) if count == 1 else f"{start},{count}"


def _validated_patch(
    snapshot_storage_path: str | None,
    file_path: str,
    patch_diff: str | None,
    max_lines: int,
    max_chars: int,
    warnings: list[str],
) -> str | None:
    if patch_diff is None:
        return None
    result = validate_unified_patch(
        snapshot_storage_path or "",
        file_path,
        patch_diff,
        max_lines=max_lines,
        max_chars=max_chars,
    )
    warnings.extend(result.warning_codes)
    return result.patch_diff if result.is_valid else None


