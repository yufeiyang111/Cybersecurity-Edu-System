"""Read-only Go baseline security scanner.

The scanner processes source text with encoding fallback. It never invokes the
Go toolchain or executes scanned project code.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.services.scanners.base import BaseLanguageScanner, ProjectProfile, RawFinding


GO_MANIFESTS = ("go.mod", "go.sum")
GO_SUFFIXES = {".go"}
FRAMEWORK_IMPORT_PATHS = {
    "gin-gonic/gin": "gin",
    "labstack/echo": "echo",
    "gofiber/fiber": "fiber",
    "go-chi/chi": "chi",
}
EXEC_SHELL_PATTERN = re.compile(r"\bexec\.Command\s*\(\s*['\"](?:sh|bash|dash|cmd|cmd\.exe|powershell|pwsh)['\"]")
MD5_USE_PATTERN = re.compile(r"\b(?:crypto/md5|md5\.(?:New|Sum|Sum128|Sum256|Sum512))\b")
INSECURE_TLS_PATTERN = re.compile(r"\bInsecureSkipVerify\s*:\s*true\b")


class GoScanner(BaseLanguageScanner):
    """Deterministic Go scanner using bounded, line-local text rules."""

    language = "go"
    scanner_name = "go-baseline"
    scanner_version = "1.0.0"
    supported_languages = ("go",)
    categories = ("sast", "secret")

    def can_handle(self, snapshot_root: Path) -> bool:
        return bool(self._source_files(snapshot_root)) or any(
            (snapshot_root / manifest).is_file() for manifest in GO_MANIFESTS
        )

    def detect_project(self, snapshot_root: Path) -> ProjectProfile:
        manifests = [manifest for manifest in GO_MANIFESTS if (snapshot_root / manifest).is_file()]
        hints: list[str] = []
        for source_file in self._source_files(snapshot_root):
            text = self.read_text_detected(source_file)
            if text is None:
                continue
            for import_path, hint in FRAMEWORK_IMPORT_PATHS.items():
                if re.search(rf"['\"][\w./\-]*{re.escape(import_path)}(?:/[\w.-]+)?['\"]", text):
                    hints.append(hint)
        return ProjectProfile(
            language=self.language,
            framework_hints=sorted(set(hints)),
            manifest_paths=manifests,
        )

    def run_sast(self, snapshot_root: Path) -> list[RawFinding]:
        findings: list[RawFinding] = []
        for source_file in self._source_files(snapshot_root):
            text = self.read_text_detected(source_file)
            if text is None:
                continue
            relative_path = source_file.relative_to(snapshot_root).as_posix()
            block_comment_open = False
            for line_number, line in enumerate(text.splitlines(), start=1):
                code_line, block_comment_open = self._mask_comments(line, block_comment_open)
                if EXEC_SHELL_PATTERN.search(code_line):
                    findings.append(self._finding(
                        "GO-EXEC-SH", "high", "CWE-78", relative_path, line_number,
                        "exec.Command 直接调用 shell，若参数含不可信输入可能造成命令注入。", code_line,
                    ))
                if MD5_USE_PATTERN.search(code_line):
                    findings.append(self._finding(
                        "GO-CRYPTO-MD5", "medium", "CWE-327", relative_path, line_number,
                        "使用 MD5 哈希，若用于安全目的（口令/签名）应改用 SHA-256 或更高强度算法。", code_line,
                    ))
                if INSECURE_TLS_PATTERN.search(code_line):
                    findings.append(self._finding(
                        "GO-TLS-INSECURE", "medium", "CWE-295", relative_path, line_number,
                        "TLS 配置禁用了证书校验（InsecureSkipVerify=true），可能遭受中间人攻击。", code_line,
                    ))
        return sorted(findings, key=lambda item: (item.file_path, item.start_line, item.rule_id))

    @staticmethod
    def _source_files(snapshot_root: Path) -> list[Path]:
        return sorted(
            path for path in snapshot_root.rglob("*")
            if path.is_file() and path.suffix.lower() in GO_SUFFIXES
        )

    @staticmethod
    def _mask_comments(line: str, block_comment_open: bool) -> tuple[str, bool]:
        """Mask `//` line comments and `/* */` block comments, keeping positions."""
        output: list[str] = []
        index = 0
        while index < len(line):
            character = line[index]
            next_character = line[index + 1] if index + 1 < len(line) else ""
            if block_comment_open:
                output.append(" ")
                if character == "*" and next_character == "/":
                    output.append(" ")
                    index += 2
                    block_comment_open = False
                    continue
                index += 1
                continue
            if character == "/" and next_character == "/":
                output.extend(" " * (len(line) - index))
                break
            if character == "/" and next_character == "*":
                output.extend("  ")
                index += 2
                block_comment_open = True
                continue
            output.append(character)
            index += 1
        return "".join(output), block_comment_open

    @classmethod
    def _finding(
        cls, rule_id: str, severity: str, cwe_id: str, file_path: str, line_number: int, message: str, line: str
    ) -> RawFinding:
        return RawFinding(
            rule_id=rule_id,
            category="sast",
            severity=severity,
            cwe_id=cwe_id,
            file_path=file_path,
            start_line=line_number,
            end_line=line_number,
            message=message,
            evidence_preview=line.strip()[:300],
        )
