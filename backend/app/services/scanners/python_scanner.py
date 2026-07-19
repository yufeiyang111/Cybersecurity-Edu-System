"""Deterministic Python baseline scanner.

The scanner reads source files as UTF-8 text only. It does not import, execute,
or install anything from the scanned snapshot.
"""
from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path
import re

from app.services.scanners.base import BaseLanguageScanner, ProjectProfile, RawFinding


PYTHON_MANIFESTS = ("pyproject.toml", "requirements.txt", "Pipfile", "Pipfile.lock", "poetry.lock")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|token|password|passwd|access[_-]?key)\b\s*=\s*(['\"])(?P<value>[^'\"\r\n]{8,})\1"
)


class PythonScanner(BaseLanguageScanner):
    language = "python"

    def can_handle(self, snapshot_root: Path) -> bool:
        return bool(list(snapshot_root.rglob("*.py"))) or any(
            (snapshot_root / manifest).is_file() for manifest in PYTHON_MANIFESTS
        )

    def detect_project(self, snapshot_root: Path) -> ProjectProfile:
        manifests = [manifest for manifest in PYTHON_MANIFESTS if (snapshot_root / manifest).is_file()]
        hints: list[str] = []
        for source_file in self._python_files(snapshot_root):
            text = self._read_utf8(source_file)
            if text is None:
                continue
            if re.search(r"\bfrom\s+flask\s+import\b|\bimport\s+flask\b", text):
                hints.append("flask")
            if re.search(r"\bfrom\s+django\b|\bimport\s+django\b", text):
                hints.append("django")
        return ProjectProfile(
            language=self.language,
            framework_hints=sorted(set(hints)),
            manifest_paths=manifests,
        )

    def run_sast(self, snapshot_root: Path) -> list[RawFinding]:
        findings: list[RawFinding] = []
        for source_file in self._python_files(snapshot_root):
            text = self._read_utf8(source_file)
            if text is None:
                continue
            relative_path = source_file.relative_to(snapshot_root).as_posix()
            findings.extend(self._find_shell_true(relative_path, text))
            findings.extend(self._find_yaml_unsafe_load(relative_path, text))
            findings.extend(self._find_flask_debug(relative_path, text))
        return sorted(findings, key=lambda item: (item.file_path, item.start_line, item.rule_id))

    def run_secret_scan(self, snapshot_root: Path) -> list[RawFinding]:
        findings: list[RawFinding] = []
        for source_file in self._candidate_text_files(snapshot_root):
            text = self._read_utf8(source_file)
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
                        evidence_preview=self._mask_secret(secret),
                        secret_sha256=sha256(secret.encode("utf-8")).hexdigest(),
                    )
                )
        return findings

    @staticmethod
    def _mask_secret(secret: str) -> str:
        if len(secret) <= 8:
            return "***"
        return f"{secret[:4]}***{secret[-4:]}"

    @staticmethod
    def _read_utf8(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    @staticmethod
    def _python_files(snapshot_root: Path) -> list[Path]:
        return sorted(path for path in snapshot_root.rglob("*.py") if path.is_file())

    @staticmethod
    def _candidate_text_files(snapshot_root: Path) -> list[Path]:
        suffixes = {".py", ".pyi", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".env"}
        return sorted(path for path in snapshot_root.rglob("*") if path.is_file() and (path.suffix.lower() in suffixes or path.name == ".env"))

    @staticmethod
    def _parse_source(text: str) -> ast.AST | None:
        try:
            return ast.parse(text)
        except SyntaxError:
            return None

    def _find_shell_true(self, relative_path: str, text: str) -> list[RawFinding]:
        tree = self._parse_source(text)
        if tree is None:
            return []
        findings: list[RawFinding] = []
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = self._call_name(node.func)
            if call_name not in {"subprocess.run", "subprocess.call", "subprocess.Popen", "subprocess.check_call", "subprocess.check_output", "os.system"}:
                continue
            has_shell_true = any(
                keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                for keyword in node.keywords
            )
            if has_shell_true:
                line = getattr(node, "lineno", 1)
                findings.append(RawFinding(
                    rule_id="PY-SHELL-TRUE",
                    category="sast",
                    severity="high",
                    cwe_id="CWE-78",
                    file_path=relative_path,
                    start_line=line,
                    end_line=getattr(node, "end_lineno", line),
                    message="subprocess 调用启用了 shell=True，可能导致命令注入。",
                    evidence_preview=lines[line - 1].strip()[:300],
                ))
        return findings

    def _find_yaml_unsafe_load(self, relative_path: str, text: str) -> list[RawFinding]:
        tree = self._parse_source(text)
        if tree is None:
            return []
        lines = text.splitlines()
        findings: list[RawFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or self._call_name(node.func) != "yaml.load":
                continue
            has_safe_loader = any(keyword.arg == "Loader" for keyword in node.keywords)
            if has_safe_loader:
                continue
            line = getattr(node, "lineno", 1)
            findings.append(RawFinding(
                rule_id="PY-YAML-UNSAFE-LOAD",
                category="sast",
                severity="high",
                cwe_id="CWE-502",
                file_path=relative_path,
                start_line=line,
                end_line=getattr(node, "end_lineno", line),
                message="yaml.load 未指定安全 Loader，可能触发不安全反序列化。",
                evidence_preview=lines[line - 1].strip()[:300],
            ))
        return findings

    def _find_flask_debug(self, relative_path: str, text: str) -> list[RawFinding]:
        tree = self._parse_source(text)
        if tree is None:
            return []
        lines = text.splitlines()
        findings: list[RawFinding] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or self._call_name(node.func) != "app.run":
                continue
            debug_enabled = any(
                keyword.arg == "debug" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                for keyword in node.keywords
            )
            if not debug_enabled:
                continue
            line = getattr(node, "lineno", 1)
            findings.append(RawFinding(
                rule_id="PY-FLASK-DEBUG",
                category="configuration",
                severity="medium",
                cwe_id="CWE-489",
                file_path=relative_path,
                start_line=line,
                end_line=getattr(node, "end_lineno", line),
                message="Flask 在代码中启用了 debug=True，生产环境可能暴露调试器。",
                evidence_preview=lines[line - 1].strip()[:300],
            ))
        return findings

    @staticmethod
    def _call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = PythonScanner._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""
