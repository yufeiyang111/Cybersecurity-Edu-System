from app.services.scanners import get_scanners
from app.services.scanners.python_scanner import PythonScanner


def test_detects_python_project_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")

    profile = PythonScanner().detect_project(tmp_path)

    assert profile.language == "python"
    assert profile.manifest_paths == ["pyproject.toml"]


def test_reports_shell_true_as_cwe_78(tmp_path):
    (tmp_path / "danger.py").write_text(
        "import subprocess\nsubprocess.run(cmd, shell=True)\n", encoding="utf-8"
    )

    findings = PythonScanner().run_sast(tmp_path)

    assert [(finding.rule_id, finding.cwe_id, finding.start_line) for finding in findings] == [
        ("PY-SHELL-TRUE", "CWE-78", 2)
    ]


def test_reports_unsafe_yaml_and_flask_debug(tmp_path):
    (tmp_path / "app.py").write_text(
        "import yaml\nvalue = yaml.load(payload)\napp.run(debug=True)\n", encoding="utf-8"
    )

    findings = PythonScanner().run_sast(tmp_path)

    assert {(finding.rule_id, finding.cwe_id) for finding in findings} == {
        ("PY-YAML-UNSAFE-LOAD", "CWE-502"),
        ("PY-FLASK-DEBUG", "CWE-489"),
    }


def test_secret_evidence_is_masked_and_hashed(tmp_path):
    (tmp_path / "settings.py").write_text(
        "API_KEY = 'sk_live_1234567890abcdef'\n", encoding="utf-8"
    )

    finding = PythonScanner().run_secret_scan(tmp_path)[0]

    assert "1234567890abcdef" not in finding.evidence_preview
    assert finding.evidence_preview == "sk_l***cdef"
    assert len(finding.secret_sha256) == 64


def test_registry_exposes_python_scanner():
    assert isinstance(get_scanners()[0], PythonScanner)
