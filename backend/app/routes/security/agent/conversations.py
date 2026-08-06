"""Multi-turn conversation endpoints: create conversation, messages, turns+runs."""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.conversation import AgentConversation
from app.models.security import SecurityProject
from app.services.security_agent.conversation_service import (
    ConversationError,
    ConversationService,
)

from .. import projects_bp
from ..common import (
    AuthorizationError,
    PROJECT_ROLES,
    READ_ROLES,
    _current_user_id,
    _json_object,
    require_workspace_role,
)

_service = ConversationService()


def _conversation_or_404(
    conversation_id: int, allowed_roles: set[str] = READ_ROLES
) -> AgentConversation | None:
    conversation = db.session.get(AgentConversation, conversation_id)
    if conversation is None:
        return None
    require_workspace_role(conversation.workspace_id, _current_user_id(), allowed_roles)
    return conversation


@projects_bp.route("/projects/<int:project_id>/agent-conversations", methods=["POST"])
@jwt_required()
def create_agent_conversation(project_id: int):
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        user_id = _current_user_id()
        require_workspace_role(project.workspace_id, user_id, PROJECT_ROLES)

        data = _json_object()
        title = data.get("title")
        if title is not None and (not isinstance(title, str) or len(title.strip()) > 200):
            return jsonify({"error": "会话标题长度不能超过 200 个字符"}), 400

        conversation = _service.create_conversation(
            project=project,
            user_id=user_id,
            title=(title or "").strip(),
        )
        return jsonify({"conversation": conversation.to_dict()}), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/projects/<int:project_id>/agent-conversations", methods=["GET"])
@jwt_required()
def list_project_agent_conversations(project_id: int):
    try:
        project = db.session.get(SecurityProject, project_id)
        if project is None:
            return jsonify({"error": "项目不存在"}), 404
        require_workspace_role(project.workspace_id, _current_user_id(), READ_ROLES)

        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        if page < 1 or not 1 <= page_size <= 100:
            return jsonify({"error": "page 不能小于 1，page_size 必须在 1 至 100 之间"}), 400

        conversations, total = _service.list_conversations(
            project_id, page=page, page_size=page_size
        )
        return jsonify(
            {
                "items": [conversation.to_dict() for conversation in conversations],
                "pagination": {"total": total, "page": page, "page_size": page_size},
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/agent-conversations/<int:conversation_id>", methods=["GET"])
@jwt_required()
def get_agent_conversation(conversation_id: int):
    try:
        conversation = _conversation_or_404(conversation_id)
        if conversation is None:
            return jsonify({"error": "会话不存在"}), 404
        payload = conversation.to_dict()
        payload["turns"] = [turn.to_dict() for turn in conversation.turns]
        return jsonify({"conversation": payload})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-conversations/<int:conversation_id>/messages", methods=["GET"])
@jwt_required()
def list_agent_conversation_messages(conversation_id: int):
    try:
        conversation = _conversation_or_404(conversation_id)
        if conversation is None:
            return jsonify({"error": "会话不存在"}), 404
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 50, type=int)
        if page < 1 or not 1 <= page_size <= 100:
            return jsonify({"error": "page 不能小于 1，page_size 必须在 1 至 100 之间"}), 400
        messages, total = _service.list_messages(
            conversation_id, page=page, page_size=page_size
        )
        return jsonify(
            {
                "items": [message.to_dict() for message in messages],
                "pagination": {"total": total, "page": page, "page_size": page_size},
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/agent-conversations/<int:conversation_id>/messages", methods=["POST"])
@jwt_required()
def post_agent_conversation_message(conversation_id: int):
    """Append a user message; creates a turn and a run reusing the snapshot.

    Idempotent on client_message_id: retries return the existing message/turn/run.
    """
    try:
        conversation = _conversation_or_404(conversation_id, PROJECT_ROLES)
        if conversation is None:
            return jsonify({"error": "会话不存在"}), 404

        data = _json_object()
        content = data.get("content")
        client_message_id = data.get("client_message_id")
        mode = data.get("mode", "baseline")
        budget = data.get("budget")
        if not isinstance(content, str) or not content.strip():
            return jsonify({"error": "消息内容不能为空"}), 400
        if not isinstance(client_message_id, str) or not client_message_id.strip():
            return jsonify({"error": "缺少 client_message_id（用于防重复提交）"}), 400
        if not isinstance(mode, str):
            return jsonify({"error": "mode 必须是字符串"}), 400
        if budget is not None and not isinstance(budget, dict):
            return jsonify({"error": "budget 必须是对象"}), 400

        message, turn, run, replayed = _service.append_user_message(
            conversation,
            content=content,
            client_message_id=client_message_id.strip(),
            mode=mode,
            budget=budget or {},
        )
        return jsonify(
            {
                "message": message.to_dict(),
                "turn": turn.to_dict() if turn is not None else None,
                "run": run.to_dict() if run is not None else None,
                "replayed": replayed,
            }
        ), 201
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ConversationError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
