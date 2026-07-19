"""
知识库相关模型
"""
from datetime import datetime
from app import db

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    icon = db.Column(db.String(50))
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship("Category", remote_side=[id], backref="children")
    items = db.relationship("KnowledgeItem", back_populates="category", cascade="all, delete-orphan")

    def to_dict(self, include_children=False):
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "icon": self.icon,
            "sort_order": self.sort_order,
            "item_count": len(self.items)
        }
        if include_children:
            result["children"] = [child.to_dict() for child in self.children]
        return result

class KnowledgeItem(db.Model):
    __tablename__ = "knowledge_items"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    difficulty = db.Column(db.Enum("easy", "medium", "hard"), default="medium")
    source = db.Column(db.String(200))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    view_count = db.Column(db.Integer, default=0)
    favorite_count = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum("draft", "published", "archived"), default="published")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = db.relationship("Category", back_populates="items")
    author = db.relationship("User")
    tags = db.relationship("KnowledgeTag", back_populates="knowledge_item", cascade="all, delete-orphan")

    def to_dict(self, include_content=True):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content if include_content else None,
            "summary": self.summary,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else "",
            "difficulty": self.difficulty,
            "source": self.source,
            "author": self.author.username if self.author else "",
            "view_count": self.view_count,
            "tags": [tag.tag_name for tag in self.tags],
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else ""
        }

class KnowledgeTag(db.Model):
    __tablename__ = "knowledge_tags"
    id = db.Column(db.Integer, primary_key=True)
    knowledge_id = db.Column(db.Integer, db.ForeignKey("knowledge_items.id"), nullable=False)
    tag_name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    knowledge_item = db.relationship("KnowledgeItem", back_populates="tags")

    __table_args__ = (db.UniqueConstraint("knowledge_id", "tag_name"),)


class KnowledgeFavorite(db.Model):
    """知识收藏"""
    __tablename__ = "knowledge_favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    knowledge_id = db.Column(db.Integer, db.ForeignKey("knowledge_items.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="knowledge_favorites")
    knowledge = db.relationship("KnowledgeItem", backref="favorites")

    __table_args__ = (db.UniqueConstraint("user_id", "knowledge_id"),)
