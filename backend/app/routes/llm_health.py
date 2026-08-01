"""受保护的 LLM Provider 健康检查路由。"""
from __future__ import annotations

from flask import Blueprint, jsonify
from app.services.rate_limit import rate_limit
from flask_jwt_extended import jwt_required

from app.services.llm.health import LLMProviderHealthChecker, ProviderHealthStatus

llm_health_bp = Blueprint("llm_health", __name__)
_HEALTH_CHECKER_EXTENSION = "llm_provider_health_checker"


def get_health_checker() -> LLMProviderHealthChecker:
    """按 Flask 应用实例复用健康检查器及其 Provider 冷却状态。"""
    from flask import current_app

    checker = current_app.extensions.get(_HEALTH_CHECKER_EXTENSION)
    if checker is None:
        checker = LLMProviderHealthChecker(config=current_app.config)
        current_app.extensions[_HEALTH_CHECKER_EXTENSION] = checker
    return checker


@llm_health_bp.get("/llm-providers")
@jwt_required()
def inspect_llm_providers():
    """返回被动配置检查结果。"""
    statuses = get_health_checker().inspect_configuration()
    return jsonify({"providers": [_serialize(status) for status in statuses]})


@llm_health_bp.post("/llm-providers/<provider_name>/check")
@jwt_required()
@rate_limit("security-expensive", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def check_llm_provider(provider_name: str):
    """执行一次受控的显式 Provider 连通性检查。"""
    status = get_health_checker().check_provider(provider_name)
    http_status = _http_status(status)
    return jsonify({"provider": _serialize(status)}), http_status


def _serialize(status: ProviderHealthStatus) -> dict:
    return status.to_dict()


def _http_status(status: ProviderHealthStatus) -> int:
    if status.status == "healthy":
        return 200
    if status.status == "rate_limited":
        return 429
    if status.status == "unsupported_provider":
        return 400
    if status.status == "not_configured":
        return 503
    return 502
