"""Read-only JavaScript and TypeScript baseline security scanner.

The scanner processes source as text with encoding fallback. It never invokes
Node, package managers, or scanned project code.
"""
from __future__ import annotations

from pathlib import Path
import re

from app.services.scanners.base import BaseLanguageScanner, ProjectProfile, RawFinding


JAVASCRIPT_MANIFESTS = ("package.json", "tsconfig.json")
JAVASCRIPT_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
FRAMEWORK_IMPORTS = {
    "react": "react",
    "vue": "vue",
    "@angular/core": "angular",
    "express": "express",
    "next": "nextjs",
}
EVAL_PATTERN = re.compile(r"\beval\s*\(")
DANGEROUSLY_SET_INNER_HTML_PATTERN = re.compile(r"\bdangerouslySetInnerHTML\s*=\s*\{")
CORS_WILDCARD_PATTERN = re.compile(
    r"\bcors\s*\([^\n]*?\borigin\s*:\s*(['\"])\*\1",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret(?:[_-]?key)?|token|password|passwd|authorization)\b\s*[:=]\s*)(['\"]?)[^\s,'\";}{]+\2"
)


class JavaScriptTypeScriptScanner(BaseLanguageScanner):
    """Deterministic JS/TS scanner using bounded, line-local text rules."""

    language = "javascript-typescript"
    scanner_name = "javascript-typescript-baseline"
    scanner_version = "1.0.0"
    supported_languages = ("javascript", "typescript")
    categories = ("sast", "secret")

    def can_handle(self, snapshot_root: Path) -> bool:
        return any((snapshot_root / manifest).is_file() for manifest in JAVASCRIPT_MANIFESTS) or bool(
            self._source_files(snapshot_root)
        )

    def detect_project(self, snapshot_root: Path) -> ProjectProfile:
        manifests = [manifest for manifest in JAVASCRIPT_MANIFESTS if (snapshot_root / manifest).is_file()]
        hints: list[str] = []
        candidate_files = self._source_files(snapshot_root)
        package_manifest = snapshot_root / "package.json"
        if package_manifest.is_file():
            candidate_files.append(package_manifest)
        for source_file in candidate_files:
            text = self.read_text_detected(source_file)
            if text is None:
                continue
            for package_name, hint in FRAMEWORK_IMPORTS.items():
                if re.search(
                    rf"(?:from\s+['\"]{re.escape(package_name)}['\"]|require\s*\(\s*['\"]{re.escape(package_name)}['\"]\s*\)|['\"]{re.escape(package_name)}['\"]\s*:)",
                    text,
                ):
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
            executable_names, module_names = self._child_process_symbols(text)
            block_comment_open = False
            for line_number, line in enumerate(text.splitlines(), start=1):
                initial_block_comment_open = block_comment_open
                code_line, block_comment_open = self._mask_comments_and_literals(
                    line, initial_block_comment_open, preserve_wildcard_string=False
                )
                cors_line, _ = self._mask_comments_and_literals(
                    line, initial_block_comment_open, preserve_wildcard_string=True
                )
                if EVAL_PATTERN.search(code_line):
                    findings.append(self._finding(
                        "JS-EVAL", "high", "CWE-95", relative_path, line_number,
                        "检测到 eval 调用，可能造成代码注入。", line,
                    ))
                if self._contains_child_process_execution(code_line, executable_names, module_names):
                    findings.append(self._finding(
                        "JS-CHILD-PROCESS-EXEC", "high", "CWE-78", relative_path, line_number,
                        "检测到 child_process 命令执行调用，可能造成命令注入。", line,
                    ))
                if DANGEROUSLY_SET_INNER_HTML_PATTERN.search(code_line):
                    findings.append(self._finding(
                        "JS-DANGEROUSLY-SET-INNER-HTML", "medium", "CWE-79", relative_path, line_number,
                        "检测到 dangerouslySetInnerHTML，未净化输入可能导致跨站脚本攻击。", line,
                    ))
                if CORS_WILDCARD_PATTERN.search(cors_line):
                    findings.append(self._finding(
                        "JS-CORS-WILDCARD", "medium", "CWE-942", relative_path, line_number,
                        "检测到 CORS 允许任意来源，可能扩大跨域访问边界。", line,
                    ))
        return sorted(findings, key=lambda item: (item.file_path, item.start_line, item.rule_id))

    def _source_files(self, snapshot_root: Path) -> list[Path]:
        return self._filter_excluded(
            sorted(
                path
                for path in snapshot_root.rglob("*")
                if path.is_file() and path.suffix.lower() in JAVASCRIPT_SUFFIXES
            ),
            snapshot_root,
        )

    @staticmethod
    def _child_process_symbols(text: str) -> tuple[set[str], set[str]]:
        """Return locally imported execution names and module aliases without execution."""
        executable_names: set[str] = set()
        module_names = {"child_process"}
        for match in re.finditer(r"\bimport\s+\{(?P<names>[^}]+)\}\s+from\s+['\"]child_process['\"]", text):
            for declaration in match.group("names").split(","):
                parts = declaration.strip().split()
                if parts and parts[0] in {"exec", "execSync", "execFile", "execFileSync"}:
                    executable_names.add(parts[-1])
        for match in re.finditer(r"\b(?:const|let|var)\s+\{(?P<names>[^}]+)\}\s*=\s*require\s*\(\s*['\"]child_process['\"]\s*\)", text):
            for declaration in match.group("names").split(","):
                parts = declaration.strip().split(":")
                if parts[0].strip() in {"exec", "execSync", "execFile", "execFileSync"}:
                    executable_names.add(parts[-1].strip())
        for match in re.finditer(r"\bimport\s+(?P<name>[A-Za-z_$][\w$]*)\s+from\s+['\"]child_process['\"]", text):
            module_names.add(match.group("name"))
        for match in re.finditer(r"\b(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*require\s*\(\s*['\"]child_process['\"]\s*\)", text):
            module_names.add(match.group("name"))
        return executable_names, module_names

    @staticmethod
    def _contains_child_process_execution(code_line: str, executable_names: set[str], module_names: set[str]) -> bool:
        if any(re.search(rf"\b{re.escape(name)}\s*\(", code_line) for name in executable_names):
            return True
        return any(
            re.search(rf"\b{re.escape(name)}\s*\.\s*(?:exec|execSync|execFile|execFileSync)\s*\(", code_line)
            for name in module_names
        )

    @staticmethod
    def _mask_comments_and_literals(
        line: str, block_comment_open: bool, *, preserve_wildcard_string: bool
    ) -> tuple[str, bool]:
        """Mask comments and literals while retaining source positions for safe regexes."""
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
            if character in {"'", '\"', "`"}:
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
