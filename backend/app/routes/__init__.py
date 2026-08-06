"""
路由包初始化
"""
from app.routes.auth import auth_bp
from app.routes.knowledge import knowledge_bp
from app.routes.qa import qa_bp
from app.routes.admin import admin_bp
from app.routes.llm import llm_bp

__all__ = ["auth_bp", "knowledge_bp", "qa_bp", "admin_bp", "llm_bp"]
