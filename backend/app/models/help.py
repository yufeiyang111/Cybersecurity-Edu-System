"""
帮助中心数据模型

- `HelpCategory`：树形分类（parent_id 自引用，可两层：父类 → 子类）
- `HelpDocument`：面向用户的 Markdown 文档，归属单个分类，版本自增
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app import db


class HelpCategory(db.Model):
    __tablename__ = "help_categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255))
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("help_categories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    parent = db.relationship(
        "HelpCategory",
        remote_side="HelpCategory.id",
        backref="children",
    )
    documents = db.relationship(
        "HelpDocument",
        backref="category",
        lazy="dynamic",
    )

    def to_dict(self, include_documents: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_documents:
            data["documents"] = [
                doc.to_dict(include_content=False)
                for doc in sorted(
                    self.documents,
                    key=lambda d: (d.sort_order, d.id),
                )
            ]
        return data


class HelpDocument(db.Model):
    __tablename__ = "help_documents"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(96), unique=True, nullable=False)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("help_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500))
    content = db.Column(db.Text, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_by = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def to_dict(self, include_content: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "slug": self.slug,
            "category_id": self.category_id,
            "category_slug": self.category.slug if self.category else None,
            "title": self.title,
            "summary": self.summary,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
            "version": self.version,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_content:
            data["content"] = self.content
        return data


__all__ = ["HelpCategory", "HelpDocument"]