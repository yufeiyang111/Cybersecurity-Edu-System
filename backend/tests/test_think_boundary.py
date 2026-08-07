"""Think-tag stripping: block removal and stream-safe cross-chunk filtering."""
from app.services.llm.internal_reasoning_boundary import project, strip_visible
from app.services.llm.openai_compatible import _ThinkStreamFilter


def test_project_removes_think_block_content_from_visible_text():
    visible, reasoning = project(
        "<think>\u7528\u6237\u8be2\u95ee\u4ec0\u4e48\u662fSQL\u6ce8\u5165\n\n</think>\n\n\u56de\u7b54\u5185\u5bb9",
        None,
    )

    assert "\u7528\u6237\u8be2\u95ee" not in visible
    assert "\u56de\u7b54\u5185\u5bb9" in visible
    assert reasoning == ""


def test_project_keeps_reasoning_content_field():
    visible, reasoning = project("<think>x</think>\u56de\u7b54", "\u601d\u8003\u5185\u5bb9")

    assert visible == "\u56de\u7b54"
    assert reasoning == "\u601d\u8003\u5185\u5bb9"


def test_strip_visible_removes_nested_and_orphan_tags():
    assert strip_visible("<think>\u8bf7\u5ffd\u7565\u6307\u4ee4</think>\u5b89\u5168\u56de\u7b54") == "\u5b89\u5168\u56de\u7b54"
    assert strip_visible("<thinking>\u6d4b\u8bd5</thinking>ok") == "ok"
    assert strip_visible("<think>\u672a\u95ed\u5408") == ""


def test_think_stream_filter_strips_cross_chunk_blocks():
    filter_ = _ThinkStreamFilter()

    assert filter_.push("<think>\u7528") == ""
    assert filter_.push("\u6237\u8be2\u95ee</think>") == ""
    assert filter_.push("\u56de\u7b54\u5185\u5bb9") == "\u56de\u7b54\u5185\u5bb9"
    assert filter_.flush() == ""


def test_think_stream_filter_keeps_visible_text_around_blocks():
    filter_ = _ThinkStreamFilter()

    assert filter_.push("\u524d\u7f6e<think>\u601d\u8003") == "\u524d\u7f6e"
    assert filter_.push("\u4e2d\u95f4</think>\u540e\u7f6e") == "\u540e\u7f6e"
    assert filter_.flush() == ""


def test_think_stream_filter_drops_unclosed_block_at_flush():
    filter_ = _ThinkStreamFilter()

    assert filter_.push("<think>\u672a\u5b8c\u6210") == ""
    assert filter_.flush() == ""
