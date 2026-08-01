"""确定性 Scanner 的兼容基类和原始 Finding 契约。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
        """默认没有语言专属 Secret 规则。"""
        return []
