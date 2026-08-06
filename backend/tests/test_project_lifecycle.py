# -*- coding: utf-8 -*-
"""项目/任务/快照/修复建议/知识源 的 CRUD 补全测试。"""
from __future__ import annotations

import io
import sys
import types
import zipfile

import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import (
    AgentArtifact,
    AgentCheckpoint,
    AgentMessage,
    AgentPlan,
    AgentPlanEdge,
    AgentPlanNode,
    AgentRun,
    AgentStepExecution,
    AgentToolCall,
)
from app.models.conversation import AgentConversation, AgentConversationMessage, AgentTurn
from app.models.security import (
    AuditEvent,
    ProjectSnapshot,
    ScanTask,
    SecurityKnowledgeDocument,
    SecurityKnowledgeSource,
    SecurityProject,
    Workspace,
    WorkspaceMember,
)
from app.models.user import User


def _install_legacy_route_stubs(monkeypatch):
    import app.routes

    for module_name, blueprint_name in {
        "app.routes.auth": "auth_bp",
        "app.routes.knowledge": "knowledge_bp",
        "app.routes.qa": "qa_bp",
        "app.routes.admin": "admin_bp",
    }.items():
        module = types.ModuleType(module_name)
        setattr(module, blueprint_name, Blueprint(blueprint_name, module_name))
        monkeypatch.setitem(sys.modules, module_name, module)


@pytest.fixture
def api_app(tmp_path, monkeypatch):
    from conftest import TestConfig

    _install_legacy_route_stubs(monkeypatch)
    config = type(
        "LifecycleApiTestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "RQ_ASYNC": False,
        },
    )
    application = create_app(config)

    with application.app_context():
        from sqlalchemy import event

        @event.listens_for(db.engine, "connect")
        def _enable_fk(dbapi_conn, connection_record):
            dbapi_conn.execute("PRAGMA foreign_keys = ON")

        import app.models  # noqa: F401

        db.create_all()
        yield application
        db.session.remove()


def _user_id(application, username: str) -> int:
    with application.app_context():
        from app.models.user import Role

        if db.session.query(Role).filter_by(id=3).first() is None:
            db.session.add(Role(id=3, name="user", description="普通用户"))
            db.session.flush()
        user = User(username=username, email=f"{username}@example.test", password_hash="x", role_id=3)
        db.session.add(user)
        db.session.commit()
        return user.id


def _headers(application, user_id: int) -> dict[str, str]:
    with application.app_context():
        token = create_access_token(identity=str(user_id), additional_claims={"role": "user"})
    return {"Authorization": f"Bearer {token}"}


def _zip_payload(contents: dict[str, str]) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in contents.items():
            archive.writestr(name, content)
    buffer.seek(0)
    return buffer


def _create_project(client, headers: dict[str, str], name: str = "demo") -> dict:
    response = client.post("/api/security/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json["project"]


def _upload_project(client, headers: dict[str, str], project_id: int, contents: dict[str, str]) -> dict:
    response = client.post(
        f"/api/security/projects/{project_id}/snapshots:upload",
        data={"archive": (_zip_payload(contents), "project.zip")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert response.status_code == 202
    return response.json


def _add_agent_run(application, workspace_id: int, project_id: int, snapshot_id: int) -> int:
    with application.app_context():
        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            goal_text="audit",
        )
        db.session.add(run)
        db.session.commit()
        return run.id


def _add_agent_conversation_chain(application, workspace_id: int, project_id: int) -> None:
    """Create conversation -> turn <-> message circular rows like the workbench does."""
    with application.app_context():
        conversation = AgentConversation(
            workspace_id=workspace_id,
            project_id=project_id,
            title="delete-me",
        )
        db.session.add(conversation)
        db.session.flush()
        turn = AgentTurn(conversation_id=conversation.id, turn_sequence=1)
        db.session.add(turn)
        db.session.flush()
        message = AgentConversationMessage(
            conversation_id=conversation.id,
            turn_id=turn.id,
            client_message_id="delete-me-msg-1",
            message_sequence=1,
            role="user",
            message_type="user_goal",
            content_redacted="redacted",
            content_digest="sha256-redacted",
        )
        db.session.add(message)
        db.session.flush()
        turn.input_message_id = message.id
        db.session.commit()


def _add_agent_run_subtree(application, workspace_id: int, project_id: int, snapshot_id: int) -> int:
    """Create an AgentRun with every referencing child table populated."""
    with application.app_context():
        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            goal_text="audit",
        )
        db.session.add(run)
        db.session.flush()
        db.session.add(AgentEvent(run_id=run.id, sequence=1, event_type="run.created"))
        db.session.add(AgentMessage(run_id=run.id, role="user", content="audit"))
        plan = AgentPlan(run_id=run.id, plan_version=1, planner_source="rule")
        db.session.add(plan)
        db.session.flush()
        node = AgentPlanNode(
            plan_id=plan.id,
            node_key="n1",
            node_type="baseline_scan",
            title="baseline",
        )
        db.session.add(node)
        db.session.flush()
        db.session.add(
            AgentPlanEdge(plan_id=plan.id, from_node="n1", to_node="n1", edge_type="success")
        )
        step = AgentStepExecution(plan_node_id=node.id, run_id=run.id, attempt_number=1)
        db.session.add(step)
        db.session.flush()
        db.session.add(
            AgentToolCall(
                run_id=run.id,
                plan_node_id=node.id,
                step_execution_id=step.id,
                tool_name="scanner",
                idempotency_key="delete-me-idem-1",
            )
        )
        db.session.add(
            AgentArtifact(
                run_id=run.id,
                plan_node_id=node.id,
                step_execution_id=step.id,
                artifact_type="report",
                summary="summary",
            )
        )
        db.session.add(
            AgentCheckpoint(run_id=run.id, plan_version=1, state_json={}, event_sequence=0)
        )
        db.session.commit()
        return run.id


def _add_knowledge(application, workspace_id: int) -> tuple[int, int]:
    with application.app_context():
        source = SecurityKnowledgeSource(
            workspace_id=workspace_id,
            name="OWASP ASVS",
            source_type="standard",
            source_version="5.0",
        )
        db.session.add(source)
        db.session.flush()
        document = SecurityKnowledgeDocument(
            source_id=source.id,
            document_version="5.0-v5.3",
            title="Command injection prevention",
            content="Use parameterized process invocation.",
            tags_json=["owasp"],
        )
        db.session.add(document)
        db.session.commit()
        return source.id, document.id


class TestProjectUpdate:
    def test_rename_project_and_update_description(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers, "old-name")

        response = client.put(
            f"/api/security/projects/{project['id']}",
            json={"name": "new-name", "description": "重命名后的描述", "default_branch": "main"},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json["project"]["name"] == "new-name"
        assert response.json["project"]["description"] == "重命名后的描述"
        assert response.json["project"]["default_branch"] == "main"
        with api_app.app_context():
            assert AuditEvent.query.filter_by(action="project.updated").count() == 1

    def test_rename_project_rejects_duplicate_name(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        _create_project(client, headers, "first")
        second = _create_project(client, headers, "second")

        response = client.put(
            f"/api/security/projects/{second['id']}",
            json={"name": "first"},
            headers=headers,
        )

        assert response.status_code == 409
        assert response.json == {"error": "项目名称已存在"}

    def test_update_project_rejects_empty_body_and_bad_name(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers)

        empty = client.put(f"/api/security/projects/{project['id']}", json={}, headers=headers)
        assert empty.status_code == 400
        blank = client.put(
            f"/api/security/projects/{project['id']}",
            json={"name": "   "},
            headers=headers,
        )
        assert blank.status_code == 400

    def test_update_project_denies_other_workspace(self, api_app):
        owner = _user_id(api_app, "owner")
        intruder = _user_id(api_app, "intruder")
        with api_app.app_context():
            workspace = Workspace(name="Private", slug="private")
            db.session.add(workspace)
            db.session.flush()
            db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner, role="owner"))
            project = SecurityProject(workspace_id=workspace.id, name="private", created_by=owner)
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        response = api_app.test_client().put(
            f"/api/security/projects/{project_id}",
            json={"name": "hijacked"},
            headers=_headers(api_app, intruder),
        )

        assert response.status_code == 403


class TestProjectDelete:
    def test_delete_project_removes_snapshot_files_and_rows(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers, "delete-me")
        upload = _upload_project(client, headers, project["id"], {"app.py": "print('x')\n"})
        snapshot_id = upload["snapshot"]["id"]
        task_id = upload["task"]["id"]

        with api_app.app_context():
            snapshot = db.session.get(ProjectSnapshot, snapshot_id)
            storage_path = snapshot.storage_path

        response = client.delete(f"/api/security/projects/{project['id']}", headers=headers)

        assert response.status_code == 200
        assert response.json == {"deleted": True}
        with api_app.app_context():
            assert db.session.get(SecurityProject, project["id"]) is None
            assert db.session.get(ProjectSnapshot, snapshot_id) is None
            assert db.session.get(ScanTask, task_id) is None
        import os
        assert not os.path.exists(storage_path)

    def test_delete_project_cascades_agent_run(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers, "busy")
        upload = _upload_project(client, headers, project["id"], {"app.py": "print('x')\n"})
        run_id = _add_agent_run(api_app, project["workspace_id"], project["id"], upload["snapshot"]["id"])

        response = client.delete(f"/api/security/projects/{project['id']}", headers=headers)

        assert response.status_code == 200
        assert response.json == {"deleted": True}
        with api_app.app_context():
            assert db.session.get(SecurityProject, project["id"]) is None
            assert db.session.get(AgentRun, run_id) is None

    def test_delete_project_cleans_conversation_turn_message_cycle(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers, "conv-cycle")
        upload = _upload_project(client, headers, project["id"], {"app.py": "print('x')\n"})
        _add_agent_conversation_chain(api_app, project["workspace_id"], project["id"])

        response = client.delete(f"/api/security/projects/{project['id']}", headers=headers)

        assert response.status_code == 200
        with api_app.app_context():
            assert AgentConversation.query.filter_by(project_id=project["id"]).count() == 0
            assert AgentTurn.query.count() == 0
            assert AgentConversationMessage.query.count() == 0

    def test_delete_project_cleans_agent_run_full_subtree(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers, "run-subtree")
        upload = _upload_project(client, headers, project["id"], {"app.py": "print('x')\n"})
        run_id = _add_agent_run_subtree(
            api_app, project["workspace_id"], project["id"], upload["snapshot"]["id"]
        )

        response = client.delete(f"/api/security/projects/{project['id']}", headers=headers)

        assert response.status_code == 200
        assert response.json == {"deleted": True}
        with api_app.app_context():
            assert db.session.get(AgentRun, run_id) is None
            assert AgentEvent.query.count() == 0
            assert AgentMessage.query.count() == 0
            assert AgentPlan.query.count() == 0
            assert AgentPlanNode.query.count() == 0
            assert AgentPlanEdge.query.count() == 0
            assert AgentStepExecution.query.count() == 0
            assert AgentToolCall.query.count() == 0
            assert AgentArtifact.query.count() == 0
            assert AgentCheckpoint.query.count() == 0


class TestTaskDelete:
    def test_delete_completed_task_cascades_findings(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers)
        upload = _upload_project(client, headers, project["id"], {"danger.py": "import subprocess\nsubprocess.run(cmd, shell=True)\n"})
        task_id = upload["task"]["id"]
        findings = client.get(f"/api/security/tasks/{task_id}/findings", headers=headers)
        assert findings.json["items"]

        response = client.delete(f"/api/security/tasks/{task_id}", headers=headers)

        assert response.status_code == 200
        with api_app.app_context():
            assert db.session.get(ScanTask, task_id) is None
            assert AuditEvent.query.filter_by(action="scan_task.deleted").count() == 1

    def test_delete_running_task_rejected(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers)
        upload = _upload_project(client, headers, project["id"], {"app.py": "print('x')\n"})
        task_id = upload["task"]["id"]
        with api_app.app_context():
            task = db.session.get(ScanTask, task_id)
            task.status = "created"
            db.session.commit()

        response = client.delete(f"/api/security/tasks/{task_id}", headers=headers)

        assert response.status_code == 409
        assert "已结束" in response.json["error"]


class TestSnapshotCrud:
    def test_list_and_delete_snapshot(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers)
        upload = _upload_project(client, headers, project["id"], {"app.py": "print('x')\n"})
        snapshot_id = upload["snapshot"]["id"]

        listed = client.get(f"/api/security/projects/{project['id']}/snapshots", headers=headers)
        assert listed.status_code == 200
        assert listed.json["pagination"]["total"] == 1
        assert listed.json["items"][0]["task_count"] == 1

        deleted = client.delete(
            f"/api/security/projects/{project['id']}/snapshots/{snapshot_id}",
            headers=headers,
        )
        assert deleted.status_code == 200
        with api_app.app_context():
            assert db.session.get(ProjectSnapshot, snapshot_id) is None
            assert AuditEvent.query.filter_by(action="snapshot.deleted").count() == 1

    def test_delete_snapshot_cascades_agent_run(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers)
        upload = _upload_project(client, headers, project["id"], {"app.py": "print('x')\n"})
        snapshot_id = upload["snapshot"]["id"]
        run_id = _add_agent_run(api_app, project["workspace_id"], project["id"], snapshot_id)

        response = client.delete(
            f"/api/security/projects/{project['id']}/snapshots/{snapshot_id}",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json == {"deleted": True}
        with api_app.app_context():
            assert db.session.get(ProjectSnapshot, snapshot_id) is None
            assert db.session.get(AgentRun, run_id) is None
            assert db.session.get(SecurityProject, project["id"]) is not None


class TestSuggestionDelete:
    def test_delete_remediation_suggestion(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        project = _create_project(client, headers)
        upload = _upload_project(client, headers, project["id"], {"app.py": "app.run(debug=True)\n"})
        task_id = upload["task"]["id"]
        findings = client.get(f"/api/security/tasks/{task_id}/findings", headers=headers)
        finding = next(item for item in findings.json["items"] if item["rule_id"] == "PY-FLASK-DEBUG")

        generated = client.post(
            f"/api/security/findings/{finding['id']}/suggestions",
            headers=headers,
        )
        suggestion_id = generated.json["suggestion"]["id"]

        response = client.delete(f"/api/security/suggestions/{suggestion_id}", headers=headers)

        assert response.status_code == 200
        assert response.json == {"deleted": True}
        with api_app.app_context():
            assert AuditEvent.query.filter_by(action="remediation.deleted").count() == 1

    def test_delete_missing_suggestion_returns_404(self, api_app):
        owner = _user_id(api_app, "owner")
        response = api_app.test_client().delete(
            "/api/security/suggestions/999999",
            headers=_headers(api_app, owner),
        )
        assert response.status_code == 404


class TestKnowledgeCrud:
    def test_update_and_delete_knowledge_source(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        workspace = _personal_workspace(api_app, owner)
        source_id, document_id = _add_knowledge(api_app, workspace)

        updated = client.put(
            f"/api/security/knowledge/sources/{source_id}",
            json={"name": "OWASP ASVS 2025", "source_version": "5.1", "is_active": False},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json["source"]["name"] == "OWASP ASVS 2025"
        assert updated.json["source"]["is_active"] is False

        updated_document = client.put(
            f"/api/security/knowledge/sources/{source_id}/documents/{document_id}",
            json={"title": "Command injection prevention (revised)", "tags": ["owasp", "updated"]},
            headers=headers,
        )
        assert updated_document.status_code == 200
        assert updated_document.json["document"]["title"] == "Command injection prevention (revised)"
        assert updated_document.json["document"]["tags"] == ["owasp", "updated"]

        with api_app.app_context():
            assert AuditEvent.query.filter_by(action="knowledge.source_updated").count() == 1
            assert AuditEvent.query.filter_by(action="knowledge.document_updated").count() == 1

        deleted_document = client.delete(
            f"/api/security/knowledge/sources/{source_id}/documents/{document_id}",
            headers=headers,
        )
        assert deleted_document.status_code == 200
        with api_app.app_context():
            assert db.session.get(SecurityKnowledgeDocument, document_id) is None

        deleted_source = client.delete(f"/api/security/knowledge/sources/{source_id}", headers=headers)
        assert deleted_source.status_code == 200
        with api_app.app_context():
            assert db.session.get(SecurityKnowledgeSource, source_id) is None
            assert AuditEvent.query.filter_by(action="knowledge.document_deleted").count() == 1
            assert AuditEvent.query.filter_by(action="knowledge.source_deleted").count() == 1

    def test_update_document_rejects_version_conflict(self, api_app):
        owner = _user_id(api_app, "owner")
        client = api_app.test_client()
        headers = _headers(api_app, owner)
        workspace = _personal_workspace(api_app, owner)
        source_id, document_id = _add_knowledge(api_app, workspace)
        with api_app.app_context():
            duplicate = SecurityKnowledgeDocument(
                source_id=source_id,
                document_version="9.9",
                title="other",
                content="other content",
            )
            db.session.add(duplicate)
            db.session.commit()
            duplicate_id = duplicate.id

        response = client.put(
            f"/api/security/knowledge/sources/{source_id}/documents/{duplicate_id}",
            json={"document_version": "5.0-v5.3"},
            headers=headers,
        )

        assert response.status_code == 409
        assert response.json == {"error": "知识文档版本已存在"}

    def test_knowledge_delete_denied_for_other_workspace(self, api_app):
        owner = _user_id(api_app, "owner")
        intruder = _user_id(api_app, "intruder")
        with api_app.app_context():
            workspace = Workspace(name="Private Knowledge", slug="private-knowledge")
            db.session.add(workspace)
            db.session.flush()
            db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner, role="owner"))
            source = SecurityKnowledgeSource(
                workspace_id=workspace.id,
                name="Private",
                source_type="internal",
                source_version="1",
            )
            db.session.add(source)
            db.session.commit()
            source_id = source.id

        response = api_app.test_client().delete(
            f"/api/security/knowledge/sources/{source_id}",
            headers=_headers(api_app, intruder),
        )

        assert response.status_code == 403


def _personal_workspace(application, user_id: int) -> int:
    from app.services.workspaces import get_or_create_personal_workspace

    with application.app_context():
        return get_or_create_personal_workspace(user_id).id
