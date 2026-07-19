"""
Swagger API 文档配置
使用 Flasgger 自动生成 API 文档
"""
from flasgger import Swagger, swag_from
from flask import Flask

# Swagger 配置
SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs/"
}

SWAGGER_TEMPLATE = {
    "info": {
        "title": "CyberGuard 网络安全智能问答教学系统 API",
        "description": """
## 系统简介
CyberGuard 是一个基于检索增强生成(RAG)技术的网络安全智能问答教学系统。

## 核心功能
- **智能问答**: 基于网络安全知识库的智能问答
- **知识图谱**: 可视化知识点关联关系
- **用户管理**: 完整的用户权限体系
- **知识库管理**: 知识的增删改查和批量导入

## 认证方式
除公开接口外，所有接口需要 JWT Token 认证。
在请求头中添加: `Authorization: Bearer <token>`

## 反馈说明
- 👍 good: 答案满意
- 😐 neutral: 答案一般
- 👎 bad: 答案不满意
        """,
        "version": "1.0.0",
        "contact": {
            "name": "API Support"
        }
    },
    "host": "localhost:5000",
    "basePath": "/api",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Token. Format: Bearer <token>"
        }
    },
    "tags": [
        {"name": "认证", "description": "用户认证相关接口"},
        {"name": "知识库", "description": "知识库管理接口"},
        {"name": "问答", "description": "智能问答接口"},
        {"name": "收藏", "description": "收藏管理接口"},
        {"name": "管理员", "description": "系统管理接口"}
    ]
}


def init_swagger(app: Flask):
    """初始化 Swagger"""
    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)


# ========== Swagger 装饰器辅助函数 ==========

def swag_tag(tag: str):
    """设置 Swagger 标签"""
    return {"tags": [tag]}


def swag_auth():
    """需要认证"""
    return {"security": [{"Bearer": []}]}


def swag_response(code: int, description: str, schema: dict = None):
    """响应定义"""
    resp = {"responses": {str(code): {"description": description}}}
    if schema:
        resp["responses"][str(code)]["schema"] = schema
    return resp
