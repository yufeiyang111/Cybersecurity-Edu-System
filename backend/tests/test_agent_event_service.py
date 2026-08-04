"""AgentEvent service tests: monotonic sequences, payloads, replay listing."""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_runtime import AgentRun, AgentRunMode, AgentRunStatus
from app.models.security import Workspace, WorkspaceMember, WorkspaceMemberRole
from app.models.user import User
from app.services.security_agent.event_service import EventService


@pytest.fixture
def run_row(app):
    with app.app_context():
        user = User(username="bob", email="bob@example.test", password_hash="x")
        db.session.add(user)
        db.session.flush()
        workspace = Workspace(name="w", slug="w-2")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceMemberRole.OWNER.value)
        )
        run = AgentRun(
            workspace_id=workspace.id,
            project_id=1,
            snapshot_id=1,
            created_by=user.id,
            goal_text="g",
            mode=AgentRunMode.BASELINE.value,
            status=AgentRunStatus.CREATED.value,
        )
        db.session.add(run)
        db.session.commit()
        yield run


def test_sequences_are_monotonic_and_update_run(run_row, app):
    with app.app_context():
        service = EventService()
        run = db.session.get(AgentRun, run_row.id)
        first = service.emit(run, "run.created", {"step": 1})
        second = service.emit(run, "plan.created", {"step": 2})
        db.session.commit()
        assert second.sequence == first.sequence + 1
        assert run.last_event_sequence == second.sequence
        assert service.latest_sequence(run.id) == second.sequence


def test_list_events_replays_from_after_sequence(run_row, app):
    with app.app_context():
        service = EventService()
        run = db.session.get(AgentRun, run_row.id)
        service.emit(run, "a", {"n": 1})
        service.emit(run, "b", {"n": 2})
        service.emit(run, "c", {"n": 3})
        db.session.commit()

        replayed = service.list_events(run.id, after_sequence=1)
        assert [event.payload_json["n"] for event in replayed] == [2, 3]


def test_tail_returns_latest_in_ascending_order(run_row, app):
    with app.app_context():
        service = EventService()
        run = db.session.get(AgentRun, run_row.id)
        for index in range(5):
            service.emit(run, "e", {"n": index})
        db.session.commit()
        tail = service.tail(run.id, limit=3)
        assert [event.payload_json["n"] for event in tail] == [2, 3, 4]
