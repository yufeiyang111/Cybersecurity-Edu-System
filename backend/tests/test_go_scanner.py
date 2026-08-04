from app.services.scanners.go_scanner import GoScanner


def test_detects_go_project_and_frameworks(tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.21\n", encoding="utf-8")
    (tmp_path / "main.go").write_text(
        'package main\nimport "github.com/gin-gonic/gin"\n',
        encoding="utf-8",
    )

    profile = GoScanner().detect_project(tmp_path)

    assert profile.language == "go"
    assert profile.manifest_paths == ["go.mod"]
    assert profile.framework_hints == ["gin"]


def test_reports_go_rules_with_expected_cwes(tmp_path):
    (tmp_path / "main.go").write_text(
        'package main\n'
        'import ("os/exec"; "crypto/md5")\n'
        'func run() {\n'
        '  exec.Command("sh", "-c", input)\n'
        '  _ = md5.Sum([]byte("x"))\n'
        '}\n',
        encoding="utf-8",
    )

    findings = GoScanner().run_sast(tmp_path)

    assert {(finding.rule_id, finding.cwe_id) for finding in findings} == {
        ("GO-EXEC-SH", "CWE-78"),
        ("GO-CRYPTO-MD5", "CWE-327"),
    }


def test_go_ignores_comments(tmp_path):
    (tmp_path / "main.go").write_text(
        'package main\n'
        '// exec.Command("sh", "-c", input)\n'
        '/* InsecureSkipVerify: true */\n',
        encoding="utf-8",
    )

    assert GoScanner().run_sast(tmp_path) == []


def test_go_inherits_generic_secret_scan(tmp_path):
    (tmp_path / "config.go").write_text(
        'package main\nconst apiKey = "abcdef1234567890"\n',
        encoding="utf-8",
    )

    findings = GoScanner().run_secret_scan(tmp_path)

    assert len(findings) == 1
    assert findings[0].rule_id == "GENERIC-HARDCODED-SECRET"
    assert findings[0].secret_sha256 is not None
    assert "abcdef1234567890" not in findings[0].evidence_preview
