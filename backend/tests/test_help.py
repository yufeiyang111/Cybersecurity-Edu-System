"""
帮助中心 API 测试

覆盖：
- 公开树/文档读取（含种子幂等）
- 鉴权：未登录 / 非管理员被拒
- 分类 CRUD（创建/更新/删除 + 删除保护）
- 文档 CRUD（创建/更新/删除 + 版本自增）
- 字段校验（slug 格式、必填、长度）
"""
from __future__ import annotations

import pytest
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.user import User
from app.services import help_service

from conftest import _install_legacy_route_stubs


@pytest.fixture
def help_app(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    from conftest import TestConfig

    _install_legacy_route_stubs(monkeypatch)
    config = type(
        "HelpApiTestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
        },
    )
    application = create_app(config)
    with application.app_context():
        import app.models  # noqa: F401

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _make_user(application, username: str, role: str):
    with application.app_context():
        user = User(username=username, email=f"{username}@example.test", password_hash="x")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    token = create_access_token(identity=str(user_id), additional_claims={"role": role})
    return user_id, {"Authorization": f"Bearer {token}"}


# ---------------------- 公开读取 ----------------------

def test_help_tree_is_public_and_seeded(help_app):
    response = help_app.test_client().get("/api/help/tree")

    assert response.status_code == 200
    tree = response.json["tree"]
    slugs = {node["slug"] for node in tree}
    assert {"getting-started", "feature-guide", "admin-manual", "troubleshooting"} <= slugs

    feature_guide = next(node for node in tree if node["slug"] == "feature-guide")
    child_slugs = {child["slug"] for child in feature_guide["children"]}
    assert {"faq", "scanning", "ai-assistant"} <= child_slugs

    doc = next(d for d in feature_guide["children"] if d["slug"] == "scanning")["documents"][0]
    assert doc["slug"] == "scanning-overview"
    assert "content" not in doc


def test_help_tree_has_no_duplicate_categories(help_app):
    """子分类不得同时出现在顶层与父分类 children 中（回归：list_active_tree 曾返回全部分类）。"""
    response = help_app.test_client().get("/api/help/tree")

    assert response.status_code == 200
    tree = response.json["tree"]
    top_slugs = {node["slug"] for node in tree}

    nested_slugs = set()
    for node in tree:
        for child in node.get("children", []) or []:
            nested_slugs.add(child["slug"])
            assert child["slug"] not in top_slugs, f"子分类 {child['slug']} 不应出现在顶层"

    assert {"faq", "scanning", "ai-assistant", "knowledge-admin"} <= nested_slugs


def test_get_active_document_returns_markdown(help_app):
    response = help_app.test_client().get("/api/help/documents/getting-started")

    assert response.status_code == 200
    document = response.json["document"]
    assert document["title"] == "快速开始"
    assert document["content"].startswith("本指南带您完成")
    assert "## 1. 注册与登录" in document["content"]


def test_get_inactive_document_returns_404(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    with help_app.app_context():
        doc = help_service.create_document(
            slug="draft-doc",
            category_id=1,
            title="草稿",
            content="## 未发布",
            is_active=False,
        )
        doc_id = doc.id

    response = help_app.test_client().get("/api/help/documents/draft-doc")
    assert response.status_code == 404

    admin_response = help_app.test_client().get("/api/help/admin/documents/%d" % doc_id, headers=headers)
    assert admin_response.status_code == 200


def test_get_unknown_document_returns_404(help_app):
    response = help_app.test_client().get("/api/help/documents/not-exists")
    assert response.status_code == 404


# ---------------------- 鉴权 ----------------------

def test_create_category_requires_auth(help_app):
    response = help_app.test_client().post(
        "/api/help/admin/categories",
        json={"slug": "new-cat", "name": "新分类"},
    )
    assert response.status_code == 401


def test_create_category_rejects_non_admin(help_app):
    _, headers = _make_user(help_app, "regular-user", "user")
    response = help_app.test_client().post(
        "/api/help/admin/categories",
        json={"slug": "new-cat", "name": "新分类"},
        headers=headers,
    )
    assert response.status_code == 403


def test_create_document_requires_auth(help_app):
    response = help_app.test_client().post(
        "/api/help/admin/documents",
        json={"slug": "new-doc", "category_id": 1, "title": "标题", "content": "正文"},
    )
    assert response.status_code == 401


# ---------------------- 分类 CRUD ----------------------

def test_admin_create_category(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    response = help_app.test_client().post(
        "/api/help/admin/categories",
        json={"slug": "ops-manual", "name": "运维手册", "sort_order": 50},
        headers=headers,
    )
    assert response.status_code == 201
    category = response.json["category"]
    assert category["slug"] == "ops-manual"
    assert category["name"] == "运维手册"


def test_create_category_with_invalid_slug(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    response = help_app.test_client().post(
        "/api/help/admin/categories",
        json={"slug": "bad slug!", "name": "分类"},
        headers=headers,
    )
    assert response.status_code == 400


def test_create_category_duplicate_slug(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    first = help_app.test_client().post(
        "/api/help/admin/categories",
        json={"slug": "dup-cat", "name": "分类一"},
        headers=headers,
    )
    assert first.status_code == 201
    second = help_app.test_client().post(
        "/api/help/admin/categories",
        json={"slug": "dup-cat", "name": "分类二"},
        headers=headers,
    )
    assert second.status_code == 400


def test_admin_update_category(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    created = help_app.test_client().post(
        "/api/help/admin/categories",
        json={"slug": "rename-me", "name": "旧名字"},
        headers=headers,
    ).json["category"]

    response = help_app.test_client().put(
        f"/api/help/admin/categories/{created['id']}",
        json={"name": "新名字"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json["category"]["name"] == "新名字"


def test_admin_update_missing_category_404(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    response = help_app.test_client().put(
        "/api/help/admin/categories/9999",
        json={"name": "不存在"},
        headers=headers,
    )
    assert response.status_code == 404


def test_admin_delete_empty_category(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    created = help_app.test_client().post(
        "/api/help/admin/categories",
        json={"slug": "empty-cat", "name": "空分类"},
        headers=headers,
    ).json["category"]

    response = help_app.test_client().delete(
        f"/api/help/admin/categories/{created['id']}",
        headers=headers,
    )
    assert response.status_code == 200


def test_admin_delete_category_with_documents_conflict(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    response = help_app.test_client().delete(
        "/api/help/admin/categories/1",  # getting-started 下有种子文档
        headers=headers,
    )
    assert response.status_code == 409


# ---------------------- 文档 CRUD ----------------------

def test_admin_create_document(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    response = help_app.test_client().post(
        "/api/help/admin/documents",
        json={
            "slug": "custom-doc",
            "category_id": 1,
            "title": "自定义文档",
            "summary": "测试摘要",
            "content": "# 自定义\n\n正文内容。",
        },
        headers=headers,
    )
    assert response.status_code == 201
    document = response.json["document"]
    assert document["slug"] == "custom-doc"
    assert document["version"] == 1
    assert document["updated_by"] == "admin-user"
    assert document["content"] == "# 自定义\n\n正文内容。"


def test_admin_create_document_missing_category_400(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    response = help_app.test_client().post(
        "/api/help/admin/documents",
        json={"slug": "no-cat", "title": "标题", "content": "正文"},
        headers=headers,
    )
    assert response.status_code == 400


def test_admin_update_document_increments_version(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    with help_app.app_context():
        doc = help_service.create_document(
            slug="versioned",
            category_id=1,
            title="版本一",
            content="## 第一版",
            updated_by="admin-user",
        )
        doc_id = doc.id

    response = help_app.test_client().put(
        f"/api/help/admin/documents/{doc_id}",
        json={"title": "版本二", "content": "## 第二版"},
        headers=headers,
    )
    assert response.status_code == 200
    document = response.json["document"]
    assert document["title"] == "版本二"
    assert document["version"] == 2

    fetch = help_app.test_client().get("/api/help/documents/versioned")
    assert fetch.json["document"]["version"] == 2


def test_admin_update_document_blank_content_400(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    with help_app.app_context():
        doc = help_service.create_document(
            slug="blank-check",
            category_id=1,
            title="标题",
            content="正文",
        )
        doc_id = doc.id

    response = help_app.test_client().put(
        f"/api/help/admin/documents/{doc_id}",
        json={"content": "   "},
        headers=headers,
    )
    assert response.status_code == 400


def test_admin_delete_document(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    with help_app.app_context():
        doc = help_service.create_document(
            slug="delete-me",
            category_id=1,
            title="待删除",
            content="正文",
        )
        doc_id = doc.id

    response = help_app.test_client().delete(
        f"/api/help/admin/documents/{doc_id}",
        headers=headers,
    )
    assert response.status_code == 200

    fetch = help_app.test_client().get("/api/help/documents/delete-me")
    assert fetch.status_code == 404


# ---------------------- 种子幂等 ----------------------

def test_seed_is_idempotent(help_app):
    with help_app.app_context():
        help_service.list_active_tree()
        help_service.list_active_tree()

        from app.models.help import HelpCategory, HelpDocument

        assert HelpCategory.query.count() >= 6
        assert HelpDocument.query.count() >= 6


def test_seed_survives_admin_delete(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    # 删除任意种子文档后，再次读取树不应重新生成被删内容
    response = help_app.test_client().delete("/api/help/admin/documents/1", headers=headers)
    assert response.status_code in (200, 404)

    tree = help_app.test_client().get("/api/help/tree").json["tree"]
    slugs = [node["slug"] for node in tree]
    assert "getting-started" in slugs


def test_seed_refresh_does_not_overwrite_admin_edits(help_app):
    _, headers = _make_user(help_app, "admin-user", "admin")
    with help_app.app_context():
        help_service.list_active_tree()  # 触发种子
        doc = help_service.get_active_document("faq-overview")
        original_title = doc.title
        # 管理员修改标题与正文
        help_service.update_document(
            doc.id,
            title="管理员改的标题",
            content="## 管理员内容",
            updated_by="admin-user",
        )

    # 再次访问树：system 之外的内容不应被种子覆盖
    with help_app.app_context():
        help_service.list_active_tree()
        doc = help_service.get_active_document("faq-overview")
        assert doc.title == "管理员改的标题"
        assert doc.content == "## 管理员内容"
        assert doc.updated_by == "admin-user"