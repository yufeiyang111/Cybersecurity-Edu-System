"""
用户相关模型
"""
import json
from datetime import datetime
from app import db
import bcrypt

class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    permissions = db.Column(db.JSON)
    users = db.relationship("User", back_populates="role")

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    nickname = db.Column(db.String(50))
    avatar_url = db.Column(db.Text)
    oauth_provider = db.Column(db.String(20), nullable=True)
    oauth_subject = db.Column(db.String(100), nullable=True)
    oauth_bindings = db.Column(db.Text, nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), default=3)
    is_active = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("oauth_provider", "oauth_subject", name="uq_users_oauth"),
    )

    role = db.relationship("Role", back_populates="users")
    qa_records = db.relationship("QARecord", back_populates="user", cascade="all, delete-orphan")
    favorites = db.relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    conversations = db.relationship("QAConversation", back_populates="user", cascade="all, delete-orphan")
    workspace_memberships = db.relationship("WorkspaceMember", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def check_password(self, password):
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def get_oauth_bindings(self):
        """返回全部第三方绑定列表：[{"provider": ..., "subject": ...}, ...]"""
        if not self.oauth_bindings:
            return []
        try:
            bindings = json.loads(self.oauth_bindings)
            if not isinstance(bindings, list):
                return []
            return [b for b in bindings if isinstance(b, dict) and b.get("provider") and b.get("subject")]
        except (ValueError, TypeError):
            return []

    def add_oauth_binding(self, provider, subject):
        """追加（或覆盖同 provider）一个第三方绑定，并同步主绑定列。"""
        bindings = [b for b in self.get_oauth_bindings() if b.get("provider") != provider]
        bindings.append({"provider": provider, "subject": str(subject)})
        self.oauth_bindings = json.dumps(bindings, ensure_ascii=False)
        self.oauth_provider = provider
        self.oauth_subject = str(subject)

    def has_oauth_binding(self, provider, subject):
        return any(
            b.get("provider") == provider and str(b.get("subject")) == str(subject)
            for b in self.get_oauth_bindings()
        ) or (self.oauth_provider == provider and str(self.oauth_subject) == str(subject))

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "nickname": self.nickname,
            "avatar_url": self.avatar_url,
            "oauth_provider": self.oauth_provider,
            "oauth_bindings": self.get_oauth_bindings(),
            "role": self.role.name if self.role else "guest",
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class LoginLog(db.Model):
    __tablename__ = "login_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.Enum("success", "failed"), default="success")


