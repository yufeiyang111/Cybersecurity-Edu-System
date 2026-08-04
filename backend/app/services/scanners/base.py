"""确定性 Scanner 的兼容基类和原始 Finding 契约。"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RawFinding:
    """Scanner 输出的未持久化 Finding；证据必须已经脱敏。"""

    rule_id: str
    category: str
    severity: str
    cwe_id: str | None
    file_path: str
    start_line: int
    end_line: int
    message: str
    evidence_preview: str
    secret_sha256: str | None = None
    confidence: float = 1.0
    cve_id: str | None = None
    source_type: str | None = None
    rule_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectProfile:
    language: str
    framework_hints: list[str]
    manifest_paths: list[str]


SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|token|password|passwd|access[_-]?key)\b\s*=\s*(['\"])(?P<value>[^'\"\r\n]{8,})\1"
)
_SECRET_CANDIDATE_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".c",
        ".h",
        ".cpp",
        ".cs",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
        ".properties",
        ".env",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".bat",
        ".cmd",
        ".sql",
        ".txt",
        ".md",
        ".gradle",
        ".kts",
    }
)
_SECRET_CANDIDATE_FILENAMES = frozenset(
    {".env", ".env.example", ".npmrc", ".pypirc", ".gitconfig", ".htaccess", "credentials", "credential"}
)


class BaseLanguageScanner(ABC):
    """只读 Scanner 基类；实现不得执行快照中的源代码。"""

    language: str = "unknown"
    scanner_name: str = ""
    scanner_version: str = "1.0.0"
    supported_languages: tuple[str, ...] = ()
    categories: tuple[str, ...] = ("sast",)

    @abstractmethod
    def can_handle(self, snapshot_root: Path) -> bool:
        """判断当前 Scanner 是否识别该项目。"""

    @abstractmethod
    def detect_project(self, snapshot_root: Path) -> ProjectProfile:
        """只根据文件名和文本返回项目元数据。"""

    @abstractmethod
    def run_sast(self, snapshot_root: Path) -> list[RawFinding]:
        """返回确定性的静态分析结果。"""

    def run_secret_scan(self, snapshot_root: Path) -> list[RawFinding]:
        """跨语言通用硬编码密钥扫描；证据已脱敏。"""
        findings: list[RawFinding] = []
        for source_file in self._secret_candidate_files(snapshot_root):
            text = self.read_text_detected(source_file)
            if text is None:
                continue
            relative_path = source_file.relative_to(snapshot_root).as_posix()
            for line_number, line in enumerate(text.splitlines(), start=1):
                match = SECRET_ASSIGNMENT.search(line)
                if match is None:
                    continue
                secret = match.group("value")
                findings.append(
                    RawFinding(
                        rule_id="GENERIC-HARDCODED-SECRET",
                        category="secret",
                        severity="high",
                        cwe_id="CWE-798",
                        file_path=relative_path,
                        start_line=line_number,
                        end_line=line_number,
                        message="检测到疑似硬编码敏感信息，请移至受控密钥管理或环境变量。",
                        evidence_preview=_mask_secret(secret),
                        secret_sha256=sha256(secret.encode("utf-8")).hexdigest(),
                    )
                )
        return findings

    @staticmethod
    def read_text_detected(path: Path) -> str | None:
        """按 UTF-8 → GBK → Latin-1 兜底解码文本；二进制安全失败返回 None。"""
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except (OSError, UnicodeDecodeError):
                continue
        return None

    @staticmethod
    def _secret_candidate_files(snapshot_root: Path) -> list[Path]:
        return sorted(
            path
            for path in snapshot_root.rglob("*")
            if path.is_file()
            and (
                path.suffix.lower() in _SECRET_CANDIDATE_SUFFIXES
                or path.name.lower() in _SECRET_CANDIDATE_FILENAMES
            )
        )


def _mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}***{secret[-4:]}"
