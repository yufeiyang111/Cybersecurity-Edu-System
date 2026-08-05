"""User-scoped LLM configuration, call log and analytics endpoints."""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.services.llm.call_logging import observe_provider
from app.services.llm.contracts import LLMRequest
from app.services.llm import analytics_service, provider_service
from app.services.rate_limit import rate_limit

logger = logging.getLogger(__name__)

# warning_code → (中文说明, 建议操作)
WARNING_DIAGNOSTICS: dict[str, tuple[str, str]] = {
    "LLM_PROVIDER_NON_SUCCESS": (
        "Provider 返回非 200 状态码",
        "请检查 base_url 是否正确、API Key 是否有权限、Provider 是否启用",
    ),
    "LLM_PROVIDER_TIMEOUT": (
        "Provider 请求超时",
        "请检查网络连通性，或在配置中调大 LLM_PROVIDER_CONNECT_TIMEOUT_SECONDS",
    ),
    "LLM_PROVIDER_REQUEST_FAILED": (
        "Provider 请求失败（网络错误）",
        "请检查 base_url 是否可访问、API Key 是否正确、服务是否上线",
    ),
    "LLM_PROVIDER_RESPONSE_TOO_LARGE": (
        "Provider 返回体超出最大允许大小",
        "请在配置中调大 LLM_PROVIDER_MAX_RESPONSE_BYTES",
    ),
    "LLM_OUTPUT_INVALID": (
        "Provider 返回格式无效（非 JSON 或缺少必需字段）",
        "请确认 base_url 支持 OpenAI Chat Completions API 格式",
    ),
    "LLM_PROVIDER_RESPONSE_INVALID": (
        "Provider 流式响应格式无效",
        "请确认 base_url 支持 SSE 流式响应",
    ),
    "provider_error": (
        "Provider 返回了成功状态但内容不是 'OK'",
        "Provider 工作正常但响应内容异常，建议检查模型是否正确",
    ),
}


def _diag_warning(warning_code: str | None) -> dict[str, Any]:
    """返回 warning_code 的诊断信息。"""
    if not warning_code:
        return {"detail": None, "hint": None}
    entry = WARNING_DIAGNOSTICS.get(warning_code, (None, None))
    return {
        "detail": entry[0] if entry else f"未知错误码: {warning_code}",
        "hint": entry[1] if entry else "请查看服务端日志获取详细堆栈",
    }


def _build_test_extra(
    provider_config: Any,
    response: Any,
    user_id: int,
) -> dict[str, Any]:
    """构造测试接口的完整 extra 字典，写入结构化日志。"""
    diag = _diag_warning(response.warning_code)
    extra = {
        "event": "llm_provider_test",
        "user_id": user_id,
        "provider_id": provider_config.id,
        "provider_name": provider_config.name,
        "base_url": provider_config.base_url,
        "model": provider_config.model,
        "status": "healthy" if response.is_success else "unhealthy",
        "latency_ms": response.latency_ms,
        "warning_code": response.warning_code,
        "http_status_code": response.status_code,
        "diag_detail": diag["detail"],
        "diag_hint": diag["hint"],
    }
    if not response.is_success and response.warning_code == "LLM_PROVIDER_NON_SUCCESS":
        extra["_debug"] = (
            f"HTTP {response.status_code} from {provider_config.base_url} "
            f"(model={provider_config.model})"
        )
    return extra

llm_bp = Blueprint("llm", __name__)


@llm_bp.get("/providers")
@jwt_required()
def list_providers():
    user_id = _current_user_id()
    return jsonify({"providers": [item.to_dict() for item in provider_service.list_for_user(user_id)]})


@llm_bp.post("/providers")
@jwt_required()
def create_provider():
    try:
        provider = provider_service.create_for_user(
            _current_user_id(),
            request.get_json(silent=True) or {},
            allowed_hosts=_allowed_hosts(),
        )
        if provider.is_default:
            provider_service.set_default(provider)
        db.session.commit()
        return jsonify({"provider": provider.to_dict()}), 201
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except RuntimeError:
        db.session.rollback()
        return jsonify({"error": "服务器尚未配置 LLM 密钥加密服务"}), 503


@llm_bp.get("/providers/<int:provider_id>")
@jwt_required()
def get_provider(provider_id: int):
    provider = provider_service.get_for_user(provider_id, _current_user_id())
    if provider is None:
        return jsonify({"error": "LLM 配置不存在"}), 404
    return jsonify({"provider": provider.to_dict()})


@llm_bp.put("/providers/<int:provider_id>")
@jwt_required()
def update_provider(provider_id: int):
    provider = provider_service.get_for_user(provider_id, _current_user_id())
    if provider is None:
        return jsonify({"error": "LLM 配置不存在"}), 404
    try:
        provider_service.update_for_user(
            provider,
            request.get_json(silent=True) or {},
            allowed_hosts=_allowed_hosts(),
        )
        if provider.is_default:
            provider_service.set_default(provider)
        db.session.commit()
        return jsonify({"provider": provider.to_dict()})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except RuntimeError:
        db.session.rollback()
        return jsonify({"error": "服务器尚未配置 LLM 密钥加密服务"}), 503


@llm_bp.delete("/providers/<int:provider_id>")
@jwt_required()
def delete_provider(provider_id: int):
    provider = provider_service.get_for_user(provider_id, _current_user_id())
    if provider is None:
        return jsonify({"error": "LLM 配置不存在"}), 404
    provider_service.delete_for_user(provider)
    db.session.commit()
    return jsonify({"message": "LLM 配置已删除"})


@llm_bp.post("/providers/<int:provider_id>/default")
@jwt_required()
def set_default_provider(provider_id: int):
    provider = provider_service.get_for_user(provider_id, _current_user_id())
    if provider is None:
        return jsonify({"error": "LLM 配置不存在"}), 404
    provider_service.set_default(provider)
    db.session.commit()
    return jsonify({"provider": provider.to_dict()})


@llm_bp.post("/providers/<int:provider_id>/toggle")
@jwt_required()
def toggle_provider(provider_id: int):
    provider = provider_service.get_for_user(provider_id, _current_user_id())
    if provider is None:
        return jsonify({"error": "LLM 配置不存在"}), 404
    data = request.get_json(silent=True) or {}
    try:
        provider_service.toggle_enabled(provider, data.get("is_enabled"))
        db.session.commit()
        return jsonify({"provider": provider.to_dict()})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@llm_bp.post("/providers/<int:provider_id>/test")
@jwt_required()
@rate_limit("llm-provider-test", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def test_provider(provider_id: int):
    user_id = _current_user_id()
    provider_config = provider_service.get_for_user(provider_id, user_id)
    if provider_config is None:
        return jsonify({"error": "LLM 配置不存在"}), 404

    logger.info(
        "LLM provider test started (provider_id=%s, user_id=%s, base_url=%s, model=%s)",
        provider_id, user_id, provider_config.base_url, provider_config.model,
    )

    try:
        provider = provider_service.build_provider(
            provider_config,
            user_id=user_id,
            operation="health_check",
        )
        observed = observe_provider(provider, user_id=user_id, operation="health_check")
        response = observed.generate(
            LLMRequest(
                prompt="Return exactly: OK",
                system_prompt="This is a provider connectivity probe. Return exactly OK.",
                temperature=0.0,
                max_tokens=8,
                timeout_seconds=8,
            )
        )

        if response.is_success:
            status = "healthy"
            logger.info(
                "LLM provider test succeeded (provider_id=%s, latency_ms=%s, text=%r)",
                provider_id, response.latency_ms,
                response.text[:50] if response.text else None,
            )
        else:
            status = response.warning_code or "provider_error"
            extra = _build_test_extra(provider_config, response, user_id)
            logger.warning(
                "LLM provider test failed (provider_id=%(provider_id)s, "
                "warning_code=%(warning_code)s, http_status_code=%(http_status_code)s, "
                "latency_ms=%(latency_ms)s, detail=%(diag_detail)s, hint=%(diag_hint)s) "
                "[%(user_id)s] %(base_url)s model=%(model)s",
                extra,
            )

        provider_service.record_health_check(provider_config, status, response.latency_ms)
        db.session.commit()

        if response.is_success:
            diag = {
                "detail": "连接成功，Provider 正常响应",
                "hint": None,
            }
        else:
            diag = _diag_warning(response.warning_code)
            if not diag["detail"]:
                diag = {
                    "detail": "Provider 返回了无效响应（HTTP 200但内容为空或格式异常）",
                    "hint": "请检查 base_url 是否为正确的 Chat Completions 端点，模型名称是否正确",
                }
        return jsonify({
            "provider": provider_config.to_dict(),
            "check": {
                "status": status,
                "warning_code": response.warning_code,
                "latency_ms": response.latency_ms,
                "detail": diag["detail"],
                "hint": diag["hint"],
            },
        }), 200

    except RuntimeError:
        db.session.rollback()
        logger.warning(
            "LLM provider test failed: decryption error (provider_id=%s, user_id=%s). "
            "提示：请重新保存 API Key",
            provider_id, user_id,
        )
        return jsonify({"error": "LLM 配置无法解密，请重新保存 API Key"}), 503

    except Exception:
        db.session.rollback()
        logger.exception(
            "LLM provider test crashed unexpectedly (provider_id=%s, user_id=%s)",
            provider_id, user_id,
        )
        raise


@llm_bp.get("/logs")
@jwt_required()
def list_call_logs():
    try:
        pagination = analytics_service.list_logs(_current_user_id(), request.args.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "items": [item.to_dict() for item in pagination.items],
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
        }
    )


@llm_bp.get("/logs/summary")
@jwt_required()
def call_log_summary():
    try:
        payload = analytics_service.summary(_current_user_id(), request.args.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"summary": payload})


@llm_bp.get("/analytics")
@jwt_required()
def call_analytics():
    try:
        payload = analytics_service.analytics(_current_user_id(), request.args.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


def _current_user_id() -> int:
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError) as exc:
        raise ValueError("用户身份无效") from exc


def _allowed_hosts() -> list[str]:
    return [str(item) for item in current_app.config.get("LLM_PROVIDER_ALLOWED_HOSTS", [])]
