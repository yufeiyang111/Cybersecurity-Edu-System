# -*- coding: utf-8 -*-
"""encoding_guard：供应商响应乱码检测与自动修复测试。"""
from app.services.llm.encoding_guard import safe_decode


def _mojibake_latin1(text: str) -> str:
    """模拟 UTF-8 中文被 ISO-8859-1 误读后的乱码文本。"""
    return text.encode("utf-8").decode("latin-1")


def test_safe_decode_keeps_normal_utf8_bytes():
    assert safe_decode("安全分析".encode("utf-8")) == "安全分析"


def test_safe_decode_keeps_normal_ascii():
    assert safe_decode(b"Return exactly: OK") == "Return exactly: OK"
    assert safe_decode("safe answer") == "safe answer"


def test_safe_decode_rejects_latin_words_with_accents():
    assert safe_decode("caf\u00e9 r\u00e9sum\u00e9") == "caf\u00e9 r\u00e9sum\u00e9"


def test_safe_decode_repairs_latin1_mojibake_str():
    broken = _mojibake_latin1("开垦的用户信息安全问题分析")
    assert "\ufffd" not in broken
    assert safe_decode(broken) == "开垦的用户信息安全问题分析"


def test_safe_decode_repairs_latin1_mojibake_bytes():
    broken = _mojibake_latin1("建议：开启双重认证").encode("utf-8")
    assert safe_decode(broken) == "建议：开启双重认证"


def test_safe_decode_falls_back_to_gb18030_for_gbk_bytes():
    gbk_bytes = "个人隐私泄露".encode("gbk")
    assert safe_decode(gbk_bytes) == "个人隐私泄露"


def test_safe_decode_does_not_repair_ascii_with_few_accent_chars():
    mixed = "order 2 caf\u00e9 for the team"
    assert safe_decode(mixed) == mixed
