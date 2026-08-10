"""
帮助中心领域服务

职责边界：
- 分类树 / 文档的查询（公开视图 + 管理视图）
- 文档与分类的 CRUD（仅管理员）
- 树形结构组装、排序、激活过滤
- 首次启动时的幂等种子

路由层仅做参数校验与鉴权委派，所有持久化逻辑收敛在此。
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.help import HelpCategory, HelpDocument
from app.services import help_seed


class HelpCategoryNotFound(Exception):
    """分类不存在或被禁用。"""


class HelpDocumentNotFound(Exception):
    """文档不存在或被禁用。"""


class HelpCategoryInUse(Exception):
    """分类下仍有文档，禁止删除。"""


class HelpValidationError(Exception):
    """字段校验失败。"""


# 字段长度常量，集中维护便于路由层复用
MAX_TITLE_LEN = 200
MAX_SLUG_LEN = 64
MAX_DOC_SLUG_LEN = 96
MAX_SUMMARY_LEN = 500
MAX_NAME_LEN = 80
MAX_DESCRIPTION_LEN = 255
MAX_CONTENT_LEN = 200_000


# ---------------------- 公开读取 ----------------------

def list_active_tree() -> list[dict[str, Any]]:
    """返回公开树形：仅含顶层激活分类（子分类在 children 内）+ 其下激活文档（不含正文）。"""
    _ensure_seed()
    categories = (
        HelpCategory.query.filter_by(is_active=True)
        .filter(HelpCategory.parent_id.is_(None))
        .order_by(HelpCategory.sort_order.asc(), HelpCategory.id.asc())
        .all()
    )
    return [_category_to_tree_node(cat, include_documents=True, only_active_docs=True) for cat in categories]


def get_active_document(slug: str) -> HelpDocument:
    """公开读取单篇文档，未激活或不存在时抛 HelpDocumentNotFound。"""
    _ensure_seed()
    document = (
        HelpDocument.query.filter_by(slug=slug, is_active=True)
        .first()
    )
    if document is None:
        raise HelpDocumentNotFound(f"帮助文档不存在或未启用: {slug}")
    return document


# ---------------------- 管理视图 ----------------------

def list_admin_tree() -> list[dict[str, Any]]:
    """管理视图：仅返回顶层分类（含未激活），子分类在 children 内。"""
    _ensure_seed()
    categories = (
        HelpCategory.query.filter(HelpCategory.parent_id.is_(None))
        .order_by(HelpCategory.sort_order.asc(), HelpCategory.id.asc())
        .all()
    )
    return [_category_to_tree_node(cat, include_documents=True, only_active_docs=False) for cat in categories]


def get_admin_document(document_id: int) -> HelpDocument:
    document = db.session.get(HelpDocument, document_id)
    if document is None:
        raise HelpDocumentNotFound(f"文档 #{document_id} 不存在")
    return document


# ---------------------- 分类 CRUD ----------------------

def _validate_slug(slug: str, *, max_len: int) -> str:
    if not slug:
        raise HelpValidationError("slug 不能为空")
    if len(slug) > max_len:
        raise HelpValidationError(f"slug 长度不能超过 {max_len}")
    if not all(c.isalnum() or c in "-_" for c in slug):
        raise HelpValidationError("slug 仅允许字母、数字、连字符、下划线")
    return slug


def _validate_required_text(value: str, field: str, max_len: int) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HelpValidationError(f"{field}不能为空")
    if len(cleaned) > max_len:
        raise HelpValidationError(f"{field}长度不能超过 {max_len} 个字符")
    return cleaned


def create_category(
    *,
    slug: str,
    name: str,
    description: Optional[str] = None,
    parent_id: Optional[int] = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> HelpCategory:
    _ensure_seed()
    slug = _validate_slug(slug, max_len=MAX_SLUG_LEN).lower()
    name = _validate_required_text(name, "分类名称", MAX_NAME_LEN)
    description = (description or "").strip() or None
    if description and len(description) > MAX_DESCRIPTION_LEN:
        raise HelpValidationError(f"分类描述长度不能超过 {MAX_DESCRIPTION_LEN}")
    if parent_id is not None:
        parent = db.session.get(HelpCategory, parent_id)
        if parent is None:
            raise HelpCategoryNotFound(f"父分类 #{parent_id} 不存在")

    category = HelpCategory(
        slug=slug,
        name=name,
        description=description,
        parent_id=parent_id,
        sort_order=sort_order,
        is_active=is_active,
    )
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise HelpValidationError(f"分类 slug 已存在: {slug}") from exc
    return category


def update_category(
    category_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    parent_id: Optional[int] = None,
    sort_order: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> HelpCategory:
    _ensure_seed()
    category = db.session.get(HelpCategory, category_id)
    if category is None:
        raise HelpCategoryNotFound(f"分类 #{category_id} 不存在")

    if name is not None:
        category.name = _validate_required_text(name, "分类名称", MAX_NAME_LEN)
    if description is not None:
        description_clean = description.strip() or None
        if description_clean and len(description_clean) > MAX_DESCRIPTION_LEN:
            raise HelpValidationError(f"分类描述长度不能超过 {MAX_DESCRIPTION_LEN}")
        category.description = description_clean
    if parent_id is not None:
        if parent_id == category.id:
            raise HelpValidationError("分类不能将自己设为父分类")
        parent = db.session.get(HelpCategory, parent_id)
        if parent is None:
            raise HelpCategoryNotFound(f"父分类 #{parent_id} 不存在")
        category.parent_id = parent_id
    if sort_order is not None:
        category.sort_order = sort_order
    if is_active is not None:
        category.is_active = is_active
    db.session.commit()
    return category


def delete_category(category_id: int) -> None:
    _ensure_seed()
    category = db.session.get(HelpCategory, category_id)
    if category is None:
        raise HelpCategoryNotFound(f"分类 #{category_id} 不存在")
    doc_count = (
        db.session.query(func.count(HelpDocument.id))
        .filter(HelpDocument.category_id == category_id)
        .scalar()
    )
    if doc_count and doc_count > 0:
        raise HelpCategoryInUse(f"分类下仍有 {doc_count} 篇文档，请先迁移或删除")
    child_count = (
        db.session.query(func.count(HelpCategory.id))
        .filter(HelpCategory.parent_id == category_id)
        .scalar()
    )
    if child_count and child_count > 0:
        raise HelpCategoryInUse(f"分类下仍有 {child_count} 个子分类")
    db.session.delete(category)
    db.session.commit()


# ---------------------- 文档 CRUD ----------------------

def create_document(
    *,
    slug: str,
    category_id: int,
    title: str,
    content: str,
    summary: Optional[str] = None,
    sort_order: int = 0,
    is_active: bool = True,
    updated_by: Optional[str] = None,
) -> HelpDocument:
    _ensure_seed()
    slug = _validate_slug(slug, max_len=MAX_DOC_SLUG_LEN).lower()
    title = _validate_required_text(title, "文档标题", MAX_TITLE_LEN)
    content_clean = _validate_required_text(content, "文档正文", MAX_CONTENT_LEN)
    summary_clean = (summary or "").strip() or None
    if summary_clean and len(summary_clean) > MAX_SUMMARY_LEN:
        raise HelpValidationError(f"摘要长度不能超过 {MAX_SUMMARY_LEN}")
    category = db.session.get(HelpCategory, category_id)
    if category is None:
        raise HelpCategoryNotFound(f"分类 #{category_id} 不存在")

    document = HelpDocument(
        slug=slug,
        category_id=category_id,
        title=title,
        summary=summary_clean,
        content=content_clean,
        sort_order=sort_order,
        is_active=is_active,
        version=1,
        updated_by=updated_by,
    )
    db.session.add(document)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise HelpValidationError(f"文档 slug 已存在: {slug}") from exc
    return document


def update_document(
    document_id: int,
    *,
    title: Optional[str] = None,
    content: Optional[str] = None,
    summary: Optional[str] = None,
    category_id: Optional[int] = None,
    sort_order: Optional[int] = None,
    is_active: Optional[bool] = None,
    updated_by: Optional[str] = None,
) -> HelpDocument:
    _ensure_seed()
    document = db.session.get(HelpDocument, document_id)
    if document is None:
        raise HelpDocumentNotFound(f"文档 #{document_id} 不存在")

    if title is not None:
        document.title = _validate_required_text(title, "文档标题", MAX_TITLE_LEN)
    if content is not None:
        document.content = _validate_required_text(content, "文档正文", MAX_CONTENT_LEN)
        document.version = (document.version or 1) + 1
    if summary is not None:
        summary_clean = summary.strip() or None
        if summary_clean and len(summary_clean) > MAX_SUMMARY_LEN:
            raise HelpValidationError(f"摘要长度不能超过 {MAX_SUMMARY_LEN}")
        document.summary = summary_clean
    if category_id is not None and category_id != document.category_id:
        category = db.session.get(HelpCategory, category_id)
        if category is None:
            raise HelpCategoryNotFound(f"分类 #{category_id} 不存在")
        document.category_id = category_id
    if sort_order is not None:
        document.sort_order = sort_order
    if is_active is not None:
        document.is_active = is_active
    if updated_by is not None:
        document.updated_by = updated_by
    db.session.commit()
    return document


def delete_document(document_id: int) -> None:
    _ensure_seed()
    document = db.session.get(HelpDocument, document_id)
    if document is None:
        raise HelpDocumentNotFound(f"文档 #{document_id} 不存在")
    db.session.delete(document)
    db.session.commit()


# ---------------------- 内部工具 ----------------------

def _category_to_tree_node(
    category: HelpCategory,
    *,
    include_documents: bool,
    only_active_docs: bool,
) -> dict[str, Any]:
    node = category.to_dict(include_documents=False)
    node["documents"] = []
    if include_documents:
        docs = sorted(category.documents, key=lambda d: (d.sort_order, d.id))
        for doc in docs:
            if only_active_docs and not doc.is_active:
                continue
            node["documents"].append(doc.to_dict(include_content=False))
    children = sorted(category.children, key=lambda c: (c.sort_order, c.id))
    node["children"] = [
        _category_to_tree_node(child, include_documents=include_documents, only_active_docs=only_active_docs)
        for child in children
    ]
    return node


# ---------------------- 种子 ----------------------

def _ensure_seed() -> None:
    """惰性建表后第一次访问时幂等写入种子分类 + 文档。"""
    if HelpCategory.query.count() == 0:
        _create_seed()
        return
    _refresh_seed_documents()


def _create_seed() -> None:
    """首次建种子：分类 + 文档全量写入。"""
    # 1) 先建顶层分类
    slug_to_id: dict[str, int] = {}
    for entry in help_seed.CATEGORY_SEED:
        parent_slug = None  # 顶层无父
        category = HelpCategory(
            slug=entry["slug"],
            name=entry["name"],
            description=entry.get("description"),
            parent_id=None,
            sort_order=entry.get("sort_order", 0),
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()
        slug_to_id[entry["slug"]] = category.id

        # 2) 再建子分类
        for child in entry.get("children", []) or []:
            child_category = HelpCategory(
                slug=child["slug"],
                name=child["name"],
                description=child.get("description"),
                parent_id=category.id,
                sort_order=child.get("sort_order", 0),
                is_active=True,
            )
            db.session.add(child_category)
            db.session.flush()
            slug_to_id[child["slug"]] = child_category.id

    # 3) 写入文档
    for doc_seed in help_seed.DOCUMENT_SEED:
        category_id = slug_to_id.get(doc_seed["category_slug"])
        if category_id is None:
            continue
        document = HelpDocument(
            slug=doc_seed["slug"],
            category_id=category_id,
            title=doc_seed["title"],
            summary=doc_seed.get("summary"),
            content=doc_seed["content"],
            sort_order=doc_seed.get("sort_order", 0),
            is_active=True,
            version=1,
            updated_by="system",
        )
        db.session.add(document)

    db.session.commit()


def _refresh_seed_documents() -> None:
    """更新种子分类描述与文档内容（仅限未被管理员改动的条目）。

    分类规则：slug 匹配且 name 未被改动（管理员改过 name 视为已接管，跳过）。
    文档规则：`updated_by == 'system'` 时若与当前种子内容不一致则刷新；
    管理员编辑过的文档（updated_by 为用户名）不会被覆盖。
    """
    changed = False

    def _refresh_category_entry(entry: dict) -> Optional[HelpCategory]:
        nonlocal changed
        category = HelpCategory.query.filter_by(slug=entry["slug"]).first()
        if category is None:
            return None
        if category.name == entry["name"] and (
            category.description != entry.get("description")
            or category.sort_order != entry.get("sort_order", 0)
        ):
            category.description = entry.get("description")
            category.sort_order = entry.get("sort_order", 0)
            changed = True
        return category

    for entry in help_seed.CATEGORY_SEED:
        _refresh_category_entry(entry)
        for child in entry.get("children", []) or []:
            _refresh_category_entry(child)

    for doc_seed in help_seed.DOCUMENT_SEED:
        category = HelpCategory.query.filter_by(slug=doc_seed["category_slug"]).first()
        if category is None:
            continue
        existing = HelpDocument.query.filter_by(slug=doc_seed["slug"]).first()
        if existing is None:
            db.session.add(
                HelpDocument(
                    slug=doc_seed["slug"],
                    category_id=category.id,
                    title=doc_seed["title"],
                    summary=doc_seed.get("summary"),
                    content=doc_seed["content"],
                    sort_order=doc_seed.get("sort_order", 0),
                    is_active=True,
                    version=1,
                    updated_by="system",
                )
            )
            changed = True
            continue
        if existing.updated_by == "system" and existing.content != doc_seed["content"]:
            existing.title = doc_seed["title"]
            existing.summary = doc_seed.get("summary")
            existing.content = doc_seed["content"]
            existing.sort_order = doc_seed.get("sort_order", 0)
            existing.version = (existing.version or 1) + 1
            changed = True
    if changed:
        db.session.commit()