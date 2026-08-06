"""File classification for scan coverage: text/binary detection and language hints.

Pure helpers shared by the snapshot catalog and the receipt writer.
"""
from __future__ import annotations

from pathlib import Path

LANGUAGE_EXTENSIONS = {
    "python": {".py", ".pyi"},
    "javascript": {".js", ".jsx", ".mjs", ".cjs"},
    "typescript": {".ts", ".tsx"},
    "java": {".java"},
    "go": {".go"},
    "php": {".php", ".phtml"},
    "ruby": {".rb"},
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

# Extensions that can never be usefully scanned as text.
NON_TEXT_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".svg",
        ".webp",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".zip",
        ".gz",
        ".tar",
        ".7z",
        ".rar",
        ".jar",
        ".war",
        ".class",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".o",
        ".a",
        ".pyc",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp3",
        ".mp4",
        ".avi",
        ".mov",
        ".wav",
        ".bin",
        ".dat",
        ".db",
        ".sqlite",
        ".min.js",
    }
)

BINARY_SNIPPET = b"\x00\x1f\x8b\xff\xd8\xff\xd9\x89PNG"

_TEXT_DECODE_BUDGET = 8192


def detect_text(path: Path) -> bool:
    """Best-effort text detection: known binary extensions lose, then magic bytes,
    then a UTF-8/GBK/Latin-1 decode attempt over the file head."""
    suffix = path.suffix.lower()
    if suffix in NON_TEXT_EXTENSIONS or suffix.endswith((".min.js", ".min.css")):
        return False
    try:
        with path.open("rb") as handle:
            head = handle.read(_TEXT_DECODE_BUDGET)
    except OSError:
        return False
    if not head:
        return True
    if head[:4] in {b"\x89PNG", b"\xff\xd8\xff\xe0", b"\x00\x00\x01\x00", b"\x1f\x8b\x08"}:
        return False
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            head.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


def detect_language(extension: str) -> str | None:
    """Map a file extension to the coarse language bucket used for coverage."""
    for language, extensions in LANGUAGE_EXTENSIONS.items():
        if extension in extensions:
            return language
    return None
