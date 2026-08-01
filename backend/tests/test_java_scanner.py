from app.services.scanners.java_scanner import JavaScanner


def test_detects_java_project_from_maven_gradle_and_source_files(tmp_path):
    (tmp_path / "pom.xml").write_text("<project />", encoding="utf-8")
    (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
    source_dir = tmp_path / "src" / "main" / "java"
    source_dir.mkdir(parents=True)
    (source_dir / "Application.java").write_text(
        "import org.springframework.boot.SpringApplication;\n", encoding="utf-8"
    )

    profile = JavaScanner().detect_project(tmp_path)

    assert profile.language == "java"
    assert profile.manifest_paths == ["build.gradle", "pom.xml"]
    assert profile.framework_hints == ["spring"]


def test_reports_all_java_rules_with_expected_cwes(tmp_path):
    (tmp_path / "Vulnerable.java").write_text(
        "import org.springframework.web.bind.annotation.CrossOrigin;\n"
        "Runtime.getRuntime().exec(command);\n"
        "ObjectInputStream input = new ObjectInputStream(stream);\n"
        "DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();\n"
        "@CrossOrigin(origins = \"*\")\n",
        encoding="utf-8",
    )

    findings = JavaScanner().run_sast(tmp_path)

    assert {(finding.rule_id, finding.cwe_id) for finding in findings} == {
        ("JAVA-RUNTIME-EXEC", "CWE-78"),
        ("JAVA-OBJECT-INPUT-STREAM", "CWE-502"),
        ("JAVA-XXE-FACTORY", "CWE-611"),
        ("JAVA-CORS-WILDCARD", "CWE-942"),
    }
    assert all(len(finding.evidence_preview) <= 300 for finding in findings)


def test_java_ignores_comments_and_string_literals(tmp_path):
    (tmp_path / "Safe.java").write_text(
        "String note = \"Runtime.getRuntime().exec(command);\";\n"
        "// new ObjectInputStream(stream);\n"
        "/* DocumentBuilderFactory.newInstance(); */\n"
        "String parsed = input.readLine();\n",
        encoding="utf-8",
    )

    assert JavaScanner().run_sast(tmp_path) == []
