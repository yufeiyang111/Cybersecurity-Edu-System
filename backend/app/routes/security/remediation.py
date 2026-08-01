"""Human-reviewable remediation suggestion endpoints."""
from __future__ import annotations

from datetime import datetime

from flask import current_app, jsonify
from app.services.rate_limit import rate_limit
from flask_jwt_extended import jwt_required

from app import db
from app.models.security import AuditEvent, RemediationSuggestion
from app.services.remediation_engine import RemediationService

from . import projects_bp
from .common import (
    AuthorizationError,
    MAX_REVIEW_COMMENT_CHARS,
    PROJECT_ROLES,
    READ_ROLES,
    _current_user_id,
    _finding_or_404,
    _json_object,
    _list_params,
    _optional_text,
    _pagination_payload,
    _required_text,
    _suggestion_or_404,
)

@projects_bp.route("/findings/<int:finding_id>/suggestions", methods=["POST"])
@jwt_required()
@rate_limit("security-expensive", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def generate_remediation_suggestion(finding_id: int):
    try:
        finding = _finding_or_404(finding_id, PROJECT_ROLES)
        if finding is None:
            return jsonify({"error": "Finding 不存在"}), 404
        actor_id = _current_user_id()
        suggestion = RemediationService().generate(finding.id, actor_id)
        db.session.add(
            AuditEvent(
                workspace_id=finding.task.snapshot.project.workspace_id,
                actor_id=actor_id,
                action="remediation.generated",
                target_type="remediation_suggestion",
                target_id=suggestion.id,
                metadata_json={
                    "finding_id": finding.id,
                    "provider": suggestion.provider,
                    "has_patch": bool(suggestion.patch_diff),
                    "citation_count": len(suggestion.citations_json or []),
                    "warning_count": len(suggestion.warning_codes_json or []),
                },
            )
        )
        db.session.commit()
        return jsonify({"suggestion": suggestion.to_dict()}), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("生成修复建议失败")
        return jsonify({"error": "生成修复建议失败"}), 500


@projects_bp.route("/findings/<int:finding_id>/suggestions", methods=["GET"])
@jwt_required()
def list_remediation_suggestions(finding_id: int):
    try:
        finding = _finding_or_404(finding_id, READ_ROLES)
        if finding is None:
            return jsonify({"error": "Finding 不存在"}), 404
        limit, offset = _list_params()
        query = RemediationSuggestion.query.filter_by(finding_id=finding.id)
        total = query.count()
        suggestions = (
            query.order_by(RemediationSuggestion.created_at.desc(), RemediationSuggestion.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return jsonify(
            {
                "items": [suggestion.to_dict() for suggestion in suggestions],
                "pagination": _pagination_payload(total=total, limit=limit, offset=offset),
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/suggestions/<int:suggestion_id>/review", methods=["POST"])
@jwt_required()
def review_remediation_suggestion(suggestion_id: int):
    try:
        suggestion = _suggestion_or_404(suggestion_id, PROJECT_ROLES)
        if suggestion is None:
            return jsonify({"error": "修复建议不存在"}), 404
        data = _json_object()
        review_state = _required_text(data, "review_state", 64)
        if review_state not in {"accepted", "rejected", "needs_revision"}:
            return jsonify({"error": "review_state 必须是 accepted、rejected 或 needs_revision"}), 400
        review_comment = _optional_text(data, "comment", MAX_REVIEW_COMMENT_CHARS)
        reviewer_id = _current_user_id()
        suggestion.review_state = review_state
        suggestion.reviewer_id = reviewer_id
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.review_comment = review_comment
        db.session.add(
            AuditEvent(
                workspace_id=suggestion.finding.task.snapshot.project.workspace_id,
                actor_id=reviewer_id,
                action="remediation.reviewed",
                target_type="remediation_suggestion",
                target_id=suggestion.id,
                metadata_json={
                    "review_state": review_state,
                    "has_comment": bool(review_comment),
                },
            )
        )
        db.session.commit()
        return jsonify({"suggestion": suggestion.to_dict()})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("审核修复建议失败")
        return jsonify({"error": "审核修复建议失败"}), 500
