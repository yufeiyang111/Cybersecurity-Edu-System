"""Validation and persistence for per-user chat preferences."""
from app import db
from app.models.user import UserPreference

DEFAULTS = {
    "theme": "system",
    "color_preset": "default",
    "font_family": "auto",
    "font_size": "medium",
    "border_radius": "auto",
    "content_density": "standard",
    "content_width": "standard",
    "language": "zh-CN",
    "about_user": "",
    "response_preferences": "",
    "custom_prompt": "",
    "response_style": "professional",
    "show_citations": True,
    "show_security_warnings": True,
    "persistent_memory_enabled": False,
    "qa_max_tokens": None,
}
OPTIONS = {
    "theme": {"system", "light", "dark", "sepia"},
    "color_preset": {
        "default", "anthropic", "simple", "night", "rose", "lake", "sunset", "forest", "sea", "lavender",
        "emerald", "gold", "candy",
    },
    "font_family": {"auto", "sans", "serif"},
    "font_size": {"small", "medium", "large"},
    "border_radius": {"auto", "0", "0.3", "0.5", "0.75", "1.0"},
    "content_density": {"compact", "standard", "comfortable"},
    "content_width": {"narrow", "standard", "wide"},
    "language": {"zh-CN", "en", "fr", "ru", "ja", "vi", "zh-TW"},
    "response_style": {"professional", "concise", "teaching", "analytical"},
}
TEXT_LIMITS = {"about_user": 1000, "response_preferences": 2000, "custom_prompt": 4000}
BOOLEAN_FIELDS = ("show_citations", "show_security_warnings", "persistent_memory_enabled")
QA_MAX_TOKENS_DEFAULT = 16384
QA_MAX_TOKENS_LIMITS = (256, 32768)


def _validated_qa_max_tokens(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("qa_max_tokens 必须是整数")
    low, high = QA_MAX_TOKENS_LIMITS
    if not low <= value <= high:
        raise ValueError(f"qa_max_tokens 必须在 {low} 至 {high} 之间")
    return value


def get_or_create(user_id):
    preferences = UserPreference.query.filter_by(user_id=user_id).first()
    if preferences:
        return preferences
    preferences = UserPreference(user_id=user_id, **DEFAULTS)
    db.session.add(preferences)
    db.session.flush()
    return preferences


def update(preferences, data):
    for field, allowed in OPTIONS.items():
        if field in data:
            value = data[field]
            if value not in allowed:
                raise ValueError(f"{field} 的取值无效")
            setattr(preferences, field, value)
    for field, max_length in TEXT_LIMITS.items():
        if field in data:
            value = data[field]
            if not isinstance(value, str) or len(value) > max_length:
                raise ValueError(f"{field} 长度超出限制")
            setattr(preferences, field, value)
    for field in BOOLEAN_FIELDS:
        if field in data:
            if not isinstance(data[field], bool):
                raise ValueError(f"{field} 必须是布尔值")
            setattr(preferences, field, data[field])
    if "qa_max_tokens" in data:
        setattr(preferences, "qa_max_tokens", _validated_qa_max_tokens(data["qa_max_tokens"]))


def reset(preferences):
    for field, value in DEFAULTS.items():
        setattr(preferences, field, value)
