"""Safe ZIP source intake for static security analysis.

Archives are treated as untrusted input.  This module validates all ZIP metadata
before creating an extraction directory, and never executes or imports content
from an uploaded project.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable


class ArchiveValidationError(ValueError):
    """Raised when an uploaded archive violates the intake safety policy."""


@dataclass(frozen=True)
class ArchiveSafetyPolicy:
    """Resource limits and file allowlist for one source archive intake."""

    max_archive_bytes: int | None = 50 * 1024 * 1024
    max_file_count: int = 20_000
    max_path_depth: int = 10
    max_extracted_bytes: int = 500 * 1024 * 1024
    chunk_size: int = 64 * 1024
    allowed_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                ".py",
                ".pyi",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".java",
                ".json",
                ".toml",
                ".yaml",
                ".yml",
                ".ini",
                ".cfg",
                ".conf",
                ".properties",
                ".xml",
                ".gradle",
                ".kts",
                ".txt",
                ".md",
                ".rst",
                ".sh",
                ".ps1",
                ".bat",
                ".cmd",
                ".sql",
                ".go",
                ".rs",
                ".rb",
                ".php",
                ".vue",
                ".svelte",
                ".c",
                ".h",
                ".cpp",
                ".cc",
                ".hpp",
                ".cxx",
                ".hxx",
                ".cs",
                ".kt",
                ".swift",
                ".scala",
                ".pl",
                ".pm",
                ".lua",
                ".dart",
                ".ex",
                ".exs",
                ".bash",
                ".zsh",
                ".fish",
                ".awk",
                ".html",
                ".htm",
                ".css",
                ".scss",
                ".sass",
                ".less",
                ".pem",
                ".key",
                ".ovpn",
            }
        )
    )
    allowed_filenames: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "dockerfile",
                "makefile",
                "pipfile",
                "poetry.lock",
                "requirements",
                "requirements.txt",
                "package-lock.json",
                "pnpm-lock.yaml",
                "yarn.lock",
                "gradlew",
                "gradlew.bat",
                ".env",
                ".gitignore",
                ".dockerignore",
                ".editorconfig",
                ".gitattributes",
                ".helmignore",
                ".markdownlintrc",
                ".gitmodules",
                ".bashrc",
                ".zshrc",
                ".profile",
                ".pylintrc",
                ".flake8",
                ".babelrc",
                ".gitconfig",
                ".npmrc",
                ".pypirc",
                "go.mod",
                "go.sum",
                "cargo.toml",
                "cargo.lock",
                "gemfile",
                "gemfile.lock",
                "composer.json",
                "composer.lock",
                "bower.json",
                "build.gradle",
                "settings.gradle",
                "build.gradle.kts",
                "settings.gradle.kts",
                "gradle.properties",
                "pubspec.yaml",
                "pubspec.lock",
                "cmakelists.txt",
                "gnumakefile",
            }
        )
    )

    def __post_init__(self) -> None:
        if self.max_archive_bytes is not None and self.max_archive_bytes <= 0:
            raise ValueError("max_archive_bytes must be positive or None")
        for name in ("max_file_count", "max_path_depth", "max_extracted_bytes", "chunk_size"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class SnapshotFile:
    """One extracted text file and its immutable content digest."""

    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SkippedSnapshotFile:
    """One archive member intentionally not written to the snapshot."""

    relative_path: str
    reason: str


@dataclass(frozen=True)
class SnapshotManifest:
    """Immutable description of the analysis-relevant project snapshot."""

    snapshot_root: Path
    content_sha256: str
    file_count: int
    extracted_bytes: int
    files: tuple[SnapshotFile, ...]
    skipped_files: tuple[SkippedSnapshotFile, ...]


_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")


def validate_and_extract_zip(
    archive_path: Path,
    destination: Path,
    policy: ArchiveSafetyPolicy,
    exclusion_matcher: object | None = None,
) -> SnapshotManifest:
    """Validate and extract an archive into an immutable static-analysis snapshot.

    All ZIP entries are validated before ``destination`` is created or any member
    content is written.  Only allowlisted text files are extracted; binary files
    and other regular files are represented as skipped manifest entries.
    ``exclusion_matcher`` 提供 ``is_excluded(relative_path)`` 接口（gitignore 风格），
    命中的文件即使属于白名单也不会写入快照。
    """

    archive_path = Path(archive_path)
    destination = Path(destination)
    _validate_archive_file(archive_path, policy)

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            entries = tuple(archive.infolist())
            _validate_archive_entries(entries, destination, policy)
            return _extract_validated_entries(archive, entries, destination, policy, exclusion_matcher)
    except ArchiveValidationError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ArchiveValidationError("无法安全读取 ZIP 压缩包") from exc


def _validate_archive_file(archive_path: Path, policy: ArchiveSafetyPolicy) -> None:
    if not archive_path.is_file():
        raise ArchiveValidationError("上传文件不是可读取的 ZIP 压缩包")

    archive_bytes = archive_path.stat().st_size
    if policy.max_archive_bytes is not None and archive_bytes > policy.max_archive_bytes:
        raise ArchiveValidationError("压缩包大小超过安全限制")


def _validate_archive_entries(
    entries: Iterable[zipfile.ZipInfo],
    destination: Path,
    policy: ArchiveSafetyPolicy,
) -> None:
    entries = tuple(entries)
    if len(entries) > policy.max_file_count:
        raise ArchiveValidationError("压缩包文件数量超过安全限制")

    root = destination.resolve()
    seen_paths: set[str] = set()
    file_paths: set[str] = set()

    for info in entries:
        relative_path = _validate_member_name(info, root, policy)
        if relative_path in seen_paths:
            raise ArchiveValidationError("压缩包包含重复文件路径")
        seen_paths.add(relative_path)

        if not info.is_dir():
            file_paths.add(relative_path)

    for file_path in file_paths:
        path = PurePosixPath(file_path)
        for parent in path.parents:
            if str(parent) != "." and parent.as_posix() in file_paths:
                raise ArchiveValidationError("压缩包包含文件与目录路径冲突")


def _validate_member_name(
    info: zipfile.ZipInfo,
    destination_root: Path,
    policy: ArchiveSafetyPolicy,
) -> str:
    name = info.filename
    if not name or "\x00" in name:
        raise ArchiveValidationError("压缩包包含非法空名称或 NUL 路径")
    if name.startswith(("/", "\\")) or name.startswith("//"):
        raise ArchiveValidationError("压缩包包含绝对路径")
    if _WINDOWS_DRIVE_PATH.match(name) or name.startswith("\\\\"):
        raise ArchiveValidationError("压缩包包含 Windows 绝对路径")
    if "\\" in name:
        raise ArchiveValidationError("压缩包路径不得使用 Windows 路径分隔符")

    path = PurePosixPath(name)
    if path.is_absolute():
        raise ArchiveValidationError("压缩包包含绝对路径")
    if any(part == ".." for part in path.parts):
        raise ArchiveValidationError("压缩包包含路径穿越")

    relative_parts = tuple(part for part in path.parts if part not in {"."})
    if not relative_parts:
        raise ArchiveValidationError("压缩包包含非法空路径")
    if len(relative_parts) > policy.max_path_depth:
        raise ArchiveValidationError("压缩包路径层级超过安全限制")

    _validate_member_type(info)

    relative_path = PurePosixPath(*relative_parts).as_posix()
    resolved_target = (destination_root / Path(*relative_parts)).resolve()
    try:
        resolved_target.relative_to(destination_root)
    except ValueError as exc:
        raise ArchiveValidationError("压缩包目标路径逃离了解压目录") from exc
    return relative_path


def _validate_member_type(info: zipfile.ZipInfo) -> None:
    unix_mode = info.external_attr >> 16
    file_type = stat.S_IFMT(unix_mode)

    if file_type == stat.S_IFLNK:
        raise ArchiveValidationError("压缩包不允许符号链接")
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise ArchiveValidationError("压缩包包含非普通文件或目录条目")
    if info.is_dir() and file_type not in {0, stat.S_IFDIR}:
        raise ArchiveValidationError("压缩包目录条目类型异常")
    if not info.is_dir() and file_type == stat.S_IFDIR:
        raise ArchiveValidationError("压缩包文件条目类型异常")
    if info.flag_bits & 0x1:
        raise ArchiveValidationError("压缩包不允许加密条目")


def _extract_validated_entries(
    archive: zipfile.ZipFile,
    entries: tuple[zipfile.ZipInfo, ...],
    destination: Path,
    policy: ArchiveSafetyPolicy,
    exclusion_matcher: object | None,
) -> SnapshotManifest:
    destination_existed = destination.exists()
    if destination_existed and (not destination.is_dir() or any(destination.iterdir())):
        raise ArchiveValidationError("解压目录必须不存在或为空")

    destination_root = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    extracted_bytes = 0
    files: list[SnapshotFile] = []
    skipped_files: list[SkippedSnapshotFile] = []

    try:
        for info in entries:
            relative_path = _relative_path_from_info(info)
            if info.is_dir():
                continue

            if not _is_analysis_relevant(relative_path, policy):
                extracted_bytes = _consume_member(archive, info, policy, extracted_bytes)
                skipped_files.append(SkippedSnapshotFile(relative_path, "not_analysis_relevant"))
                continue

            if exclusion_matcher is not None and exclusion_matcher.is_excluded(relative_path):
                extracted_bytes = _consume_member(archive, info, policy, extracted_bytes)
                skipped_files.append(SkippedSnapshotFile(relative_path, "user_excluded"))
                continue

            target_path = destination_root / Path(*PurePosixPath(relative_path).parts)
            _ensure_path_inside_root(target_path, destination_root)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".source-intake-",
                suffix=".tmp",
                dir=destination_root,
                delete=False,
            ) as staging_file:
                staging_path = Path(staging_file.name)
                file_sha256, file_size, extracted_bytes, is_text = _stream_member_to_staging(
                    archive,
                    info,
                    staging_file,
                    policy,
                    extracted_bytes,
                )

            if not is_text:
                staging_path.unlink(missing_ok=True)
                skipped_files.append(SkippedSnapshotFile(relative_path, "binary_or_non_text"))
                continue

            os.replace(staging_path, target_path)
            files.append(SnapshotFile(relative_path, file_sha256, file_size))

        files.sort(key=lambda item: item.relative_path)
        skipped_files.sort(key=lambda item: (item.relative_path, item.reason))
        return SnapshotManifest(
            snapshot_root=destination_root,
            content_sha256=_compute_snapshot_hash(files),
            file_count=len(files),
            extracted_bytes=extracted_bytes,
            files=tuple(files),
            skipped_files=tuple(skipped_files),
        )
    except Exception:
        _cleanup_partial_destination(destination, destination_existed)
        raise


def _relative_path_from_info(info: zipfile.ZipInfo) -> str:
    return PurePosixPath(*[part for part in PurePosixPath(info.filename).parts if part != "."]).as_posix()


def _is_analysis_relevant(relative_path: str, policy: ArchiveSafetyPolicy) -> bool:
    path = PurePosixPath(relative_path)
    filename = path.name.lower()
    if filename in policy.allowed_filenames or path.suffix.lower() in policy.allowed_extensions:
        return True
    return filename == ".env" or filename.startswith(".env.")


def _consume_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    policy: ArchiveSafetyPolicy,
    extracted_bytes: int,
) -> int:
    with archive.open(info, "r") as source:
        while chunk := source.read(policy.chunk_size):
            extracted_bytes = _increment_extracted_bytes(extracted_bytes, len(chunk), policy)
    return extracted_bytes


def _stream_member_to_staging(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    staging_file: object,
    policy: ArchiveSafetyPolicy,
    extracted_bytes: int,
) -> tuple[str, int, int, bool]:
    digest = hashlib.sha256()
    file_size = 0
    head = b""
    has_nul = False

    with archive.open(info, "r") as source:
        while chunk := source.read(policy.chunk_size):
            extracted_bytes = _increment_extracted_bytes(extracted_bytes, len(chunk), policy)
            file_size += len(chunk)
            digest.update(chunk)
            staging_file.write(chunk)  # type: ignore[attr-defined]
            if not has_nul and b"\x00" in chunk:
                has_nul = True
            if len(head) < _BINARY_MAGIC_HEAD_BYTES:
                head = (head + chunk)[:_BINARY_MAGIC_HEAD_BYTES]

    is_text = not has_nul and not _matches_binary_magic(head)
    return digest.hexdigest(), file_size, extracted_bytes, is_text


_BINARY_MAGIC_HEAD_BYTES = 8

_BINARY_MAGIC_PREFIXES = (
    b"\x89PNG",
    b"\xff\xd8\xff",
    b"GIF8",
    b"%PDF",
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
    b"MZ",
    b"\x7fELF",
    b"\xca\xfe\xba\xbe",
    b"\x1f\x8b",
    b"BM",
    b"fLaC",
    b"OggS",
    b"\x00\x01\x00\x00",
    b"wOFF",
    b"wOF2",
    b"7z\xbc\xaf\x27\x1c",
    b"RIFF",
    b"\x1a\x45\xdf\xa3",
    b"\x00\x00\x00\x18ftyp",
)


def _matches_binary_magic(head: bytes) -> bool:
    if not head:
        return False
    for magic in _BINARY_MAGIC_PREFIXES:
        if head[: len(magic)] == magic:
            return True
    return False


def _increment_extracted_bytes(
    extracted_bytes: int,
    chunk_size: int,
    policy: ArchiveSafetyPolicy,
) -> int:
    total = extracted_bytes + chunk_size
    if total > policy.max_extracted_bytes:
        raise ArchiveValidationError("解压后大小超过安全限制")
    return total


def _ensure_path_inside_root(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(root)
    except ValueError as exc:
        raise ArchiveValidationError("压缩包目标路径逃离了解压目录") from exc


def _compute_snapshot_hash(files: Iterable[SnapshotFile]) -> str:
    canonical_entries = "".join(
        f"{item.relative_path}\0{item.sha256}\n" for item in sorted(files, key=lambda item: item.relative_path)
    )
    return hashlib.sha256(canonical_entries.encode("utf-8")).hexdigest()


def _cleanup_partial_destination(destination: Path, destination_existed: bool) -> None:
    if not destination.exists():
        return

    if destination_existed:
        for child in destination.iterdir():
            _remove_generated_path(child)
        return

    shutil.rmtree(destination)


def _remove_generated_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)



