from __future__ import annotations

from pathlib import Path
import py_compile


def test_init_sample_data_script_compiles():
    script = Path(__file__).resolve().parents[1] / "app" / "scripts" / "init_sample_data.py"
    py_compile.compile(str(script), doraise=True)


def test_init_sample_data_uses_a_valid_idempotent_suggested_question_lookup():
    script = Path(__file__).resolve().parents[1] / "app" / "scripts" / "init_sample_data.py"
    source = script.read_text(encoding="utf-8")

    assert "question__contains" not in source
    assert "SuggestedQuestion.query.filter_by(question=question)" in source
