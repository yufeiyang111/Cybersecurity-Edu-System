import zipfile

import pytest

from app.services.source_intake import (
    ArchiveSafetyPolicy,
    ArchiveValidationError,
    validate_and_extract_zip,
)


def write_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for member_name, content in members.items():
            archive.writestr(member_name, content)


def test_extracts_text_project_and_returns_deterministic_sha256(tmp_path):
    archive = tmp_path / "safe.zip"
    write_zip(archive, {"app.py": "print('safe')\n", "requirements.txt": "Flask==3.0.0\n"})

    first = validate_and_extract_zip(archive, tmp_path / "out-one", ArchiveSafetyPolicy())
    second = validate_and_extract_zip(archive, tmp_path / "out-two", ArchiveSafetyPolicy())

    assert first.file_count == 2
    assert first.content_sha256 == second.content_sha256
    assert tuple(item.relative_path for item in first.files) == ("app.py", "requirements.txt")
    assert (tmp_path / "out-one" / "app.py").is_file()


@pytest.mark.parametrize("member_name", ["../escaped.py", "/absolute.py", "C:/drive.py", "C:relative.py"])
def test_rejects_unsafe_paths(tmp_path, member_name):
    archive = tmp_path / "unsafe.zip"
    write_zip(archive, {member_name: "print('unsafe')"})

    with pytest.raises(ArchiveValidationError):
        validate_and_extract_zip(archive, tmp_path / "out", ArchiveSafetyPolicy())
    assert not (tmp_path / "escaped.py").exists()


def test_rejects_symlink_entries(tmp_path):
    archive = tmp_path / "symlink.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        info = zipfile.ZipInfo("link.py")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        zip_file.writestr(info, "target.py")

    with pytest.raises(ArchiveValidationError, match="符号链接"):
        validate_and_extract_zip(archive, tmp_path / "out", ArchiveSafetyPolicy())


def test_rejects_file_count_and_extracted_size_overflow(tmp_path):
    count_archive = tmp_path / "many.zip"
    write_zip(count_archive, {"a.py": "a", "b.py": "b"})
    with pytest.raises(ArchiveValidationError, match="文件数量"):
        validate_and_extract_zip(count_archive, tmp_path / "count-out", ArchiveSafetyPolicy(max_file_count=1))

    size_archive = tmp_path / "large.zip"
    write_zip(size_archive, {"a.py": "x" * 32})
    with pytest.raises(ArchiveValidationError, match="解压后大小"):
        validate_and_extract_zip(size_archive, tmp_path / "size-out", ArchiveSafetyPolicy(max_extracted_bytes=8))


def test_skips_binary_files_without_extracting_them(tmp_path):
    archive = tmp_path / "binary.zip"
    write_zip(archive, {"app.py": "print('safe')", "payload.py": b"\xff\x00\x01"})

    manifest = validate_and_extract_zip(archive, tmp_path / "out", ArchiveSafetyPolicy())

    assert manifest.file_count == 1
    assert manifest.skipped_files[0].relative_path == "payload.py"
    assert manifest.skipped_files[0].reason == "binary_or_non_text"
    assert not (tmp_path / "out" / "payload.py").exists()

