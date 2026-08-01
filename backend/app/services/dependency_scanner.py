"""Read-only dependency manifest discovery for immutable project snapshots.

No package manager, build tool, or uploaded source code is ever executed by this module.
"""

from __future__ import annotations

import json
from hashlib import sha256
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


_IGNORED_DIRECTORIES = {".git", ".hg", ".svn", "node_modules", "venv", ".venv", "__pycache__"}
_REQUIREMENTS_PATTERN = "requirements*.txt"
_PYPI_NORMALIZE_PATTERN = re.compile(r"[-_.]+")
_EXACT_VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+!~-]*$")
_REQUIREMENT_PATTERN = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]+\])?)\s*(==|===)\s*([^\s;#]+)"
)
_GRADLE_DEPENDENCY_PATTERN = re.compile(
    r"^\s*(?:[A-Za-z_][\w]*\.)?(?:implementation|api|compileOnly|runtimeOnly|testImplementation|testCompileOnly|testRuntimeOnly)\s*(?:\(\s*)?['\"]([^'\"]+)['\"]"
)
_POETRY_SECTION_PATTERN = re.compile(
    r"^\s*\[tool\.poetry(?:\.group\.[^.]+)?\.dependencies\]\s*$", re.IGNORECASE
)
_TOML_STRING_PATTERN = re.compile(r"['\"]([^'\"]+)['\"]")


@dataclass(frozen=True, order=True)
class DependencyCoordinate:
    """A stable, non-sensitive dependency coordinate from a manifest.

    All fields participate in equality and hashing. Discovery deduplication is deliberately
    narrower (ecosystem/name/version/manifest) so duplicate declarations retain the first
    deterministic source location.
    """

    ecosystem: str
    package_name: str
    version: str
    manifest_path: str
    is_direct: bool
    source_line: int | None


def dependency_coordinate_hash(coordinate: DependencyCoordinate) -> str:
    """Return the stable identity hash used for database uniqueness, not display."""
    canonical = json.dumps(
        [
            coordinate.ecosystem,
            coordinate.package_name,
            coordinate.version,
            coordinate.manifest_path,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def discover_dependencies(snapshot_root: Path) -> list[DependencyCoordinate]:
    """Discover pinned dependencies without executing package managers or project code."""
    root = Path(snapshot_root).resolve()
    if not root.is_dir():
        return []

    candidates: list[DependencyCoordinate] = []
    for path in _iter_manifest_files(root, _REQUIREMENTS_PATTERN):
        candidates.extend(_parse_requirements(path, root))
    for path in _iter_named_files(root, {"pyproject.toml"}):
        candidates.extend(_parse_pyproject(path, root))
    for path in _iter_named_files(root, {"package.json"}):
        candidates.extend(_parse_package_json(path, root))
    for path in _iter_named_files(root, {"package-lock.json"}):
        candidates.extend(_parse_package_lock(path, root))
    for path in _iter_named_files(root, {"pom.xml"}):
        candidates.extend(_parse_maven_pom(path, root))
    for path in _iter_named_files(root, {"build.gradle", "build.gradle.kts"}):
        candidates.extend(_parse_gradle(path, root))

    deduped: dict[tuple[str, str, str, str], DependencyCoordinate] = {}
    for coordinate in candidates:
        key = (
            coordinate.ecosystem,
            coordinate.package_name,
            coordinate.version,
            coordinate.manifest_path,
        )
        existing = deduped.get(key)
        if existing is None or _coordinate_sort_key(coordinate) < _coordinate_sort_key(existing):
            deduped[key] = coordinate
    return sorted(deduped.values(), key=_coordinate_sort_key)


def _iter_manifest_files(root: Path, pattern: str) -> Iterable[Path]:
    for path in root.rglob(pattern):
        if _is_allowed_manifest_path(path, root):
            yield path


def _iter_named_files(root: Path, names: set[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.name in names and _is_allowed_manifest_path(path, root):
            yield path


def _is_allowed_manifest_path(path: Path, root: Path) -> bool:
    if not path.is_file():
        return False
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return False
    return not any(part in _IGNORED_DIRECTORIES for part in relative_parts)


def _parse_requirements(path: Path, root: Path) -> list[DependencyCoordinate]:
    coordinates: list[DependencyCoordinate] = []
    for line_number, line in enumerate(_read_lines(path), 1):
        stripped = line.split("#", 1)[0].strip()
        if not stripped or stripped.startswith(("-", "--")):
            continue
        match = _REQUIREMENT_PATTERN.match(stripped)
        if match is None:
            continue
        package_name = _normalize_pypi_name(match.group(1).split("[", 1)[0])
        version = _normalize_pinned_version(match.group(3))
        if package_name and version:
            coordinates.append(_coordinate("PyPI", package_name, version, path, root, True, line_number))
    return coordinates


def _parse_pyproject(path: Path, root: Path) -> list[DependencyCoordinate]:
    content = _read_text(path)
    if content is None:
        return []
    coordinates: list[DependencyCoordinate] = []

    for requirement, line_number in _project_dependency_strings(content):
        parsed = _parse_python_requirement(requirement)
        if parsed is not None:
            package_name, version = parsed
            coordinates.append(_coordinate("PyPI", package_name, version, path, root, True, line_number))

    active_poetry_section = False
    for line_number, raw_line in enumerate(content.splitlines(), 1):
        stripped = raw_line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            active_poetry_section = bool(_POETRY_SECTION_PATTERN.match(stripped))
            continue
        if not active_poetry_section or not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, raw_value = (part.strip() for part in stripped.split("=", 1))
        if name.lower() == "python":
            continue
        version = _extract_toml_version(raw_value)
        package_name = _normalize_pypi_name(name.strip("'\""))
        if package_name and version:
            coordinates.append(_coordinate("PyPI", package_name, version, path, root, True, line_number))
    return coordinates


def _project_dependency_strings(content: str) -> Iterable[tuple[str, int]]:
    section_match = re.search(r"(?ms)^\s*\[project\]\s*(.*?)(?=^\s*\[|\Z)", content)
    if section_match is None:
        return []
    section = section_match.group(1)
    dependency_match = re.search(r"(?ms)^\s*dependencies\s*=\s*\[(.*?)\]", section)
    if dependency_match is None:
        return []
    offset = content[: section_match.start(1) + dependency_match.start(1)].count("\n") + 1
    return [
        (match.group(1), offset + dependency_match.group(1)[: match.start()].count("\n"))
        for match in _TOML_STRING_PATTERN.finditer(dependency_match.group(1))
    ]


def _parse_python_requirement(requirement: str) -> tuple[str, str] | None:
    match = _REQUIREMENT_PATTERN.match(requirement)
    if match is None:
        return None
    package_name = _normalize_pypi_name(match.group(1).split("[", 1)[0])
    version = _normalize_pinned_version(match.group(3))
    return (package_name, version) if package_name and version else None


def _extract_toml_version(raw_value: str) -> str | None:
    value_match = _TOML_STRING_PATTERN.search(raw_value)
    if value_match is None:
        version_match = re.search(r"\bversion\s*=\s*['\"]([^'\"]+)['\"]", raw_value)
        if version_match is None:
            return None
        candidate = version_match.group(1)
    else:
        candidate = value_match.group(1)
    return _normalize_pinned_version(candidate.lstrip("="))


def _parse_package_json(path: Path, root: Path) -> list[DependencyCoordinate]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return []
    coordinates: list[DependencyCoordinate] = []
    for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        dependencies = payload.get(key)
        if not isinstance(dependencies, dict):
            continue
        for package_name, raw_version in dependencies.items():
            version = _normalize_pinned_version(raw_version)
            normalized_name = _normalize_npm_name(package_name)
            if normalized_name and version:
                coordinates.append(_coordinate("npm", normalized_name, version, path, root, True, _find_json_key_line(path, package_name)))
    return coordinates


def _parse_package_lock(path: Path, root: Path) -> list[DependencyCoordinate]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return []
    coordinates: list[DependencyCoordinate] = []
    packages = payload.get("packages")
    root_direct: set[str] = set()
    if isinstance(packages, dict) and isinstance(packages.get(""), dict):
        root_manifest = packages[""]
        for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            values = root_manifest.get(key)
            if isinstance(values, dict):
                root_direct.update(name for name in values if isinstance(name, str))
    if isinstance(packages, dict):
        for package_path, metadata in packages.items():
            if not isinstance(package_path, str) or not isinstance(metadata, dict) or not package_path.startswith("node_modules/"):
                continue
            package_name = package_path.removeprefix("node_modules/")
            version = _normalize_pinned_version(metadata.get("version"))
            normalized_name = _normalize_npm_name(package_name)
            if normalized_name and version:
                coordinates.append(_coordinate("npm", normalized_name, version, path, root, package_name in root_direct, None))
        return coordinates

    dependencies = payload.get("dependencies")
    if isinstance(dependencies, dict):
        coordinates.extend(_parse_npm_lock_dependencies(dependencies, path, root, True))
    return coordinates


def _parse_npm_lock_dependencies(
    dependencies: dict[str, Any], path: Path, root: Path, is_direct: bool
) -> list[DependencyCoordinate]:
    coordinates: list[DependencyCoordinate] = []
    for package_name, metadata in dependencies.items():
        if not isinstance(package_name, str) or not isinstance(metadata, dict):
            continue
        version = _normalize_pinned_version(metadata.get("version"))
        normalized_name = _normalize_npm_name(package_name)
        if normalized_name and version:
            coordinates.append(_coordinate("npm", normalized_name, version, path, root, is_direct, None))
        nested = metadata.get("dependencies")
        if isinstance(nested, dict):
            coordinates.extend(_parse_npm_lock_dependencies(nested, path, root, False))
    return coordinates


def _parse_maven_pom(path: Path, root: Path) -> list[DependencyCoordinate]:
    content = _read_text(path)
    if content is None or "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
        return []
    try:
        document = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return []
    properties: dict[str, str] = {}
    for element in document.iter():
        if _local_name(element.tag) != "properties":
            continue
        for child in element:
            value = (child.text or "").strip()
            if value:
                properties[_local_name(child.tag)] = value
    coordinates: list[DependencyCoordinate] = []
    for dependency in document.iter():
        if _local_name(dependency.tag) != "dependency":
            continue
        values = {_local_name(child.tag): (child.text or "").strip() for child in dependency}
        group_id = values.get("groupId")
        artifact_id = values.get("artifactId")
        version = _resolve_maven_version(values.get("version"), properties)
        if group_id and artifact_id and version:
            package_name = f"{group_id}:{artifact_id}".lower()
            coordinates.append(_coordinate("Maven", package_name, version, path, root, True, _find_xml_dependency_line(content, group_id, artifact_id)))
    return coordinates


def _parse_gradle(path: Path, root: Path) -> list[DependencyCoordinate]:
    coordinates: list[DependencyCoordinate] = []
    for line_number, line in enumerate(_read_lines(path), 1):
        match = _GRADLE_DEPENDENCY_PATTERN.match(line)
        if match is None:
            continue
        parts = match.group(1).split(":")
        if len(parts) != 3:
            continue
        group_id, artifact_id, raw_version = (part.strip() for part in parts)
        version = _normalize_pinned_version(raw_version)
        if group_id and artifact_id and version:
            coordinates.append(_coordinate("Maven", f"{group_id}:{artifact_id}".lower(), version, path, root, True, line_number))
    return coordinates


def _coordinate(
    ecosystem: str, package_name: str, version: str, path: Path, root: Path, is_direct: bool, source_line: int | None
) -> DependencyCoordinate:
    return DependencyCoordinate(ecosystem, package_name, version, path.relative_to(root).as_posix(), is_direct, source_line)


def _coordinate_sort_key(coordinate: DependencyCoordinate) -> tuple[str, str, str, str, bool, int]:
    return (
        coordinate.ecosystem.casefold(),
        coordinate.package_name.casefold(),
        coordinate.version,
        coordinate.manifest_path,
        not coordinate.is_direct,
        coordinate.source_line if coordinate.source_line is not None else -1,
    )


def _normalize_pypi_name(name: object) -> str | None:
    if not isinstance(name, str):
        return None
    normalized = _PYPI_NORMALIZE_PATTERN.sub("-", name.strip().lower())
    return normalized if normalized and re.fullmatch(r"[a-z0-9][a-z0-9-]*", normalized) else None


def _normalize_npm_name(name: object) -> str | None:
    if not isinstance(name, str):
        return None
    normalized = name.strip().lower()
    if not normalized or normalized.startswith("@") and not re.fullmatch(r"@[a-z0-9._-]+/[a-z0-9._-]+", normalized):
        return None
    if not normalized.startswith("@") and not re.fullmatch(r"[a-z0-9._-]+", normalized):
        return None
    return normalized


def _normalize_pinned_version(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if candidate.startswith("v"):
        candidate = candidate[1:]
    if candidate.startswith("="):
        candidate = candidate[1:].strip()
    if not candidate or candidate.startswith(("^", "~", ">", "<", "*", "[", "(", "$")):
        return None
    if candidate.lower() in {"latest", "release", "dynamic", "x", "*"} or "+" in candidate and candidate.endswith("+"):
        return None
    if not _EXACT_VERSION_PATTERN.fullmatch(candidate):
        return None
    return candidate


def _resolve_maven_version(value: str | None, properties: dict[str, str]) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"\$\{([^}]+)\}", value.strip())
    candidate = properties.get(match.group(1)) if match else value
    return _normalize_pinned_version(candidate)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _read_lines(path: Path) -> list[str]:
    content = _read_text(path)
    return content.splitlines() if content is not None else []


def _read_json(path: Path) -> Any:
    content = _read_text(path)
    if content is None:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_xml_dependency_line(content: str, group_id: str, artifact_id: str) -> int | None:
    marker = f"<groupId>{group_id}</groupId>"
    position = content.find(marker)
    if position < 0:
        marker = f"<artifactId>{artifact_id}</artifactId>"
        position = content.find(marker)
    return content[:position].count("\n") + 1 if position >= 0 else None


def _find_json_key_line(path: Path, key: str) -> int | None:
    quoted_key = f'"{key}"'
    for line_number, line in enumerate(_read_lines(path), 1):
        if quoted_key in line:
            return line_number
    return None
