"""Read-only Java baseline security scanner.

The scanner reads source as text with encoding fallback. It never invokes Java,
Maven, Gradle, or any executable contained in the scanned project.
"""
from __future__ import annotations

from pathlib import Path
import re

from app.services.scanners.base import BaseLanguageScanner, ProjectProfile, RawFinding


JAVA_MANIFESTS = ("build.gradle", "build.gradle.kts", "pom.xml")
RUNTIME_EXEC_PATTERN = re.compile(r"\bRuntime\s*\.\s*getRuntime\s*\(\s*\)\s*\.\s*exec\s*\(")
OBJECT_INPUT_STREAM_PATTERN = re.compile(r"\bnew\s+ObjectInputStream\s*\(")
XXE_FACTORY_PATTERN = re.compile(
    r"\b(?:DocumentBuilderFactory|SAXParserFactory|XMLInputFactory|TransformerFactory)\s*\.\s*newInstance\s*\(\s*\)"
)
CORS_WILDCARD_PATTERN = re.compile(
    r"(?:@CrossOrigin\s*\([^\n]*?\b(?:origins?|value)\s*=\s*(['\"])\*\1|\ballowedOrigins\s*\(\s*(['\"])\*\2\s*\))"
)
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret(?:[_-]?key)?|token|password|passwd|authorization)\b\s*[:=]\s*)(['\"]?)[^\s,'\";}{]+\2"
)


class JavaScanner(BaseLanguageScanner):
    """Deterministic Java scanner using safe, bounded source-line rules."""

    language = "java"
    scanner_name = "java-baseline"
    scanner_version = "1.0.0"
    supported_languages = ("java",)
    categories = ("sast", "secret")

    def can_handle(self, snapshot_root: Path) -> bool:
        return any((snapshot_root / manifest).is_file() for manifest in JAVA_MANIFESTS) or bool(
            self._source_files(snapshot_root)
        )

    def detect_project(self, snapshot_root: Path) -> ProjectProfile:
        manifests = [manifest for manifest in JAVA_MANIFESTS if (snapshot_root / manifest).is_file()]
        hints: list[str] = []
        for source_file in self._source_files(snapshot_root):
            text = self.read_text_detected(source_file)
            if text and re.search(r"\b(?:org\.springframework|@SpringBootApplication|@RestController)\b", text):
                hints.append("spring")
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
                initial_block_comment_open = block_comment_open
                code_line, block_comment_open = self._mask_comments_and_literals(
                    line, initial_block_comment_open, preserve_wildcard_string=False
                )
                cors_line, _ = self._mask_comments_and_literals(
                    line, initial_block_comment_open, preserve_wildcard_string=True
                )
                if RUNTIME_EXEC_PATTERN.search(code_line):
                    findings.append(self._finding(
                        "JAVA-RUNTIME-EXEC", "high", "CWE-78", relative_path, line_number,
                        "检测到 Runtime.exec 调用，可能造成命令注入。", line,
                    ))
                if OBJECT_INPUT_STREAM_PATTERN.search(code_line):
                    findings.append(self._finding(
                        "JAVA-OBJECT-INPUT-STREAM", "high", "CWE-502", relative_path, line_number,
                        "检测到 ObjectInputStream，反序列化不可信数据可能导致安全风险。", line,
                    ))
                if XXE_FACTORY_PATTERN.search(code_line):
                    findings.append(self._finding(
                        "JAVA-XXE-FACTORY", "high", "CWE-611", relative_path, line_number,
                        "检测到 XML 工厂默认创建，需显式禁用外部实体解析。", line,
                    ))
                if CORS_WILDCARD_PATTERN.search(cors_line):
                    findings.append(self._finding(
                        "JAVA-CORS-WILDCARD", "medium", "CWE-942", relative_path, line_number,
                        "检测到 CORS 允许任意来源，可能扩大跨域访问边界。", line,
                    ))
        return sorted(findings, key=lambda item: (item.file_path, item.start_line, item.rule_id))

    def _source_files(self, snapshot_root: Path) -> list[Path]:
        return self._filter_excluded(
            sorted(path for path in snapshot_root.rglob("*.java") if path.is_file()),
            snapshot_root,
        )

    @staticmethod
    def _mask_comments_and_literals(
        line: str, block_comment_open: bool, *, preserve_wildcard_string: bool
    ) -> tuple[str, bool]:
        output: list[str] = []
        index = 0
        quote: str | None = None
        escaped = False
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
            if quote is not None:
                if preserve_wildcard_string and character == "*" and next_character == quote:
                    output.append("*")
                else:
                    output.append(" ")
                if character == quote and not escaped:
                    quote = None
                escaped = character == "\\" and not escaped
                if character != "\\":
                    escaped = False
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
            if character in {"'", '\"'}:
                if (
                    preserve_wildcard_string
                    and index + 2 < len(line)
                    and line[index + 1] == "*"
                    and line[index + 2] == character
                ):
                    output.extend((character, "*", character))
                    index += 3
                    continue
                quote = character
                output.append(character)
                index += 1
                continue
            output.append(character)
            index += 1
        return "".join(output), block_comment_open

    @staticmethod
    def _redact_evidence(line: str) -> str:
        return SECRET_VALUE_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}***{match.group(2)}", line.strip())[:300]

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
            evidence_preview=cls._redact_evidence(line),
        )
