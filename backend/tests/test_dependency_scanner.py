from __future__ import annotations

from pathlib import Path

from app.services.dependency_scanner import DependencyCoordinate, discover_dependencies


def _coordinate_keys(dependencies: list[DependencyCoordinate]) -> list[tuple[str, str, str, str]]:
    return [
        (dependency.ecosystem, dependency.package_name, dependency.version, dependency.manifest_path)
        for dependency in dependencies
    ]


def test_discovers_pinned_dependencies_across_supported_ecosystems(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "Flask==3.0.0\nunpinned>=1.0\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
dependencies = [
  "requests==2.31.0",
  "ignored>=1.0",
]

[tool.poetry.dependencies]
django = "4.2.11"
python = "^3.10"
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text(
        """{
  "dependencies": {"express": "4.18.3", "ignored": "^2.0.0"},
  "devDependencies": {"typescript": "5.4.5"}
}""",
        encoding="utf-8",
    )
    (tmp_path / "package-lock.json").write_text(
        """{
  "lockfileVersion": 3,
  "packages": {
    "": {"dependencies": {"express": "4.18.3"}},
    "node_modules/express": {"version": "4.18.3"},
    "node_modules/transitive": {"version": "1.0.0"}
  }
}""",
        encoding="utf-8",
    )
    (tmp_path / "pom.xml").write_text(
        """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <properties><spring.version>6.1.2</spring.version></properties>
  <dependencies>
    <dependency><groupId>org.springframework</groupId><artifactId>spring-core</artifactId><version>${spring.version}</version></dependency>
  </dependencies>
</project>""",
        encoding="utf-8",
    )
    (tmp_path / "build.gradle").write_text(
        """dependencies {
  implementation 'org.apache.commons:commons-lang3:3.14.0'
  testImplementation("junit:junit:4.13.2")
  implementation 'ignored:dynamic:1.+'
}""",
        encoding="utf-8",
    )

    dependencies = discover_dependencies(tmp_path)
    keys = _coordinate_keys(dependencies)

    assert ("PyPI", "flask", "3.0.0", "requirements.txt") in keys
    assert ("PyPI", "requests", "2.31.0", "pyproject.toml") in keys
    assert ("PyPI", "django", "4.2.11", "pyproject.toml") in keys
    assert ("npm", "express", "4.18.3", "package.json") in keys
    assert ("npm", "typescript", "5.4.5", "package.json") in keys
    assert ("npm", "transitive", "1.0.0", "package-lock.json") in keys
    assert ("Maven", "org.springframework:spring-core", "6.1.2", "pom.xml") in keys
    assert ("Maven", "org.apache.commons:commons-lang3", "3.14.0", "build.gradle") in keys
    assert ("Maven", "junit:junit", "4.13.2", "build.gradle") in keys
    assert all("ignored" not in package_name for _, package_name, _, _ in keys)


def test_deduplicates_same_manifest_coordinate_and_returns_stable_sorted_results(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "Requests==2.31.0\nrequests==2.31.0\n", encoding="utf-8"
    )
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "requirements-dev.txt").write_text(
        "flask==3.0.0\n", encoding="utf-8"
    )

    first = discover_dependencies(tmp_path)
    second = discover_dependencies(tmp_path)

    assert first == second
    assert _coordinate_keys(first) == [
        ("PyPI", "flask", "3.0.0", "nested/requirements-dev.txt"),
        ("PyPI", "requests", "2.31.0", "requirements.txt"),
    ]
    requests_dependency = next(item for item in first if item.package_name == "requests")
    assert requests_dependency.source_line == 1
    assert hash(requests_dependency) == hash(DependencyCoordinate("PyPI", "requests", "2.31.0", "requirements.txt", True, 1))


def test_maven_doctype_and_unpinned_specs_are_ignored_safely(tmp_path: Path):
    (tmp_path / "pom.xml").write_text(
        """<!DOCTYPE project SYSTEM "https://example.test/external.dtd">
<project><dependencies><dependency><groupId>bad</groupId><artifactId>bad</artifactId><version>1.0.0</version></dependency></dependencies></project>""",
        encoding="utf-8",
    )
    (tmp_path / "build.gradle.kts").write_text(
        'implementation("org.example:valid:1.2.3")\nimplementation("org.example:unpinned:+")\n',
        encoding="utf-8",
    )

    dependencies = discover_dependencies(tmp_path)

    assert _coordinate_keys(dependencies) == [
        ("Maven", "org.example:valid", "1.2.3", "build.gradle.kts"),
    ]
