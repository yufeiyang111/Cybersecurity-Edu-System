"""Security workbench route package with one shared public Blueprint."""

from flask import Blueprint, current_app, jsonify

projects_bp = Blueprint("projects", __name__)


@projects_bp.before_request
def _check_security_workbench_enabled():
    """安全工作台熔断开关拦截：关闭时所有安全接口均直接熔断拒绝。"""
    if not current_app.config.get("SECURITY_WORKBENCH_ENABLED", True):
        return jsonify({
            "error": "安全工作台功能暂未开放或已熔断下线",
            "code": "FEATURE_DISABLED",
            "message": "安全工作台功能已临时下线维护"
        }), 503


__all__ = ["projects_bp"]

