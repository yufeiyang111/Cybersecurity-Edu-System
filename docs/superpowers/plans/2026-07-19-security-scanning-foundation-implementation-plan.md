# CyberGuard Security Scanning Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a verified first vertical slice: an authenticated user uploads a safe ZIP project, CyberGuard creates an isolated snapshot, runs deterministic Python static checks, and presents a persisted task with evidence-backed findings.

**Architecture:** Keep Flask + SQLAlchemy + Vue as a modular monolith. Add a workspace-scoped security domain, safe archive intake, scanner plugin contracts, and an RQ dispatch boundary. Scanners only read validated text files; they never execute uploaded code. Existing ChromaDB/RAG remains unchanged in this phase.

**Tech Stack:** Python 3.10+, Flask 3, Flask-SQLAlchemy, MySQL 8, Redis + RQ, pytest, Vue 3, Vite 5, Pinia, Element Plus, Vitest 1, Axios.

## Global Constraints

- Never execute, install, import, build, test, or run any uploaded project code.
- ZIP intake rejects traversal, absolute paths, symlinks, non-regular files, file-count overflow, compressed-size overflow, and extracted-size overflow before scanning.
- This plan supports ZIP input only; public GitHub import is a subsequent plan.
- Every new resource query authorizes with `workspace_id`.
- Never store, log, render, or prompt with a complete secret; retain only a SHA-256 digest and masked preview.
- Retain ChromaDB; do not replace the existing vector backend in this phase.
- Apply additive schema changes in both `database/init.sql` and `database/migrations/001_security_scanning_foundation.sql`.
- Do not read, print, copy, modify, or commit `backend/.env`; manually author `backend/.env.example` with placeholders.
- Do not initialize Git, commit, push, reset, or rewrite history without a later explicit user request.
- Do not run installation commands until dependency installation is explicitly approved.

---

## File Structure

- Create `backend/app/models/security.py`: workspace, project, snapshot, task, finding, evidence, and audit models.
- Create `backend/app/services/workspaces.py`: default-workspace bootstrap and membership authorization.
- Create `backend/app/services/source_intake.py`: safe ZIP validation, extraction, and snapshot manifests.
- Create `backend/app/services/scanners/base.py`, `backend/app/services/scanners/__init__.py`, and `backend/app/services/scanners/python_scanner.py`: scanner contract and Python baseline rules.
- Create `backend/app/services/scan_orchestrator.py` and `backend/app/services/task_dispatcher.py`: state transitions and RQ/inline dispatch.
- Create `backend/app/routes/projects.py`: project, upload, task, and finding APIs.
- Create `database/migrations/001_security_scanning_foundation.sql`: idempotent additive migration.
- Create backend tests under `backend/tests/` and frontend tests under `frontend/src/views/security/__tests__/`.
- Create `frontend/src/views/security/Projects.vue`, `frontend/src/views/security/ProjectDetail.vue`, and status/severity components.
- Modify `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/models/__init__.py`, `backend/app/models/user.py`, `backend/run.py`, `backend/requirements.txt`, `database/init.sql`, `frontend/src/api/index.js`, `frontend/src/router/index.js`, `frontend/src/views/Home.vue`, `frontend/package.json`, and `README.md`.
- Create `.gitignore`, `.github/workflows/ci.yml`, `backend/.env.example`, `backend/pytest.ini`, `frontend/vitest.config.js`, and `frontend/src/test/setup.js`.

## Task 1: Establish a testable secure application baseline

**Files:**
- Create: `backend/tests/conftest.py`, `backend/tests/test_config_security.py`, `backend/pytest.ini`, `backend/.env.example`
- Modify: `backend/app/config.py`, `backend/app/__init__.py`, `backend/requirements.txt`, `backend/run.py`

**Interfaces:** Produces `create_app(config_object: type | None = None) -> Flask` and `Config.validate_security_settings() -> None`.

- [ ] **Step 1: Write failing configuration tests.**

```python
# backend/tests/test_config_security.py
import pytest
from app import create_app
from app.config import Config


def test_testing_config_uses_explicit_allowed_origin(app):
    assert app.config["CORS_ALLOWED_ORIGINS"] == ["http://testserver"]


def test_production_rejects_default_signing_keys(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Config.validate_security_settings()
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `python -m pytest backend/tests/test_config_security.py -q`

Expected: FAIL because the app fixture and `validate_security_settings` are absent.

- [ ] **Step 3: Add isolated test config and secure runtime defaults.**

```python
# backend/tests/conftest.py
import pytest
from app import create_app, db


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test-secret-key"
    JWT_SECRET_KEY = "test-jwt-secret-key"
    CORS_ALLOWED_ORIGINS = ["http://testserver"]
    SECURITY_WORKSPACE_ROOT = "tests/.security-workspaces"
    RQ_QUEUE_NAME = "security-scans"
    RQ_ASYNC = False


@pytest.fixture()
def app(tmp_path, monkeypatch):
    TestConfig.SECURITY_WORKSPACE_ROOT = str(tmp_path / "security-workspaces")
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
```

Implement `APP_ENV`, `CORS_ALLOWED_ORIGINS`, archive limits, `REDIS_URL`, `RQ_QUEUE_NAME`, `RQ_ASYNC`, `SECURITY_WORKSPACE_ROOT`, and `validate_security_settings()` in `Config`. In production, raise if either signing key is absent or equals the old placeholder values. Change `create_app` to accept an optional config object, call validation, use the explicit CORS origin list, and create only configured data roots. Change `run.py` so its `debug` value is `app.config["DEBUG"]`.

- [ ] **Step 4: Add exact dependency declarations and non-secret environment template.**

Append to `backend/requirements.txt`:

```text
redis==5.0.8
rq==1.16.2
pytest==8.3.2
fakeredis==2.23.2
```

Write `backend/.env.example` with only placeholders: `APP_ENV=development`, `SECRET_KEY=replace-with-a-long-random-value`, `JWT_SECRET_KEY=replace-with-a-different-long-random-value`, `CORS_ALLOWED_ORIGINS=http://localhost:5173`, `REDIS_URL=redis://localhost:6379/0`, and the archive limit variables.

- [ ] **Step 5: Run focused tests.**

Run: `python -m pytest backend/tests/test_config_security.py -q`

Expected: PASS with two tests. If a dependency is absent locally, stop before installing it and report the exact install command for approval.

## Task 2: Add additive workspace and scan persistence models

**Files:**
- Create: `backend/app/models/security.py`, `database/migrations/001_security_scanning_foundation.sql`, `backend/tests/test_security_models.py`
- Modify: `backend/app/models/user.py`, `backend/app/models/__init__.py`, `database/init.sql`

**Interfaces:** Produces `Workspace`, `WorkspaceMember`, `SecurityProject`, `ProjectSnapshot`, `ScanTask`, `SecurityFinding`, `FindingEvidence`, and `AuditEvent`.

- [ ] **Step 1: Write failing model tests.**

```python
# backend/tests/test_security_models.py
import pytest
from sqlalchemy.exc import IntegrityError
from app import db
from app.models.security import SecurityFinding, ScanTask, ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User


def make_task():
    user = User(username="alice", email="alice@example.test", password_hash="x")
    workspace = Workspace(name="Alice", slug="alice")
    db.session.add_all([user, workspace])
    db.session.flush()
    db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    project = SecurityProject(workspace_id=workspace.id, name="demo", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    snapshot = ProjectSnapshot(project_id=project.id, source_type="zip", content_sha256="a" * 64, file_count=1, total_bytes=1)
    db.session.add(snapshot)
    db.session.flush()
    task = ScanTask(snapshot_id=snapshot.id, status="created", progress=0)
    db.session.add(task)
    db.session.flush()
    return workspace, user, task


def test_workspace_membership_is_unique(app):
    with app.app_context():
        workspace, user, _ = make_task()
        db.session.commit()
        assert workspace.members[0].role == "owner"
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="viewer"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_finding_fingerprint_is_unique_per_task(app):
    with app.app_context():
        _, _, task = make_task()
        db.session.add(SecurityFinding(task_id=task.id, fingerprint="same", rule_id="PY-SHELL-TRUE", category="sast", severity="high", file_path="a.py", start_line=1, message="x"))
        db.session.commit()
        db.session.add(SecurityFinding(task_id=task.id, fingerprint="same", rule_id="PY-SHELL-TRUE", category="sast", severity="high", file_path="a.py", start_line=1, message="x"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `python -m pytest backend/tests/test_security_models.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.security'`.

- [ ] **Step 3: Implement normalized models and additive SQL.**

Define `ScanTaskStatus` values `created`, `validating`, `snapshotting`, `scanning`, `completed`, `completed_with_warnings`, `failed`, and `canceled`. Define severity values `critical`, `high`, `medium`, `low`, and `info`. Add unique constraints named `uq_workspaces_slug`, `uq_workspace_membership`, and `uq_task_finding_fingerprint`. Every mutable model has `created_at` and `updated_at`; `SecurityFinding.to_dict()` excludes raw secret values.

Write the same new table definitions and indexes in both SQL files. Move the existing legacy default-user insert block in `database/init.sql` to after the legacy `users` table creation so a fresh MySQL initialization succeeds. Add `User.workspace_memberships` and export all new models from `backend/app/models/__init__.py`.

- [ ] **Step 4: Run model tests.**

Run: `python -m pytest backend/tests/test_config_security.py backend/tests/test_security_models.py -q`

Expected: PASS.

## Task 3: Implement workspace bootstrap and authorization service

**Files:**
- Create: `backend/app/services/workspaces.py`, `backend/tests/test_workspaces.py`

**Interfaces:** Consumes `Workspace`, `WorkspaceMember`, `User`, and SQLAlchemy session. Produces `AuthorizationError`, `get_or_create_personal_workspace(user_id: int) -> Workspace`, `get_workspace_member(workspace_id: int, user_id: int) -> WorkspaceMember | None`, and `require_workspace_role(workspace_id: int, user_id: int, allowed_roles: set[str]) -> WorkspaceMember`.

- [ ] **Step 1: Write failing authorization tests.**

```python
# backend/tests/test_workspaces.py
import pytest
from app import db
from app.models.user import User
from app.services.workspaces import AuthorizationError, get_or_create_personal_workspace, require_workspace_role


def test_legacy_user_gets_one_personal_owner_workspace(app):
    with app.app_context():
        user = User(username="alice", email="alice@example.test", password_hash="x")
        db.session.add(user)
        db.session.commit()
        first = get_or_create_personal_workspace(user.id)
        second = get_or_create_personal_workspace(user.id)
        assert first.id == second.id
        assert first.members[0].role == "owner"


def test_member_cannot_access_unrelated_workspace(app):
    with app.app_context(), pytest.raises(AuthorizationError):
        require_workspace_role(999, 1, {"owner", "analyst"})
```

Add a third test asserting that a user with only `viewer` membership cannot satisfy `{"analyst", "security_admin"}` and gets the exact message `无权访问该工作区`.

- [ ] **Step 2: Run tests to verify the service is missing.**

Run: `python -m pytest backend/tests/test_workspaces.py -q`

Expected: FAIL with import error.

- [ ] **Step 3: Implement deterministic default workspace behavior.**

Use a slug of `personal-{user_id}`. `get_or_create_personal_workspace` must query by slug, create `Workspace(name=f"{user.username} 的安全工作区", slug=slug)`, add an `owner` membership, and commit once. `require_workspace_role` must raise `AuthorizationError("无权访问该工作区")` when no membership exists or the role is insufficient, so callers do not learn whether a workspace exists.

- [ ] **Step 4: Run workspace tests.**

Run: `python -m pytest backend/tests/test_workspaces.py -q`

Expected: PASS.

## Task 4: Build safe ZIP intake and immutable snapshot manifests

**Files:**
- Create: `backend/app/services/source_intake.py`, `backend/tests/test_source_intake.py`

**Interfaces:** Consumes `pathlib.Path`, `zipfile.ZipFile`, and archive limits from config. Produces `ArchiveValidationError`, `ArchiveSafetyPolicy`, `SnapshotManifest`, and `validate_and_extract_zip(archive_path: Path, destination: Path, policy: ArchiveSafetyPolicy) -> SnapshotManifest`.

- [ ] **Step 1: Write ZIP attack-regression tests.**

```python
# backend/tests/test_source_intake.py
import zipfile
import pytest
from app.services.source_intake import ArchiveSafetyPolicy, ArchiveValidationError, validate_and_extract_zip


def write_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for member_name, content in members.items():
            archive.writestr(member_name, content)


def test_rejects_path_traversal(tmp_path):
    archive = tmp_path / "escape.zip"
    write_zip(archive, {"../escaped.py": "print('unsafe')"})
    with pytest.raises(ArchiveValidationError, match="路径穿越"):
        validate_and_extract_zip(archive, tmp_path / "out", ArchiveSafetyPolicy())


def test_extracts_text_project_and_returns_sha256(tmp_path):
    archive = tmp_path / "safe.zip"
    write_zip(archive, {"app.py": "print('safe')", "requirements.txt": "Flask==3.0.0\n"})
    manifest = validate_and_extract_zip(archive, tmp_path / "out", ArchiveSafetyPolicy())
    assert manifest.file_count == 2
    assert manifest.content_sha256
    assert (tmp_path / "out" / "app.py").is_file()
```

Add cases for an absolute path, a symlink `ZipInfo` entry, more files than `max_file_count`, and extracted bytes above `max_extracted_bytes`.

- [ ] **Step 2: Run tests to verify the service is missing.**

Run: `python -m pytest backend/tests/test_source_intake.py -q`

Expected: FAIL with import error.

- [ ] **Step 3: Implement validated extraction.**

Reject entries when `PurePosixPath(info.filename).is_absolute()`, any path part equals `".."`, the ZIP metadata indicates a symlink, the normalized destination escapes the extraction root, or configured limits are exceeded. Stream extraction in chunks, track uncompressed bytes, and compute a deterministic project content SHA-256 from sorted `(relative_path, file_sha256)` pairs. Extract only UTF-8-decodable source/config/manifest files under an allowlist; record skipped binary files in the manifest.

- [ ] **Step 4: Run regression tests.**

Run: `python -m pytest backend/tests/test_source_intake.py -q`

Expected: PASS with all malicious-archive cases rejected.

## Task 5: Implement scanner plug-in contracts and deterministic Python baseline rules

**Files:**
- Create: `backend/app/services/scanners/base.py`, `backend/app/services/scanners/__init__.py`, `backend/app/services/scanners/python_scanner.py`, `backend/tests/test_python_scanner.py`

**Interfaces:** Consumes `SnapshotManifest` and the extracted snapshot root. Produces `ProjectProfile`, `RawFinding`, `BaseLanguageScanner`, `PythonScanner`, and `get_scanners() -> list[BaseLanguageScanner]`.

- [ ] **Step 1: Write failing scanner tests.**

```python
# backend/tests/test_python_scanner.py
from app.services.scanners.python_scanner import PythonScanner


def test_detects_python_project_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    profile = PythonScanner().detect_project(tmp_path)
    assert profile.language == "python"
    assert profile.manifest_paths == ["pyproject.toml"]


def test_reports_shell_true_as_cwe_78(tmp_path):
    (tmp_path / "danger.py").write_text("import subprocess\nsubprocess.run(cmd, shell=True)\n", encoding="utf-8")
    findings = PythonScanner().run_sast(tmp_path)
    assert [(f.rule_id, f.cwe_id, f.start_line) for f in findings] == [("PY-SHELL-TRUE", "CWE-78", 2)]


def test_secret_evidence_is_masked_and_hashed(tmp_path):
    (tmp_path / "settings.py").write_text("API_KEY = 'sk_live_1234567890abcdef'\n", encoding="utf-8")
    finding = PythonScanner().run_secret_scan(tmp_path)[0]
    assert "1234567890abcdef" not in finding.evidence_preview
    assert len(finding.secret_sha256) == 64
```

- [ ] **Step 2: Run tests to verify contracts are absent.**

Run: `python -m pytest backend/tests/test_python_scanner.py -q`

Expected: FAIL with import error.

- [ ] **Step 3: Implement stable DTOs and rules.**

Use dataclasses in `base.py`:

```python
@dataclass(frozen=True)
class RawFinding:
    rule_id: str
    category: str
    severity: str
    cwe_id: str | None
    file_path: str
    start_line: int
    end_line: int
    message: str
    evidence_preview: str
    secret_sha256: str | None = None

@dataclass(frozen=True)
class ProjectProfile:
    language: str
    framework_hints: list[str]
    manifest_paths: list[str]
```

Implement only deterministic Python rules: `PY-SHELL-TRUE` (CWE-78, high), `PY-YAML-UNSAFE-LOAD` (CWE-502, high), `PY-FLASK-DEBUG` (CWE-489, medium), and a generic secret rule that masks the detected value as first four characters + `***` + last four characters. Build the final scan fingerprint in orchestration from `rule_id`, `file_path`, `start_line`, and a raw-evidence digest; never persist full secret text.

- [ ] **Step 4: Run scanner tests.**

Run: `python -m pytest backend/tests/test_python_scanner.py -q`

Expected: PASS.

## Task 6: Orchestrate scan state, persistence, and RQ dispatch boundaries

**Files:**
- Create: `backend/app/services/scan_orchestrator.py`, `backend/app/services/task_dispatcher.py`, `backend/tests/test_scan_orchestrator.py`
- Modify: `backend/app/models/security.py`, `backend/run.py`

**Interfaces:** Consumes `ScanTask`, `ProjectSnapshot`, `get_scanners()`, and `db`. Produces `run_scan_task(task_id: int) -> ScanTask`, `cancel_scan_task(task: ScanTask) -> None`, and `ScanTaskDispatcher.enqueue(task_id: int) -> str`.

- [ ] **Step 1: Write state-transition tests.**

```python
# backend/tests/test_scan_orchestrator.py
from app.models.security import ScanTaskStatus
from app.services.scan_orchestrator import run_scan_task


def test_scan_task_persists_findings_and_completes(app, scan_task_with_python_snapshot):
    with app.app_context():
        task = run_scan_task(scan_task_with_python_snapshot.id)
        assert task.status == ScanTaskStatus.COMPLETED.value
        assert task.findings[0].rule_id == "PY-SHELL-TRUE"
        assert task.findings[0].evidences[0].content_redacted


def test_scanner_failure_preserves_completed_findings_as_warning(app, scan_task_with_one_failing_scanner):
    with app.app_context():
        task = run_scan_task(scan_task_with_one_failing_scanner.id)
        assert task.status == ScanTaskStatus.COMPLETED_WITH_WARNINGS.value
```

- [ ] **Step 2: Run tests to establish missing orchestration.**

Run: `python -m pytest backend/tests/test_scan_orchestrator.py -q`

Expected: FAIL with import error.

- [ ] **Step 3: Implement explicit legal transitions and normalized persistence.**

Define `ALLOWED_TRANSITIONS` so a task moves only through `created → validating → snapshotting → scanning → completed|completed_with_warnings|failed`, while cancellation is allowed only before terminal states. `run_scan_task` loads the task, checks cancellation before each scanner, invokes matching scanners, computes `fingerprint = sha256(f"{rule_id}:{file_path}:{start_line}:{sha256(evidence)}")`, upserts `SecurityFinding`, writes `FindingEvidence`, and records `AuditEvent`. A scanner exception adds a structured warning; if at least one scanner completed, end in `completed_with_warnings`, otherwise `failed`.

Create `InlineScanTaskDispatcher` for tests and `RQScanTaskDispatcher` for runtime. The RQ dispatcher must enqueue only `run_scan_task(task_id)` with the integer ID; it must not serialize archive paths, user objects, request objects, or raw source text into Redis. Add an `rq-worker` Flask CLI command that instantiates a worker on `app.config["RQ_QUEUE_NAME"]`.

- [ ] **Step 4: Run orchestration tests.**

Run: `python -m pytest backend/tests/test_scan_orchestrator.py -q`

Expected: PASS.

## Task 7: Add workspace-scoped project and ZIP scan APIs

**Files:**
- Create: `backend/app/routes/projects.py`, `backend/tests/test_projects_api.py`
- Modify: `backend/app/__init__.py`, `backend/app/services/task_dispatcher.py`

**Interfaces:** Consumes JWT identity, workspace service, source intake, and scan dispatcher. Produces `POST /api/security/projects`, `GET /api/security/projects`, `POST /api/security/projects/<project_id>/snapshots:upload`, `GET /api/security/projects/<project_id>/tasks`, `GET /api/security/tasks/<task_id>`, and `GET /api/security/tasks/<task_id>/findings`.

- [ ] **Step 1: Write API security tests.**

```python
# backend/tests/test_projects_api.py

def test_upload_creates_snapshot_and_scan_task(authenticated_client, project, safe_zip):
    response = authenticated_client.post(
        f"/api/security/projects/{project.id}/snapshots:upload",
        data={"archive": (safe_zip, "demo.zip")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 202
    assert response.json["task"]["status"] == "created"


def test_user_cannot_upload_to_project_in_another_workspace(authenticated_client, other_workspace_project, safe_zip):
    response = authenticated_client.post(
        f"/api/security/projects/{other_workspace_project.id}/snapshots:upload",
        data={"archive": (safe_zip, "demo.zip")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 403
    assert response.json == {"error": "无权访问该工作区"}
```

Add cases for missing archive (400), non-ZIP suffix/MIME mismatch (400), malicious ZIP (400), unauthenticated request (401), and cross-workspace task/finding reads (403).

- [ ] **Step 2: Run API tests to verify endpoints are absent.**

Run: `python -m pytest backend/tests/test_projects_api.py -q`

Expected: FAIL with 404.

- [ ] **Step 3: Implement thin authenticated handlers.**

Use `@jwt_required()` and convert `get_jwt_identity()` with `int(...)` exactly once at route entry. The upload route must authorize the project workspace, save the archive in a generated task staging directory, call `validate_and_extract_zip`, persist `ProjectSnapshot` and `ScanTask`, emit an audit event, dispatch the integer task ID, and return HTTP 202. Catch `ArchiveValidationError` and return `{ "error": str(error) }` with HTTP 400; do not return tracebacks. Register the blueprint at `/api/security`.

- [ ] **Step 4: Run API tests.**

Run: `python -m pytest backend/tests/test_projects_api.py -q`

Expected: PASS.

## Task 8: Expose the scan vertical slice in Vue and document local verification

**Files:**
- Create: `frontend/src/views/security/Projects.vue`, `frontend/src/views/security/ProjectDetail.vue`, `frontend/src/components/security/ScanStatusTag.vue`, `frontend/src/components/security/FindingSeverityTag.vue`, `frontend/src/views/security/__tests__/Projects.spec.js`, `frontend/vitest.config.js`, `frontend/src/test/setup.js`, `.gitignore`, `.github/workflows/ci.yml`
- Modify: `frontend/src/api/index.js`, `frontend/src/router/index.js`, `frontend/src/views/Home.vue`, `frontend/package.json`, `README.md`

**Interfaces:** Consumes Task 7 endpoint shapes. Produces `securityAPI.createProject`, `securityAPI.listProjects`, `securityAPI.uploadSnapshot`, `securityAPI.getTasks`, and `securityAPI.getFindings`; protected project list/detail routes.

- [ ] **Step 1: Write a failing UI test.**

```javascript
// frontend/src/views/security/__tests__/Projects.spec.js
it('submits a ZIP and shows the returned queued task', async () => {
  securityAPI.listProjects.mockResolvedValue({ items: [{ id: 1, name: 'demo' }] })
  securityAPI.uploadSnapshot.mockResolvedValue({ task: { id: 9, status: 'created' } })
  const wrapper = mount(Projects, { global: { plugins: [pinia, router] } })

  await flushPromises()
  await wrapper.get('[data-test="archive-input"]').setValue(makeZipFile())
  await wrapper.get('[data-test="submit-scan"]').trigger('click')

  expect(wrapper.text()).toContain('任务 #9')
  expect(wrapper.text()).toContain('等待校验')
})
```

Add cases for loading state, empty state, backend validation error, and duplicate-submit disabled state.

- [ ] **Step 2: Run the test to confirm failure.**

Run: `npm --prefix frontend run test:unit:run -- src/views/security/__tests__/Projects.spec.js`

Expected: FAIL because the script/component/module does not exist.

- [ ] **Step 3: Implement the minimal secure UX.**

Add `securityAPI` methods with `multipart/form-data` only for upload. `Projects.vue` must provide a labeled project-name field, list user-visible projects, restrict the browser-selected archive to `.zip` as UX only, disable submission while pending, show server validation errors, and navigate to `/security/projects/:id` after selecting a project. It must not expose raw archive contents, raw evidence, secrets, RQ job IDs, or stack traces.

`ProjectDetail.vue` polls task status only while any task is non-terminal, stops polling on unmount, displays status with `ScanStatusTag`, and renders only finding count/severity summary in this phase. Add a `/security/projects` route requiring authentication. Add a Security Workbench entry to the Home navigation only for logged-in users.

Add scripts:

```json
"test:unit": "vitest",
"test:unit:run": "vitest run"
```

Add pinned dev dependencies for Vitest, `@vue/test-utils`, and `jsdom` after checking the existing Vue/Vite compatibility. Update README with the architecture boundary, ZIP-only workflow, required Redis command, test commands, and the statement that uploaded code is never executed.

- [ ] **Step 4: Add CI and ignore generated files.**

Create `.gitignore` entries for `backend/.env`, `backend/data/`, `frontend/node_modules/`, `frontend/dist/`, Python `venv/`, `.pytest_cache/`, coverage outputs, and `.superpowers/`. Create `.github/workflows/ci.yml` that runs backend pytest and frontend test/build on pushes and pull requests after the repository is initialized.

- [ ] **Step 5: Run focused frontend checks.**

Run: `npm --prefix frontend run test:unit:run`

Expected: PASS. Then run: `npm --prefix frontend run build`.

## Task 9: Run the phase verification matrix and record evidence

**Files:**
- Modify: `README.md`

**Interfaces:** Consumes all implemented backend endpoints and frontend routes. Produces reproducible commands and a documented verification evidence table.

- [ ] **Step 1: Execute backend unit/integration suite.**

Run: `python -m pytest backend/tests -q`

Expected: all configuration, model, authorization, ZIP safety, scanner, orchestration, and API tests pass.

- [ ] **Step 2: Execute frontend verification.**

Run: `npm --prefix frontend run test:unit:run`

Expected: all component tests pass.

Run: `npm --prefix frontend run build`

Expected: Vite production build succeeds.

- [ ] **Step 3: Perform a manual safe-input smoke test.**

Start Redis, start the RQ worker, start Flask, start Vite, log in with a non-production account, upload a purpose-built ZIP fixture containing `subprocess.run(cmd, shell=True)`, and verify the task reaches `completed` with a `PY-SHELL-TRUE` high-severity finding. Repeat with a ZIP containing `../escape.py` and verify HTTP 400 plus no file outside the task workspace.

- [ ] **Step 4: Document actual results, not assumptions.**

Add a README verification table with the exact date, command, pass/fail result, and known limitations: ZIP-only input, Python baseline scanner only, no Agent/Diff output yet, and no uploaded-code execution.

## Plan Self-Review

### Spec coverage

This plan implements Phase 1 of the approved design: secure application baseline, workspace isolation, ZIP security controls, task state persistence, Python extensibility seed, deterministic evidence, RQ boundary, project APIs, user workflow, tests, CI skeleton, and verification evidence. It intentionally defers public GitHub import, JavaScript/TypeScript and Java adapters, external SAST/SCA engine selection, security knowledge governance, Agent/RAG evidence synthesis, Diff generation, rule administration, report export, and full audit dashboard to subsequent plans because each is independently reviewable and testable.

### Placeholder scan

The plan has no `TODO`, `TBD`, “implement later”, or unspecified validation step. Every task names files, interfaces, test command, expected result, and exact success behavior.

### Type consistency

All later tasks reference the model names from Task 2, workspace methods from Task 3, archive functions from Task 4, scanner DTOs from Task 5, and dispatcher/orchestration functions from Task 6. Task API and frontend method names are fixed in Tasks 7 and 8.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-security-scanning-foundation-implementation-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, faster parallelism.
2. **Inline Execution** — I execute tasks in this session using executing-plans, with checkpoints.

Which approach?
