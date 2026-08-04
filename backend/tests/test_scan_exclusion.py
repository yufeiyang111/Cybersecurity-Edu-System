"""Gitignore-style scan exclusion matcher unit tests."""
import pytest

from app.services.scan_exclusion import GitignoreMatcher, compile_patterns


def test_ignores_comments_and_empty_lines():
    matcher = GitignoreMatcher.from_patterns(["# comment", "", "*.xlsx", "  "])
    assert matcher.rule_count == 1
    assert matcher.is_excluded("docs/人员表.xlsx")


def test_extension_pattern_matches_any_level():
    matcher = GitignoreMatcher.from_patterns(["*.xlsx"])
    assert matcher.is_excluded("人员表.xlsx")
    assert matcher.is_excluded("docs/内部/人员表.xlsx")
    assert not matcher.is_excluded("人员表.xls")
    assert not matcher.is_excluded("app.py")


def test_directory_pattern_matches_subtree():
    matcher = GitignoreMatcher.from_patterns(["docs/private/"])
    assert matcher.is_excluded("docs/private")
    assert matcher.is_excluded("docs/private/合同.txt")
    assert matcher.is_excluded("docs/private/a/b/notes.md")
    assert not matcher.is_excluded("docs/public/合同.txt")


def test_leading_slash_anchors_to_root():
    matcher = GitignoreMatcher.from_patterns(["/secret.txt"])
    assert matcher.is_excluded("secret.txt")
    assert not matcher.is_excluded("nested/secret.txt")


def test_embedded_slash_anchors_relative_to_root():
    matcher = GitignoreMatcher.from_patterns(["config/keys.env"])
    assert matcher.is_excluded("config/keys.env")
    assert not matcher.is_excluded("other/config/keys.env")


def test_unprefixed_name_matches_any_level():
    matcher = GitignoreMatcher.from_patterns(["client_secrets.py"])
    assert matcher.is_excluded("client_secrets.py")
    assert matcher.is_excluded("src/client_secrets.py")
    assert matcher.is_excluded("deep/er/client_secrets.py")


def test_negation_reincludes():
    matcher = GitignoreMatcher.from_patterns(["*.md", "!重要说明.md"])
    assert matcher.is_excluded("普通.md")
    assert not matcher.is_excluded("重要说明.md")


def test_double_star_crosses_directories():
    matcher = GitignoreMatcher.from_patterns(["**/keys/*.pem"])
    assert matcher.is_excluded("keys/prod.pem")
    assert matcher.is_excluded("a/b/keys/prod.pem")
    assert not matcher.is_excluded("a/b/keys/sub/dev.pem")


def test_question_mark_and_char_class():
    matcher = GitignoreMatcher.from_patterns(["config?[0-9].ini"])
    assert matcher.is_excluded("config19.ini")
    assert matcher.is_excluded("a/configx5.ini")
    assert not matcher.is_excluded("config1.ini")
    assert not matcher.is_excluded("config.ini")


def test_last_matching_rule_wins():
    matcher = GitignoreMatcher.from_patterns(["docs/", "!docs/README.md"])
    assert matcher.is_excluded("docs/合同.txt")
    assert not matcher.is_excluded("docs/README.md")


def test_excluded_paths_filters_collection():
    matcher = GitignoreMatcher.from_patterns(["*.env"])
    paths = ["a.py", "config/.env", "b.js"]
    assert matcher.excluded_paths(paths) == ["config/.env"]


def test_compile_patterns_filters_invalid_lines():
    assert compile_patterns(["# x", "", "*.log", "   ", "!keep.txt"]) == ["*.log", "!keep.txt"]
    assert compile_patterns(["", "  "]) == []
