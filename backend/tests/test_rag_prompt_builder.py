# -*- coding: utf-8 -*-
"""QA 提示词组装测试：XML 标签化结构 + 稳定前缀缓存友好 + 长度档位联动。"""
from __future__ import annotations

import pytest

from app.services.rag_prompt_builder import (
    DEFAULT_QA_MAX_TOKENS,
    SYSTEM_PROMPT,
    build_qa_messages,
    output_guidance_for,
    resolve_qa_max_tokens,
)

_TAG_ORDER = [
    "retrieved_context",
    "conversation_history",
    "user_context",
    "memories",
    "question",
    "output_guidance",
]


def _messages(**kwargs):
    kwargs.setdefault("query", "什么是SQL注入？")
    kwargs.setdefault("context", "参考资料内容")
    return build_qa_messages(**kwargs)


def test_system_prompt_is_stable_and_contains_no_user_data():
    messages = _messages(
        user_preferences={"about_user": "我是安全工程师"},
        memories=[{"content": "用户喜欢详细回答"}],
    )
    system_content = messages[0]["content"]
    assert system_content == SYSTEM_PROMPT
    assert "我是安全工程师" not in system_content
    assert "用户喜欢详细回答" not in system_content
    assert "什么是SQL注入" not in system_content
    assert "参考资料内容" not in system_content


def test_user_prompt_uses_xml_tags_in_fixed_order():
    messages = _messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_content = messages[1]["content"]
    first_positions = [user_content.index(f"<{tag}>") for tag in _TAG_ORDER]
    assert first_positions == sorted(first_positions)
    for tag in _TAG_ORDER:
        assert f"<{tag}>" in user_content
        assert f"</{tag}>" in user_content
    assert "什么是SQL注入" in user_content


def test_user_prompt_includes_preferences_and_memories_in_tags():
    messages = _messages(
        user_preferences={"about_user": "我是安全工程师", "response_style": "analytical"},
        memories=[{"content": "用户喜欢详细回答"}, {"content": "用户在金融行业工作"}],
    )
    user_content = messages[1]["content"]
    user_context = user_content.split("<user_context>")[1].split("</user_context>")[0]
    memories = user_content.split("<memories>")[1].split("</memories>")[0]
    assert "我是安全工程师" in user_context
    assert "analytical" in user_context
    assert "用户喜欢详细回答" in memories
    assert "用户在金融行业工作" in memories


def test_user_prompt_uses_placeholders_when_empty():
    messages = _messages(
        context="  ",
        conversation_history=None,
        user_preferences=None,
        memories=None,
    )
    user_content = messages[1]["content"]
    assert "（无）" in user_content
    assert "（无）" in user_content.split("<conversation_history>")[1].split("</conversation_history>")[0]
    assert "（无）" in user_content.split("<memories>")[1].split("</memories>")[0]


def test_history_is_included_and_bounded_to_five_turns():
    history = [
        {"role": "user", "content": f"历史问题{i}"}
        for i in range(8)
    ]
    messages = _messages(conversation_history=history, include_history=True)
    user_content = messages[1]["content"]
    history_section = user_content.split("<conversation_history>")[1].split("</conversation_history>")[0]
    assert "历史问题7" in history_section
    assert "历史问题0" not in history_section


def test_history_skipped_when_include_history_false():
    history = [{"role": "user", "content": "历史问题"}]
    messages = _messages(conversation_history=history, include_history=False)
    history_section = messages[1]["content"].split("<conversation_history>")[1].split("</conversation_history>")[0]
    assert history_section.strip() == "（无）"


def test_output_guidance_tiers_follow_max_tokens():
    assert "详尽完整" in output_guidance_for(DEFAULT_QA_MAX_TOKENS)
    assert "详尽完整" in output_guidance_for(8192)
    assert "详尽完整" in output_guidance_for(384000)
    assert "适中" in output_guidance_for(4096)
    assert "简洁" in output_guidance_for(1)
    assert "简洁" in output_guidance_for(1024)


def test_qa_max_tokens_resolution_defaults_and_invalid_values():
    assert resolve_qa_max_tokens(None) == DEFAULT_QA_MAX_TOKENS
    assert resolve_qa_max_tokens({}) == DEFAULT_QA_MAX_TOKENS
    assert resolve_qa_max_tokens({"qa_max_tokens": None}) == DEFAULT_QA_MAX_TOKENS
    assert resolve_qa_max_tokens({"qa_max_tokens": 8192}) == 8192
    assert resolve_qa_max_tokens({"qa_max_tokens": 384000}) == 384000
    assert resolve_qa_max_tokens({"qa_max_tokens": 1}) == 1
    for invalid in (0, -1, 384001, 500000, "8192", True, 3.14):
        assert resolve_qa_max_tokens({"qa_max_tokens": invalid}) == DEFAULT_QA_MAX_TOKENS


def test_system_prompt_stable_across_different_user_inputs():
    prompts = set()
    for index, preferences in enumerate(
        (None, {"about_user": "A"}, {"custom_prompt": "B"}, {"qa_max_tokens": 1024})
    ):
        messages = _messages(user_preferences=preferences, query=f"查询{index}")
        prompts.add(messages[0]["content"])
    assert len(prompts) == 1


def test_output_guidance_in_user_message_uses_max_tokens_preference():
    messages = _messages(user_preferences={"qa_max_tokens": 1024})
    guidance = messages[1]["content"].split("<output_guidance>")[1].split("</output_guidance>")[0]
    assert "简洁" in guidance
    messages = _messages(user_preferences={"qa_max_tokens": 32768})
    guidance = messages[1]["content"].split("<output_guidance>")[1].split("</output_guidance>")[0]
    assert "详尽完整" in guidance
