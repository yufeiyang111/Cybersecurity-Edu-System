from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest

from app.services.remediation_engine import validate_unified_patch


def test_remediation_engine_module_exposes_contract():
    assert importlib.util.find_spec("app.services.remediation_engine") is not None


def test_remediation_engine_exposes_public_contracts():
    module = importlib.import_module("app.services.remediation_engine")

    assert isinstance(getattr(module, "PatchValidationResult", None), type)
    assert callable(getattr(module, "validate_unified_patch", None))
    assert isinstance(getattr(module, "RemediationGenerationResult", None), type)
    assert isinstance(getattr(module, "RemediationService", None), type)


def _write_snapshot_file(snapshot_root: Path, relative_path: str, content: str) -> Path:
    target = snapshot_root.joinpath(*relative_path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def test_validate_unified_patch_accepts_matching_single_file_context_without_mutation(tmp_path):
    snapshot_root = tmp_path / "snapshot"
    original = "from flask import Flask\napp = Flask(__name__)\napp.run(debug=True)\n"
    target = _write_snapshot_file(snapshot_root, "app.py", original)
    patch = """--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
 from flask import Flask
 app = Flask(__name__)
-app.run(debug=True)
+app.run(debug=False)
"""

    result = validate_unified_patch(snapshot_root, "app.py", patch, max_lines=50, max_chars=5000)

    assert result.is_valid is True
    assert result.patch_diff == patch
    assert result.warning_codes == ()
    assert target.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("patch", "expected_warning"),
    [
        (
            """--- a/../app.py
+++ b/../app.py
@@ -1,3 +1,3 @@
 from flask import Flask
 app = Flask(__name__)
-app.run(debug=True)
+app.run(debug=False)
""",
            "PATCH_PATH_INVALID",
        ),
        (
            """--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
 from flask import Flask
 app = Flask(__name__)
-app.run(debug=not_true)
+app.run(debug=False)
""",
            "PATCH_CONTEXT_MISMATCH",
        ),
        (
            """--- a/app.py
+++ b/app.py
@@ -3 +3 @@
-app.run(debug=True)
+app.run(debug=False)
""",
            "PATCH_NO_CONTEXT",
        ),
        (
            """--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
 from flask import Flask
 app = Flask(__name__)
-app.run(debug=True)
+app.run(debug=False)
--- a/other.py
+++ b/other.py
@@ -1 +1 @@
-one
+two
""",
            "PATCH_MULTIFILE",
        ),
    ],
)
def test_validate_unified_patch_rejects_escaping_multifile_or_unverifiable_diffs(
    tmp_path, patch, expected_warning
):
    snapshot_root = tmp_path / "snapshot"
    _write_snapshot_file(
        snapshot_root,
        "app.py",
        "from flask import Flask\napp = Flask(__name__)\napp.run(debug=True)\n",
    )

    result = validate_unified_patch(snapshot_root, "app.py", patch, max_lines=50, max_chars=5000)

    assert result.is_valid is False
    assert result.patch_diff is None
    assert expected_warning in result.warning_codes

from app import db
from app.models.security import (
    FindingEvidence,
    ProjectSnapshot,
    ScanTask,
    SecurityFinding,
    SecurityKnowledgeDocument,
    SecurityKnowledgeSource,
    SecurityProject,
    Workspace,
)
from app.models.user import User
from app.services.remediation_engine import RemediationService


def _make_finding(
    tmp_path: Path,
    *,
    rule_id: str = "PY-FLASK-DEBUG",
    category: str = "configuration",
    file_path: str = "app.py",
    source_content: str = "from flask import Flask\napp = Flask(__name__)\napp.run(debug=True)\n",
    start_line: int = 3,
) -> tuple[Workspace, User, SecurityFinding, Path]:
    snapshot_root = tmp_path / "immutable-snapshot"
    target = _write_snapshot_file(snapshot_root, file_path, source_content)

    user = User(username="remediation-user", email="remediation-user@example.test", password_hash="x")
    workspace = Workspace(name="Remediation Workspace", slug="remediation-workspace")
    db.session.add_all([user, workspace])
    db.session.flush()

    project = SecurityProject(workspace_id=workspace.id, name="demo-project", created_by=user.id)
    db.session.add(project)
    db.session.flush()

    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="a" * 64,
        storage_path=str(snapshot_root),
        file_count=1,
        total_bytes=target.stat().st_size,
    )
    db.session.add(snapshot)
    db.session.flush()

    task = ScanTask(snapshot_id=snapshot.id, status="completed", progress=100)
    db.session.add(task)
    db.session.flush()

    finding = SecurityFinding(
        task_id=task.id,
        fingerprint=f"{rule_id}-{category}-{file_path}",
        rule_id=rule_id,
        category=category,
        severity="medium",
        cwe_id="CWE-489",
        file_path=file_path,
        start_line=start_line,
        end_line=start_line,
        message="Detected insecure debug configuration.",
        confidence=1.0,
        rule_version="baseline-rules-v2",
    )
    db.session.add(finding)
    db.session.flush()
    db.session.add(
        FindingEvidence(
            finding_id=finding.id,
            evidence_type="configuration",
            content_redacted="app.run(debug=True)",
            source_uri=file_path,
            start_line=start_line,
            end_line=start_line,
            score=1.0,
        )
    )

    source = SecurityKnowledgeSource(
        workspace_id=workspace.id,
        name="OWASP deployment guidance",
        source_type="standard",
        source_version="2026.1",
    )
    db.session.add(source)
    db.session.flush()
    db.session.add(
        SecurityKnowledgeDocument(
            source_id=source.id,
            document_version="2026.1-debug",
            title="Flask debug deployment guidance",
            summary="Disable development debug mode in production.",
            content="Production deployments must keep debug mode disabled.",
            tags_json=["flask", "debug", "production"],
        )
    )
    db.session.commit()
    return workspace, user, finding, target


def test_disabled_llm_creates_cited_rule_based_fallback_without_modifying_snapshot(app, tmp_path):
    with app.app_context():
        app.config.update(
            REMEDIATION_LLM_ENABLED=False,
            REMEDIATION_MAX_CONTEXT_CHARS=2000,
            REMEDIATION_MAX_OUTPUT_CHARS=4000,
            REMEDIATION_RETRIEVAL_TOP_K=3,
            REMEDIATION_PATCH_MAX_LINES=100,
            REMEDIATION_PATCH_MAX_CHARS=10_000,
        )
        _, user, finding, target = _make_finding(tmp_path)
        original = target.read_text(encoding="utf-8")

        suggestion = RemediationService().generate(finding.id, user.id)

        assert suggestion is not None
        assert suggestion.provider == "rule-based"
        assert "LLM_DISABLED" in suggestion.warning_codes_json
        assert suggestion.patch_diff is not None
        assert "debug=False" in suggestion.patch_diff
        assert suggestion.citations_json
        assert suggestion.citations_json[0]["citation_id"].startswith("knowledge-")
        assert target.read_text(encoding="utf-8") == original

        rag_evidence = FindingEvidence.query.filter_by(
            finding_id=finding.id,
            evidence_type="rag_reference",
        ).one()
        assert rag_evidence.content_redacted == suggestion.citations_json[0]["citation_id"]
        assert "prompt" not in suggestion.to_dict()
        assert "raw_model_response" not in suggestion.to_dict()

class _FakeProvider:
    provider_name = "test-provider"
    model = "test-model"
    model_version = "test-version"

    def __init__(self, output: str):
        self.output = output
        self.prompt: str | None = None
        self.system_prompt: str | None = None

    def generate(self, prompt: str, *, system_prompt: str, max_tokens: int) -> str:
        self.prompt = prompt
        self.system_prompt = system_prompt
        return self.output


def test_enabled_provider_json_is_parsed_and_validated_without_applying_patch(app, tmp_path):
    with app.app_context():
        app.config.update(
            REMEDIATION_LLM_ENABLED=True,
            REMEDIATION_MAX_CONTEXT_CHARS=2000,
            REMEDIATION_MAX_OUTPUT_CHARS=4000,
            REMEDIATION_RETRIEVAL_TOP_K=3,
            REMEDIATION_PATCH_MAX_LINES=100,
            REMEDIATION_PATCH_MAX_CHARS=10_000,
        )
        _, user, finding, target = _make_finding(tmp_path)
        original = target.read_text(encoding="utf-8")
        patch = """--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
 from flask import Flask
 app = Flask(__name__)
-app.run(debug=True)
+app.run(debug=False)
"""
        provider = _FakeProvider(
            """{
              "rationale": "Disable Flask debug mode for production.",
              "remediation_steps": ["Set debug to false", "Verify the deployment configuration"],
              "patch_diff": %s,
              "confidence": 0.92
            }""" % __import__("json").dumps(patch)
        )

        suggestion = RemediationService(provider=provider).generate(finding.id, user.id)

        assert suggestion.provider == "test-provider"
        assert suggestion.model == "test-model"
        assert suggestion.model_version == "test-version"
        assert suggestion.patch_diff == patch
        assert suggestion.confidence == pytest.approx(0.92)
        assert "LLM_DISABLED" not in suggestion.warning_codes_json
        assert provider.prompt is not None
        assert "from flask import Flask" in provider.prompt
        assert target.read_text(encoding="utf-8") == original
        assert not hasattr(suggestion, "raw_prompt")
        assert not hasattr(suggestion, "raw_model_response")


def test_secret_finding_withholds_file_context_from_enabled_provider(app, tmp_path):
    with app.app_context():
        app.config.update(
            REMEDIATION_LLM_ENABLED=True,
            REMEDIATION_MAX_CONTEXT_CHARS=2000,
            REMEDIATION_MAX_OUTPUT_CHARS=4000,
            REMEDIATION_RETRIEVAL_TOP_K=3,
            REMEDIATION_PATCH_MAX_LINES=100,
            REMEDIATION_PATCH_MAX_CHARS=10_000,
        )
        secret_value = "super-secret-value-123456789"
        _, user, finding, target = _make_finding(
            tmp_path,
            rule_id="GENERIC-HARDCODED-SECRET",
            category="secret",
            file_path="settings.py",
            source_content=f'API_KEY = "{secret_value}"\n',
            start_line=1,
        )
        provider = _FakeProvider(
            '{"rationale":"Move the credential to managed secret storage.","remediation_steps":["Rotate the exposed secret","Load it from a secret manager"],"patch_diff":null,"confidence":0.7}'
        )

        suggestion = RemediationService(provider=provider).generate(finding.id, user.id)

        assert suggestion.provider == "test-provider"
        assert "SECRET_CONTEXT_WITHHELD" in suggestion.warning_codes_json
        assert provider.prompt is not None
        assert secret_value not in provider.prompt
        assert '"content":""' in provider.prompt
        assert target.read_text(encoding="utf-8") == f'API_KEY = "{secret_value}"\n'


def test_malformed_enabled_provider_degrades_to_rule_based_fallback(app, tmp_path):
    with app.app_context():
        app.config.update(REMEDIATION_LLM_ENABLED=True)
        _, user, finding, _ = _make_finding(tmp_path)
        provider = _FakeProvider("not valid JSON")

        suggestion = RemediationService(provider=provider).generate(finding.id, user.id)

        assert suggestion.provider == "rule-based"
        assert "LLM_OUTPUT_INVALID" in suggestion.warning_codes_json
        assert suggestion.patch_diff is not None


def test_remediation_engine_is_backed_by_cohesive_domain_modules():
    required_modules = (
        "app.services.remediation.types",
        "app.services.remediation.snapshot_paths",
        "app.services.remediation.patch_validator",
        "app.services.remediation.context",
        "app.services.remediation.fallback_rules",
        "app.services.remediation.provider",
        "app.services.remediation.service",
    )

    for module_name in required_modules:
        assert importlib.util.find_spec(module_name) is not None
