"""inventory_snapshot tool: real snapshot metadata inventory, never source content."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.models.security import ProjectSnapshot
from app.services.security_agent.tools.contracts import (
    ToolExecutionContext,
    ToolExecutionError,
    ToolResult,
)

LANGUAGE_EXTENSIONS = {
    "python": {".py", ".pyi"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx"},
    "java": {".java", ".gradle", ".kt", ".kts"},
    "go": {".go"},
    "php": {".php", ".phtml"},
    "ruby": {".rb", ".rake"},
    "rust": {".rs"},
    "c_cpp": {".c", ".h", ".cc", ".cpp", ".hpp", ".cxx", ".hxx"},
    "shell": {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".fish"},
    "sql": {".sql"},
    "markup": {".html", ".htm", ".xml", ".vue", ".svelte", ".md", ".rst"},
    "config": {
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".properties",
        ".env",
    },
}

MAX_INVENTORY_EXTENSION_KINDS = 40


def _walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file():
            files.append(path)
    return files


def build_inventory_handler():
    def inventory_snapshot(ctx: ToolExecutionContext) -> ToolResult:
        if ctx.cancelled():
            return ToolResult(status="failed", summary="任务已取消，未执行清点", error_code="AGENT_TOOL_FAILED")

        snapshot = ProjectSnapshot.query.filter_by(id=ctx.snapshot_id).first()
        if snapshot is None or not snapshot.storage_path:
            raise ToolExecutionError("快照存储路径缺失，无法清点")

        root = Path(snapshot.storage_path).resolve()
        if not root.is_dir():
            raise ToolExecutionError("快照存储目录不存在或不可读")

        files = _walk_files(root)
        total_bytes = 0
        extension_counts: Counter = Counter()
        for path in files:
            total_bytes += path.stat().st_size
            extension_counts[path.suffix.lower()] += 1

        languages: dict[str, int] = {}
        for extension, count in extension_counts.items():
            for language, extensions in LANGUAGE_EXTENSIONS.items():
                if extension in extensions:
                    languages[language] = languages.get(language, 0) + count
                    break
        language_summary = dict(
            sorted(languages.items(), key=lambda item: item[1], reverse=True)
        )
        top_extensions = extension_counts.most_common(MAX_INVENTORY_EXTENSION_KINDS)
        directory_counts = Counter(path.relative_to(root).parts[0] for path in files if len(path.relative_to(root).parts) > 1)
        top_directories = dict(directory_counts.most_common(20))

        payload = {
            "file_count": len(files),
            "total_bytes": total_bytes,
            "languages": language_summary,
            "top_extensions": [{"extension": ext, "count": count} for ext, count in top_extensions],
            "top_directories": top_directories,
        }
        return ToolResult(
            status="succeeded",
            summary=f"清点完成：{len(files)} 个文件，{total_bytes} 字节，"
            f"识别语言 {', '.join(language_summary.keys()) if language_summary else '未识别'}",
            artifact_refs=[
                {
                    "artifact_type": "inventory_report",
                    "summary": f"{len(files)} files, {total_bytes} bytes",
                }
            ],
            metrics=payload,
        )

    return inventory_snapshot
