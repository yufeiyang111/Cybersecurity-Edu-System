"""Agent state machine unit tests: transitions, optimism, terminal guards."""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_runtime import AgentRun, AgentRunMode, AgentRunStatus, PAUSABLE_RUN_STATUSES
from app.models.security import AuditEvent, Workspace, WorkspaceMember, WorkspaceMemberRole
from app.models.agent_events import AgentEvent
from app.models.user import User
from app.services.security_agent.state_machine import (
    AgentStateError,
    AgentStateMachine,
    AgentVersionConflictError,
)


@pytest.fixture
def seeded_app(app):
    with app.app_context():
        user = User(username="alice", email="alice@example.test", password_hash="x")
        db.session.add(user)
        db.session.flush()
        workspace = Workspace(name="w", slug="w-1")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role=WorkspaceMemberRole.OWNER.value,
            )
        )
        run = AgentRun(
            workspace_id=workspace.id,
            project_id=1,
            snapshot_id=1,
            created_by=user.id,
            goal_text="先清点项目文件",
            mode=AgentRunMode.BASELINE.value,
            status=AgentRunStatus.CREATED.value,
        )
        db.session.add(run)
        db.session.commit()
        yield {"user": user, "workspace": workspace, "run": run}


def test_legal_transition_writes_state_version_event_and_audit(seeded_app, app):
    with app.app_context():
        machine = AgentStateMachine()
        run = db.session.get(AgentRun, seeded_app["run"].id)
        new_version = machine.transition(
            run, AgentRunStatus.QUEUED, actor_id=seeded_app["user"].id, reason="派发"
        )
        assert new_version == 1
        assert run.state_version == 1

        event = (
            AgentEvent.query.filter_by(run_id=run.id, event_type="run.state_changed")
            .order_by(AgentEvent.sequence.desc())
            .first()
        )
        assert event is not None
        assert event.payload_json["status"] == "queued"
        assert event.state_version == 1

        audit = AuditEvent.query.filter_by(target_type="agent_run", target_id=run.id).first()
        assert audit is not None
        assert audit.action == "agent.run.queued"


def test_illegal_transition_rejected(seeded_app, app):
    with app.app_context():
        machine = AgentStateMachine()
        run = db.session.get(AgentRun, seeded_app["run"].id)
        with pytest.raises(AgentStateError):
            machine.transition(run, AgentRunStatus.COMPLETED)


def test_terminal_status_rejects_any_further_transition(seeded_app, app):
    with app.app_context():
        machine = AgentStateMachine()
        run = db.session.get(AgentRun, seeded_app["run"].id)
        with pytest.raises(AgentStateError):
            machine.transition(run, AgentRunStatus.CANCELED, actor_id=seeded_app["user"].id)
        machine.transition(
            run,
            AgentRunStatus.CANCEL_REQUESTED,
            actor_id=seeded_app["user"].id,
        )
        assert not machine.is_terminal("cancel_requested")
        machine.transition(run, AgentRunStatus.CANCELED, actor_id=seeded_app["user"].id)
        with pytest.raises(AgentStateError):
            machine.transition(run, AgentRunStatus.COMPLETED)
        assert machine.is_terminal("canceled")


def test_pause_resume_cycle_is_legal(seeded_app, app):
    with app.app_context():
        machine = AgentStateMachine()
        run = db.session.get(AgentRun, seeded_app["run"].id)
        for target in (
            AgentRunStatus.QUEUED,
            AgentRunStatus.PREPARING,
            AgentRunStatus.EXECUTING_TOOLS,
            AgentRunStatus.PAUSED,
            AgentRunStatus.EXECUTING_TOOLS,
            AgentRunStatus.COMPLETED,
        ):
            machine.transition(run, target, actor_id=seeded_app["user"].id)
        assert run.status.value == "completed"


def test_optimistic_version_conflict_does_not_overwrite(seeded_app, app):
    with app.app_context():
        machine = AgentStateMachine()
        run = db.session.get(AgentRun, seeded_app["run"].id)
        machine.transition(run, AgentRunStatus.QUEUED, actor_id=seeded_app["user"].id)

        stale = db.session.get(AgentRun, seeded_app["run"].id)
        with pytest.raises(AgentVersionConflictError):
            machine.transition(stale, AgentRunStatus.PREPARING, expected_version=0)

        fresh = db.session.get(AgentRun, seeded_app["run"].id)
        assert fresh.state_version == 1
        assert fresh.status.value == "queued"


def test_allowed_transitions_table_is_complete(app):
    statuses = {member.value for member in AgentRunStatus}
    for status in statuses:
        allowed = AgentStateMachine.allowed_transitions(status)
        assert allowed.issubset(statuses - {status}), f"{status} 指向自身或未定义状态"
    for status in statuses:
        assert status in {member.value for member in AgentRunStatus}

def test_pause_capability_matches_state_machine():
    expected = {
        status
        for status in (member.value for member in AgentRunStatus)
        if AgentRunStatus.PAUSED.value in AgentStateMachine.allowed_transitions(status)
    }

    assert PAUSABLE_RUN_STATUSES == expected