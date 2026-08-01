"""
政策文档模型（用户协议 / 隐私政策等面向用户的公开文档）
"""
from datetime import datetime

from app import db


class PolicyDocument(db.Model):
    __tablename__ = "policy_documents"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_by = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_content: bool = True) -> dict:
        data = {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "version": self.version,
            "updated_by": self.updated_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            data["content"] = self.content
        return data
