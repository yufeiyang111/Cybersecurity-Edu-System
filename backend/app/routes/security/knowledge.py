"""Governed security knowledge source and document endpoints."""
from __future__ import annotations

from flask import current_app, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.security import AuditEvent, SecurityKnowledgeDocument, SecurityKnowledgeSource
from app.services.security_knowledge import SecurityKnowledgeIndex

from . import projects_bp
from .common import (
    AuthorizationError,
    KNOWLEDGE_ADMIN_ROLES,
    MAX_KNOWLEDGE_DOCUMENT_CHARS,
    _current_user_id,
    _document_tags,
    _effective_range_is_valid,
    _json_object,
    _knowledge_document_or_404,
    _knowledge_source_or_404,
    _list_params,
    _optional_bool,
    _optional_datetime,
    _optional_text,
    _pagination_payload,
    _required_text,
    _source_uri,
    get_or_create_personal_workspace,
    require_workspace_role,
)

@projects_bp.route("/knowledge/sources", methods=["POST"])
@jwt_required()
def create_knowledge_source():
    try:
        data = _json_object()
        user_id = _current_user_id()
        workspace = get_or_create_personal_workspace(user_id)
        require_workspace_role(workspace.id, user_id, KNOWLEDGE_ADMIN_ROLES)
        effective_from = _optional_datetime(data, "effective_from")
        effective_until = _optional_datetime(data, "effective_until")
        if not _effective_range_is_valid(effective_from, effective_until):
            return jsonify({"error": "effective_until 不能早于 effective_from"}), 400
        source = SecurityKnowledgeSource(
            workspace_id=workspace.id,
            name=_required_text(data, "name", 255),
            source_type=_required_text(data, "source_type", 64),
            source_uri=_source_uri(data),
            license_name=_optional_text(data, "license_name", 255),
            source_version=_required_text(data, "source_version", 255),
            is_active=_optional_bool(data, "is_active", True),
            published_at=_optional_datetime(data, "published_at"),
            effective_from=effective_from,
            effective_until=effective_until,
        )
        db.session.add(source)
        db.session.flush()
        db.session.add(
            AuditEvent(
                workspace_id=workspace.id,
                actor_id=user_id,
                action="knowledge.source_created",
                target_type="security_knowledge_source",
                target_id=source.id,
                metadata_json={
                    "source_type": source.source_type,
                    "source_version": source.source_version,
                    "is_active": bool(source.is_active),
                },
            )
        )
        db.session.commit()
        return jsonify({"source": source.to_dict()}), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("创建安全知识源失败")
        return jsonify({"error": "创建安全知识源失败"}), 500


@projects_bp.route("/knowledge/sources", methods=["GET"])
@jwt_required()
def list_knowledge_sources():
    try:
        user_id = _current_user_id()
        workspace = get_or_create_personal_workspace(user_id)
        require_workspace_role(workspace.id, user_id, KNOWLEDGE_ADMIN_ROLES)
        limit, offset = _list_params()
        query = SecurityKnowledgeSource.query.filter_by(workspace_id=workspace.id)
        total = query.count()
        sources = (
            query.order_by(SecurityKnowledgeSource.updated_at.desc(), SecurityKnowledgeSource.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return jsonify(
            {
                "items": [source.to_dict() for source in sources],
                "pagination": _pagination_payload(total=total, limit=limit, offset=offset),
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/knowledge/sources/<int:source_id>", methods=["PUT"])
@jwt_required()
def update_knowledge_source(source_id: int):
    """更新知识源元数据，不改变既有文档版本。"""
    try:
        source = _knowledge_source_or_404(source_id)
        if source is None:
            return jsonify({"error": "知识来源不存在"}), 404
        data = _json_object()
        if not any(key in data for key in (
            "name",
            "source_type",
            "source_uri",
            "license_name",
            "source_version",
            "is_active",
            "published_at",
            "effective_from",
            "effective_until",
        )):
            return jsonify({"error": "没有需要更新的字段"}), 400
        effective_from = _optional_datetime(data, "effective_from")
        effective_until = _optional_datetime(data, "effective_until")
        if not _effective_range_is_valid(effective_from, effective_until):
            return jsonify({"error": "effective_until 不能早于 effective_from"}), 400
        if "name" in data:
            source.name = _required_text(data, "name", 255)
        if "source_type" in data:
            source.source_type = _required_text(data, "source_type", 64)
        if "source_uri" in data:
            source.source_uri = _source_uri(data)
        if "license_name" in data:
            source.license_name = _optional_text(data, "license_name", 255)
        if "source_version" in data:
            source.source_version = _required_text(data, "source_version", 255)
        if "is_active" in data:
            source.is_active = _optional_bool(data, "is_active", True)
        if "published_at" in data:
            source.published_at = _optional_datetime(data, "published_at")
        if "effective_from" in data:
            source.effective_from = effective_from
        if "effective_until" in data:
            source.effective_until = effective_until
        db.session.add(
            AuditEvent(
                workspace_id=source.workspace_id,
                actor_id=_current_user_id(),
                action="knowledge.source_updated",
                target_type="security_knowledge_source",
                target_id=source.id,
                metadata_json={
                    "source_type": source.source_type,
                    "source_version": source.source_version,
                    "is_active": bool(source.is_active),
                },
            )
        )
        db.session.commit()
        return jsonify({"source": source.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("更新安全知识源失败")
        return jsonify({"error": "更新安全知识源失败"}), 500


@projects_bp.route("/knowledge/sources/<int:source_id>", methods=["DELETE"])
@jwt_required()
def delete_knowledge_source(source_id: int):
    """删除知识源及其全部文档，并同步清理向量索引。"""
    try:
        source = _knowledge_source_or_404(source_id)
        if source is None:
            return jsonify({"error": "知识来源不存在"}), 404
        document_ids = [document.id for document in source.documents]
        for document_id in document_ids:
            try:
                SecurityKnowledgeIndex().delete(document_id)
            except Exception:
                current_app.logger.warning(
                    "Security knowledge vector delete skipped (document_id=%s)", document_id
                )
        db.session.add(
            AuditEvent(
                workspace_id=source.workspace_id,
                actor_id=_current_user_id(),
                action="knowledge.source_deleted",
                target_type="security_knowledge_source",
                target_id=source.id,
                metadata_json={"document_count": len(document_ids)},
            )
        )
        db.session.delete(source)
        db.session.commit()
        return jsonify({"deleted": True})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except Exception:
        db.session.rollback()
        current_app.logger.exception("删除安全知识源失败")
        return jsonify({"error": "删除安全知识源失败"}), 500


@projects_bp.route("/knowledge/sources/<int:source_id>/documents", methods=["POST"])
@jwt_required()
def create_knowledge_document(source_id: int):
    try:
        source = _knowledge_source_or_404(source_id, KNOWLEDGE_ADMIN_ROLES)
        if source is None:
            return jsonify({"error": "知识来源不存在"}), 404
        data = _json_object()
        effective_from = _optional_datetime(data, "effective_from")
        effective_until = _optional_datetime(data, "effective_until")
        if not _effective_range_is_valid(effective_from, effective_until):
            return jsonify({"error": "effective_until 不能早于 effective_from"}), 400
        document = SecurityKnowledgeDocument(
            source_id=source.id,
            document_version=_required_text(data, "document_version", 255),
            title=_required_text(data, "title", 500),
            content=_required_text(data, "content", MAX_KNOWLEDGE_DOCUMENT_CHARS),
            summary=_optional_text(data, "summary", 4_000),
            tags_json=_document_tags(data),
            is_active=_optional_bool(data, "is_active", True),
            effective_from=effective_from,
            effective_until=effective_until,
        )
        db.session.add(document)
        db.session.flush()
        db.session.add(
            AuditEvent(
                workspace_id=source.workspace_id,
                actor_id=_current_user_id(),
                action="knowledge.document_created",
                target_type="security_knowledge_document",
                target_id=document.id,
                metadata_json={
                    "source_id": source.id,
                    "document_version": document.document_version,
                    "is_active": bool(document.is_active),
                    "tags_count": len(document.tags_json or []),
                },
            )
        )
        db.session.commit()
        try:
            SecurityKnowledgeIndex().upsert(document)
        except Exception:
            current_app.logger.warning("Security knowledge vector indexing skipped (document_id=%s)", document.id)
        return jsonify({"document": document.to_dict()}), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "知识文档版本已存在"}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("创建安全知识文档失败")
        return jsonify({"error": "创建安全知识文档失败"}), 500


@projects_bp.route("/knowledge/sources/<int:source_id>/documents", methods=["GET"])
@jwt_required()
def list_knowledge_documents(source_id: int):
    try:
        source = _knowledge_source_or_404(source_id, KNOWLEDGE_ADMIN_ROLES)
        if source is None:
            return jsonify({"error": "知识来源不存在"}), 404
        limit, offset = _list_params()
        query = SecurityKnowledgeDocument.query.filter_by(source_id=source.id)
        total = query.count()
        documents = (
            query.order_by(SecurityKnowledgeDocument.updated_at.desc(), SecurityKnowledgeDocument.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return jsonify(
            {
                "items": [document.to_dict() for document in documents],
                "pagination": _pagination_payload(total=total, limit=limit, offset=offset),
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route(
    "/knowledge/sources/<int:source_id>/documents/<int:document_id>",
    methods=["GET"],
)
@jwt_required()
def get_knowledge_document(source_id: int, document_id: int):
    """返回单个知识文档，正文仅在显式请求时回显。"""
    try:
        document = _knowledge_document_or_404(source_id, document_id, KNOWLEDGE_ADMIN_ROLES)
        if document is None:
            return jsonify({"error": "知识文档不存在"}), 404
        return jsonify({"document": document.to_dict(include_content=True)})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route(
    "/knowledge/sources/<int:source_id>/documents/<int:document_id>",
    methods=["PUT"],
)
@jwt_required()
def update_knowledge_document(source_id: int, document_id: int):
    """更新知识文档正文与元数据，并刷新向量索引。"""
    try:
        document = _knowledge_document_or_404(source_id, document_id)
        if document is None:
            return jsonify({"error": "知识文档不存在"}), 404
        data = _json_object()
        if not any(key in data for key in (
            "document_version",
            "title",
            "content",
            "summary",
            "tags",
            "is_active",
            "effective_from",
            "effective_until",
        )):
            return jsonify({"error": "没有需要更新的字段"}), 400
        effective_from = _optional_datetime(data, "effective_from")
        effective_until = _optional_datetime(data, "effective_until")
        if not _effective_range_is_valid(effective_from, effective_until):
            return jsonify({"error": "effective_until 不能早于 effective_from"}), 400
        if "document_version" in data:
            document.document_version = _required_text(data, "document_version", 255)
        if "title" in data:
            document.title = _required_text(data, "title", 500)
        if "content" in data:
            document.content = _required_text(data, "content", MAX_KNOWLEDGE_DOCUMENT_CHARS)
        if "summary" in data:
            document.summary = _optional_text(data, "summary", 4_000)
        if "tags" in data:
            document.tags_json = _document_tags(data)
        if "is_active" in data:
            document.is_active = _optional_bool(data, "is_active", True)
        if "effective_from" in data:
            document.effective_from = effective_from
        if "effective_until" in data:
            document.effective_until = effective_until
        db.session.add(
            AuditEvent(
                workspace_id=document.source.workspace_id,
                actor_id=_current_user_id(),
                action="knowledge.document_updated",
                target_type="security_knowledge_document",
                target_id=document.id,
                metadata_json={
                    "source_id": source_id,
                    "document_version": document.document_version,
                    "is_active": bool(document.is_active),
                },
            )
        )
        db.session.commit()
        try:
            SecurityKnowledgeIndex().upsert(document)
        except Exception:
            current_app.logger.warning("Security knowledge vector indexing skipped (document_id=%s)", document.id)
        return jsonify({"document": document.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "知识文档版本已存在"}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("更新安全知识文档失败")
        return jsonify({"error": "更新安全知识文档失败"}), 500


@projects_bp.route(
    "/knowledge/sources/<int:source_id>/documents/<int:document_id>",
    methods=["DELETE"],
)
@jwt_required()
def delete_knowledge_document(source_id: int, document_id: int):
    """删除知识文档并同步清理向量索引。"""
    try:
        document = _knowledge_document_or_404(source_id, document_id)
        if document is None:
            return jsonify({"error": "知识文档不存在"}), 404
        db.session.add(
            AuditEvent(
                workspace_id=document.source.workspace_id,
                actor_id=_current_user_id(),
                action="knowledge.document_deleted",
                target_type="security_knowledge_document",
                target_id=document.id,
                metadata_json={"source_id": source_id},
            )
        )
        db.session.delete(document)
        db.session.commit()
        try:
            SecurityKnowledgeIndex().delete(document_id)
        except Exception:
            current_app.logger.warning("Security knowledge vector delete skipped (document_id=%s)", document_id)
        return jsonify({"deleted": True})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except Exception:
        db.session.rollback()
        current_app.logger.exception("删除安全知识文档失败")
        return jsonify({"error": "删除安全知识文档失败"}), 500
