"""
帮助中心路由（薄层）

- 公开读取：分类树 / 单篇文档
- 管理员 CRUD：分类 + 文档
- 鉴权：所有写操作要求 JWT + admin 角色
- 审计：所有写操作记录 `audit_events`

业务逻辑统一委托给 `app.services.help_service`。
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app import db
from app.models.user import User
from app.services import help_service


help_bp = Blueprint("help", __name__)


# ---------------------- 公开读取 ----------------------

@help_bp.route("/help/tree", methods=["GET"])
def get_help_tree():
    tree = help_service.list_active_tree()
    return jsonify({"tree": tree}), 200


@help_bp.route("/help/documents/<slug>", methods=["GET"])
def get_help_document(slug: str):
    try:
        document = help_service.get_active_document(slug)
    except help_service.HelpDocumentNotFound:
        return jsonify({"error": "帮助文档不存在或未启用"}), 404
    return jsonify({"document": document.to_dict(include_content=True)}), 200


# ---------------------- 管理员：分类 ----------------------

@help_bp.route("/help/admin/tree", methods=["GET"])
@jwt_required()
def admin_get_help_tree():
    _require_admin_or_403()
    tree = help_service.list_admin_tree()
    return jsonify({"tree": tree}), 200


@help_bp.route("/help/admin/categories", methods=["POST"])
@jwt_required()
def admin_create_category():
    if not _is_admin():
        return jsonify({"error": "权限不足，仅管理员可创建分类"}), 403

    data = request.get_json(silent=True) or {}
    try:
        category = help_service.create_category(
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            description=data.get("description"),
            parent_id=data.get("parent_id"),
            sort_order=int(data.get("sort_order") or 0),
            is_active=_as_bool(data.get("is_active"), default=True),
        )
    except help_service.HelpValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except help_service.HelpCategoryNotFound as exc:
        return jsonify({"error": str(exc)}), 400

    _audit("create", "help_category", category.id, before=None, after=category.to_dict())
    return jsonify({"category": category.to_dict()}), 201


@help_bp.route("/help/admin/categories/<int:category_id>", methods=["PUT"])
@jwt_required()
def admin_update_category(category_id: int):
    if not _is_admin():
        return jsonify({"error": "权限不足，仅管理员可编辑分类"}), 403

    before = _category_snapshot(category_id)

    data = request.get_json(silent=True) or {}
    try:
        category = help_service.update_category(
            category_id,
            name=data.get("name"),
            description=data.get("description"),
            parent_id=data.get("parent_id"),
            sort_order=_as_int_or_none(data.get("sort_order")),
            is_active=_as_bool_or_none(data.get("is_active")),
        )
    except help_service.HelpCategoryNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except help_service.HelpValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    _audit("update", "help_category", category.id, before=before, after=category.to_dict())
    return jsonify({"category": category.to_dict()}), 200


@help_bp.route("/help/admin/categories/<int:category_id>", methods=["DELETE"])
@jwt_required()
def admin_delete_category(category_id: int):
    if not _is_admin():
        return jsonify({"error": "权限不足，仅管理员可删除分类"}), 403

    before = _category_snapshot(category_id)
    try:
        help_service.delete_category(category_id)
    except help_service.HelpCategoryNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except help_service.HelpCategoryInUse as exc:
        return jsonify({"error": str(exc)}), 409

    _audit("delete", "help_category", category_id, before=before, after=None)
    return jsonify({"message": "分类已删除"}), 200


# ---------------------- 管理员：文档 ----------------------

@help_bp.route("/help/admin/documents/<int:document_id>", methods=["GET"])
@jwt_required()
def admin_get_document(document_id: int):
    if not _is_admin():
        return jsonify({"error": "权限不足，仅管理员可读取文档"}), 403

    try:
        document = help_service.get_admin_document(document_id)
    except help_service.HelpDocumentNotFound as exc:
        return jsonify({"error": str(exc)}), 404

    return jsonify({"document": document.to_dict(include_content=True)}), 200


@help_bp.route("/help/admin/documents", methods=["POST"])
@jwt_required()
def admin_create_document():
    if not _is_admin():
        return jsonify({"error": "权限不足，仅管理员可创建文档"}), 403

    data = request.get_json(silent=True) or {}
    category_id = _as_int_or_none(data.get("category_id"))
    if category_id is None:
        return jsonify({"error": "缺少 category_id"}), 400

    try:
        document = help_service.create_document(
            slug=data.get("slug", ""),
            category_id=category_id,
            title=data.get("title", ""),
            summary=data.get("summary"),
            content=data.get("content", ""),
            sort_order=int(data.get("sort_order") or 0),
            is_active=_as_bool(data.get("is_active"), default=True),
            updated_by=_current_username(),
        )
    except help_service.HelpValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except help_service.HelpCategoryNotFound as exc:
        return jsonify({"error": str(exc)}), 400

    _audit("create", "help_document", document.id, before=None, after=document.to_dict())
    return jsonify({"document": document.to_dict()}), 201


@help_bp.route("/help/admin/documents/<int:document_id>", methods=["PUT"])
@jwt_required()
def admin_update_document(document_id: int):
    if not _is_admin():
        return jsonify({"error": "权限不足，仅管理员可编辑文档"}), 403

    before = _document_snapshot(document_id)

    data = request.get_json(silent=True) or {}
    try:
        document = help_service.update_document(
            document_id,
            title=data.get("title"),
            summary=data.get("summary"),
            content=data.get("content"),
            category_id=_as_int_or_none(data.get("category_id")),
            sort_order=_as_int_or_none(data.get("sort_order")),
            is_active=_as_bool_or_none(data.get("is_active")),
            updated_by=_current_username(),
        )
    except help_service.HelpDocumentNotFound as exc:
        return jsonify({"error": str(exc)}), 404
    except help_service.HelpValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except help_service.HelpCategoryNotFound as exc:
        return jsonify({"error": str(exc)}), 400

    _audit("update", "help_document", document.id, before=before, after=document.to_dict())
    return jsonify({"document": document.to_dict()}), 200


@help_bp.route("/help/admin/documents/<int:document_id>", methods=["DELETE"])
@jwt_required()
def admin_delete_document(document_id: int):
    if not _is_admin():
        return jsonify({"error": "权限不足，仅管理员可删除文档"}), 403

    before = _document_snapshot(document_id)
    try:
        help_service.delete_document(document_id)
    except help_service.HelpDocumentNotFound as exc:
        return jsonify({"error": str(exc)}), 404

    _audit("delete", "help_document", document_id, before=before, after=None)
    return jsonify({"message": "文档已删除"}), 200


# ---------------------- 内部工具 ----------------------

def _is_admin() -> bool:
    claims = get_jwt()
    return claims.get("role", "guest") == "admin"


def _require_admin_or_403():
    if not _is_admin():
        return _forbidden()
    return None


def _forbidden():
    return jsonify({"error": "权限不足"}), 403


def _current_username() -> str:
    identity = get_jwt_identity()
    if not identity or not str(identity).isdigit():
        return str(identity or "unknown")
    user = db.session.get(User, int(identity))
    return user.username if user else str(identity)


def _as_bool(value, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _as_bool_or_none(value):
    if value is None:
        return None
    return _as_bool(value, default=False)


def _as_int_or_none(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _category_snapshot(category_id: int):
    from app.models.help import HelpCategory

    category = db.session.get(HelpCategory, category_id)
    return category.to_dict() if category else None


def _document_snapshot(document_id: int):
    from app.models.help import HelpDocument

    document = db.session.get(HelpDocument, document_id)
    return document.to_dict(include_content=False) if document else None


def _audit(action: str, target_type: str, target_id: int, *, before, after) -> None:
    """写入结构化审计日志。

    帮助中心是全局资源，不绑定任何 workspace，因此不使用 `AuditEvent`
    （其 `workspace_id` 字段为 NOT NULL 外键）。改为写入应用日志，
    由运维侧的日志聚合负责检索与告警。
    """
    try:
        actor_id = _as_int_or_none(get_jwt_identity())
        current_app.logger.info(
            "help.audit action=%s target=%s id=%s actor=%s before=%s after=%s",
            action,
            target_type,
            target_id,
            actor_id,
            before,
            after,
        )
    except Exception:
        current_app.logger.exception("帮助中心审计日志写入失败")