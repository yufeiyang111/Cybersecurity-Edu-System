# -*- coding: utf-8 -*-
"""Redactor for streaming reasoning deltas before they reach the browser.

Design (spec §3.3): reasoning text is a live-only channel. Every delta must be
redacted before pushing; if a delta cannot be safely redacted it is dropped
(returns None). Deltas must never reach agent_events payloads, logs or audit.
"""
from __future__ import annotations

import re

_SENSITIVE_PATTERNS = (
    # OpenAI-style secret keys
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}\b"),
    # Bearer / Basic tokens
    re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9_\-\.\+/=]{12,}\b"),
    # Authorization / Cookie headers
    re.compile(r"(?i)\b(Authorization|Set-Cookie|Cookie|x-api-key)\s*[:=]\s*[^\s,;]{8,}"),
    # explicit key/value assignments
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret|password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    # private key blocks
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.DOTALL),
    # long high-entropy hex/base64-looking strings (>= 32 chars)
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
)

_REDACTED = "[REDACTED]"


def redact_reasoning(text: str) -> str | None:
    """Redact sensitive content from one reasoning delta.

    Returns the redacted text, or None when the delta cannot be safely
    processed (empty after redaction or still containing sensitive patterns).
    """
    if not text:
        return None
    redacted = text
    for pattern in _SENSITIVE_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    if not redacted.strip():
        return None
    if _still_sensitive(redacted):
        return None
    return redacted


def _still_sensitive(text: str) -> bool:
    """True when redaction left a sensitive pattern intact (drop the delta)."""
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(text):
            return True
    return False
