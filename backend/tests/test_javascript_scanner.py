from app.services.scanners import get_scanners
from app.services.scanners.go_scanner import GoScanner
from app.services.scanners.javascript_scanner import JavaScriptTypeScriptScanner
from app.services.scanners.java_scanner import JavaScanner
from app.services.scanners.python_scanner import PythonScanner


def test_detects_javascript_typescript_project_from_manifests_and_source(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "1.0.0"}}', encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("export const value = 1;\n", encoding="utf-8")

    profile = JavaScriptTypeScriptScanner().detect_project(tmp_path)

    assert profile.language == "javascript-typescript"
    assert profile.manifest_paths == ["package.json", "tsconfig.json"]
    assert profile.framework_hints == ["react"]


def test_reports_all_javascript_typescript_rules_with_expected_cwes(tmp_path):
    (tmp_path / "app.tsx").write_text(
        "import { exec } from 'child_process';\n"
        "const payload = window.location.hash;\n"
        "eval(payload);\n"
        "exec(payload);\n"
        "const view = <section dangerouslySetInnerHTML={{ __html: payload }} />;\n"
        "app.use(cors({ origin: '*' }));\n",
        encoding="utf-8",
    )

    findings = JavaScriptTypeScriptScanner().run_sast(tmp_path)

    assert {(finding.rule_id, finding.cwe_id) for finding in findings} == {
        ("JS-EVAL", "CWE-95"),
        ("JS-CHILD-PROCESS-EXEC", "CWE-78"),
        ("JS-DANGEROUSLY-SET-INNER-HTML", "CWE-79"),
        ("JS-CORS-WILDCARD", "CWE-942"),
    }
    assert all(len(finding.evidence_preview) <= 300 for finding in findings)


def test_javascript_typescript_ignores_comments_and_string_literals(tmp_path):
    (tmp_path / "safe.js").write_text(
        "const note = 'eval(payload); exec(payload); dangerouslySetInnerHTML={{}}';\n"
        "// eval(payload);\n"
        "/* app.use(cors({ origin: '*' })); */\n"
        "const parsed = JSON.parse(payload);\n",
        encoding="utf-8",
    )

    assert JavaScriptTypeScriptScanner().run_sast(tmp_path) == []


def test_registry_exposes_scanners_in_stable_language_order():
    assert [type(scanner) for scanner in get_scanners()] == [
        PythonScanner,
        JavaScriptTypeScriptScanner,
        JavaScanner,
        GoScanner,
    ]
