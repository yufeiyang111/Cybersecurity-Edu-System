"""Multi-turn conversation service: conversations, turns, idempotent messages.

A conversation owns a project security task across many turns; each user input
creates one turn and (for now) one run that reuses the conversation's current
snapshot, so follow-up questions never require re-uploading the project.
"""
from __future__ import annotations

import hashlib
import re

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.agent_runtime import AgentRun, AgentRunMode
from app.models.conversation import (
    AgentConversation,
    AgentConversationMessage,
    AgentTurn,
    ConversationStatus,
    TurnStatus,
)
from app.models.security import ProjectSnapshot
from app.services.security_agent.service import AgentRunService

CLIENT_MESSAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
MAX_MESSAGE_CHARS = 4000
DEFAULT_PAGE_SIZE = 50


class ConversationError(ValueError):
    pass


class ConversationNotFoundError(ConversationError):
    pass


class ConversationService:
    def __init__(self, run_service: AgentRunService | None = None) -> None:
        self._runs = run_service or AgentRunService()

    # ------------------------------------------------------------------ create

    def create_conversation(
        self,
        *,
        project,
        user_id: int,
        title: str = "",
    ) -> AgentConversation:
        conversation = AgentConversation(
            workspace_id=project.workspace_id,
            project_id=project.id,
            title=(title or "")[:200],
            created_by=user_id,
        )
        db.session.add(conversation)
        db.session.commit()
        return conversation

    def list_conversations(
        self,
        project_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AgentConversation], int]:
        """Return the project's conversations newest first for the workbench."""
        query = AgentConversation.query.filter_by(project_id=project_id).order_by(
            AgentConversation.updated_at.desc(), AgentConversation.id.desc()
        )
        total = query.count()
        offset = max(0, page - 1) * page_size
        rows = query.offset(offset).limit(page_size).all()
        return rows, total

    # ------------------------------------------------------------------ messages

    def append_user_message(
        self,
        conversation: AgentConversation,
        *,
        content: str,
        client_message_id: str,
        mode: str = AgentRunMode.BASELINE.value,
        budget: dict | None = None,
    ) -> tuple[AgentConversationMessage, AgentTurn, AgentRun, bool]:
        """Append one user message, then create a turn + run reusing the snapshot.

        Idempotent on client_message_id: a retry with the same id returns the
        existing message and its turn/run without duplicating execution
        (replayed=True).

        A5：若会话存在可追加方向的活跃 Run，消息走方向重规划（新计划版本），
        不创建新 Run；仅当没有活跃 Run 时才创建新 Turn + Run。
        """
        normalized = content.strip()
        if not normalized:
            raise ConversationError("消息内容不能为空")
        if len(normalized) > MAX_MESSAGE_CHARS:
            raise ConversationError(f"消息长度不能超过 {MAX_MESSAGE_CHARS} 个字符")
        if not CLIENT_MESSAGE_ID_PATTERN.match(client_message_id):
            raise ConversationError("client_message_id 必须是 8-64 位字母数字或 -_ 字符")
        if mode not in {item.value for item in AgentRunMode}:
            raise ConversationError("不支持的 Agent 运行模式")

        existing = AgentConversationMessage.query.filter_by(
            client_message_id=client_message_id
        ).one_or_none()
        if existing is not None:
            return self._replay(existing)

        active_run = self._active_replanable_run(conversation)
        if active_run is not None:
            message, plan = self.append_follow_up_direction(
                conversation,
                content=normalized,
                client_message_id=client_message_id,
                run=active_run,
            )
            turn = self._active_turn(conversation)
            return message, turn, active_run, False

        snapshot = self._resolve_snapshot(conversation)
        message = self._append_message(
            conversation,
            role="user",
            message_type="user_goal" if conversation.turn_sequence == 0 else "follow_up",
            content=normalized,
            client_message_id=client_message_id,
        )
        db.session.flush()

        turn = AgentTurn(
            conversation_id=conversation.id,
            turn_sequence=conversation.turn_sequence + 1,
            parent_turn_id=conversation.turns[-1].id if conversation.turns else None,
            status=TurnStatus.ACTIVE.value,
            input_message_id=message.id,
        )
        db.session.add(turn)
        db.session.flush()

        run = self._runs.create_run(
            project=conversation.project,
            snapshot=snapshot,
            user_id=conversation.created_by,
            goal_text=normalized,
            mode=mode,
            budget=budget or {},
        )
        turn.run_id = run.id
        message.turn_id = turn.id
        conversation.turn_sequence = turn.turn_sequence
        conversation.current_snapshot_id = snapshot.id
        if not conversation.title:
            conversation.title = normalized[:40]
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = AgentConversationMessage.query.filter_by(
                client_message_id=client_message_id
            ).one_or_none()
            if existing is not None:
                return self._replay(existing)
            raise
        return message, turn, run, False

    def append_follow_up_direction(
        self,
        conversation: AgentConversation,
        *,
        content: str,
        client_message_id: str,
        run: AgentRun,
    ) -> tuple[AgentConversationMessage, "object | None"]:
        """A5 方向追加：消息落库到活跃 Turn，并创建新计划版本（含方向节点）。

        返回 (message, new_plan)；new_plan 为 None 表示达到重规划上限。
        """
        from app.models.agent_runtime import AgentPlan
        from app.services.security_agent.event_service import EventService
        from app.services.security_agent.replanner import Replanner
        from app.services.security_agent.strategy_catalog import (
            normalize_user_direction_nodes,
        )

        normalized = content.strip()
        message = self._append_message(
            conversation,
            role="user",
            message_type="follow_up",
            content=normalized,
            client_message_id=client_message_id,
        )
        db.session.flush()
        active_turn = self._active_turn(conversation)
        if active_turn is not None:
            message.turn_id = active_turn.id

        latest_plan = (
            AgentPlan.query.filter_by(run_id=run.id)
            .order_by(AgentPlan.plan_version.desc())
            .first()
        )
        if latest_plan is None:
            raise ConversationError("任务还没有计划，无法追加方向")
        replanner = Replanner(EventService())
        new_plan = replanner.create_version(
            run,
            latest_plan,
            reason_code="user_direction_extends_plan",
            decision_type="user_direction",
            node_specs=normalize_user_direction_nodes(normalized),
            decision_summary=f"用户追加方向：{normalized[:200]}",
        )
        if new_plan is None:
            db.session.rollback()
            raise ConversationError("已达到重规划上限，无法追加新方向")
        db.session.commit()
        return message, new_plan

    def _active_replanable_run(self, conversation: AgentConversation) -> AgentRun | None:
        """最新活跃 Turn 的 Run 且处于可追加方向状态时返回，否则 None。"""
        from app.models.agent_runtime import AgentRunStatus

        turn = self._active_turn(conversation)
        if turn is None or turn.run_id is None:
            return None
        run = db.session.get(AgentRun, turn.run_id)
        if run is None:
            return None
        status = run.status.value if hasattr(run.status, "value") else str(run.status)
        if status not in {
            AgentRunStatus.QUEUED.value,
            AgentRunStatus.PREPARING.value,
            AgentRunStatus.MAPPING_REPOSITORY.value,
            AgentRunStatus.EXECUTING_TOOLS.value,
            AgentRunStatus.PAUSED.value,
        }:
            return None
        return run

    def _active_turn(self, conversation: AgentConversation) -> AgentTurn | None:
        return (
            AgentTurn.query.filter_by(conversation_id=conversation.id)
            .order_by(AgentTurn.turn_sequence.desc())
            .first()
        )

    def list_messages(
        self,
        conversation_id: int,
        *,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[AgentConversationMessage], int]:
        query = AgentConversationMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(AgentConversationMessage.message_sequence.asc())
        total = query.count()
        offset = max(0, page - 1) * page_size
        rows = query.offset(offset).limit(page_size).all()
        return rows, total

    # ------------------------------------------------------------------ helpers

    def _resolve_snapshot(self, conversation: AgentConversation) -> ProjectSnapshot:
        snapshot = None
        if conversation.current_snapshot_id:
            snapshot = db.session.get(ProjectSnapshot, conversation.current_snapshot_id)
        if snapshot is None:
            snapshot = (
                ProjectSnapshot.query.filter_by(project_id=conversation.project_id)
                .order_by(ProjectSnapshot.id.desc())
                .first()
            )
        if snapshot is None:
            raise ConversationError("项目还没有可用的快照，请先上传 ZIP 或拉取 GitHub 项目")
        return snapshot

    def _append_message(
        self,
        conversation: AgentConversation,
        *,
        role: str,
        message_type: str,
        content: str,
        client_message_id: str,
    ) -> AgentConversationMessage:
        message = AgentConversationMessage(
            conversation_id=conversation.id,
            client_message_id=client_message_id,
            message_sequence=conversation.message_sequence + 1,
            role=role,
            message_type=message_type,
            content_redacted=content,
            content_digest=_content_digest(content),
        )
        db.session.add(message)
        conversation.message_sequence = message.message_sequence
        return message

    def _replay(
        self, existing: AgentConversationMessage
    ) -> tuple[AgentConversationMessage, AgentTurn | None, AgentRun | None, bool]:
        turn = (
            AgentTurn.query.filter_by(id=existing.turn_id).first()
            if existing.turn_id
            else None
        )
        run = db.session.get(AgentRun, turn.run_id) if turn and turn.run_id else None
        return existing, turn, run, True


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_conversation_service() -> ConversationService:
    return ConversationService()
