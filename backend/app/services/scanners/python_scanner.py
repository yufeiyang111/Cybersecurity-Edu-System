"""Deterministic Python baseline scanner.

The scanner reads source files as text with encoding fallback. It does not
import, execute, or install anything from the scanned snapshot.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re

from app.services.scanners.base import BaseLanguageScanner, ProjectProfile, RawFinding


PYTHON_MANIFESTS = ("pyproject.toml", "requirements.txt", "Pipfile", "Pipfile.lock", "poetry.lock")


class PythonScanner(BaseLanguageScanner):
    language = "python"
    scanner_name = "python-baseline"
    scanner_version = "1.0.0"
    supported_languages = ("python",)
    categories = ("sast", "secret")

    def can_handle(self, snapshot_root: Path) -> bool:
        return bool(list(snapshot_root.rglob("*.py"))) or any(
            (snapshot_root / manifest).is_file() for manifest in PYTHON_MANIFESTS
        )

    def detect_project(self, snapshot_root: Path) -> ProjectProfile:
        manifests = [manifest for manifest in PYTHON_MANIFESTS if (snapshot_root / manifest).is_file()]
        hints: list[str] = []
        for source_file in self._python_files(snapshot_root):
            text = self.read_text_detected(source_file)
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
            text = self.read_text_detected(source_file)
            if text is None:
                continue
            relative_path = source_file.relative_to(snapshot_root).as_posix()
            findings.extend(self._find_shell_true(relative_path, text))
            findings.extend(self._find_yaml_unsafe_load(relative_path, text))
            findings.extend(self._find_flask_debug(relative_path, text))
        return sorted(findings, key=lambda item: (item.file_path, item.start_line, item.rule_id))

    @staticmethod
    def _python_files(snapshot_root: Path) -> list[Path]:
        return sorted(path for path in snapshot_root.rglob("*.py") if path.is_file())

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
