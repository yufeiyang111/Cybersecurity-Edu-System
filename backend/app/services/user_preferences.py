"""Validation and persistence for per-user chat preferences."""
from app import db
from app.models.user import UserPreference

DEFAULTS = {
    "theme": "system",
    "color_preset": "default",
    "font_family": "auto",
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
}
OPTIONS = {
    "theme": {"system", "light", "dark", "sepia"},
    "color_preset": {
        "default", "anthropic", "simple", "night", "rose", "lake", "sunset", "forest", "sea", "lavender",
        "emerald", "gold", "candy",
    },
    "font_family": {"auto", "sans", "serif"},
    "border_radius": {"auto", "0", "0.3", "0.5", "0.75", "1.0"},
    "content_density": {"compact", "standard", "comfortable"},
    "content_width": {"narrow", "standard", "wide"},
    "language": {"zh-CN", "en", "fr", "ru", "ja", "vi", "zh-TW"},
    "response_style": {"professional", "concise", "teaching", "analytical"},
}
TEXT_LIMITS = {"about_user": 1000, "response_preferences": 2000, "custom_prompt": 4000}
BOOLEAN_FIELDS = ("show_citations", "show_security_warnings", "persistent_memory_enabled")


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


def reset(preferences):
    for field, value in DEFAULTS.items():
        setattr(preferences, field, value)
