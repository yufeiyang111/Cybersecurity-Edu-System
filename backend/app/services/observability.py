# -*- coding: utf-8 -*-
"""请求关联 ID 和安全响应头。"""
from __future__ import annotations

import re
from uuid import uuid4

from flask import Flask, Response, current_app, g, has_app_context, request

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
REQUEST_ID_HEADER = "X-Request-ID"


def register_request_context(app: Flask) -> None:
    """为每个请求建立可追踪但不包含业务数据的关联 ID。"""

    @app.before_request
    def _assign_request_id() -> None:
        supplied = str(request.headers.get(REQUEST_ID_HEADER, "")).strip()
        g.request_id = supplied if _REQUEST_ID_PATTERN.fullmatch(supplied) else uuid4().hex

    @app.after_request
    def _attach_request_id(response: Response) -> Response:
        response.headers[REQUEST_ID_HEADER] = getattr(g, "request_id", uuid4().hex)
        return response


def get_request_id() -> str:
    """返回当前请求关联 ID，非请求上下文时生成短生命周期 ID。"""
    return str(getattr(g, "request_id", uuid4().hex))


RAG_RUNTIME_METRICS_EXTENSION = "rag_runtime_metrics"


def register_rag_runtime_metrics(app: Flask) -> None:
    """注册当前 Flask worker 私有的 RAG 指标聚合器。"""
    from app.services.rag_core.metrics import RagRuntimeMetrics

    sample_limit = app.config.get("RAG_METRICS_SAMPLE_LIMIT", 512)
    app.extensions[RAG_RUNTIME_METRICS_EXTENSION] = RagRuntimeMetrics(
        sample_limit=int(sample_limit),
    )


def get_rag_runtime_metrics():
    """返回当前应用的 RAG 指标聚合器；脱离 Flask 上下文时安全返回空值。"""
    if not has_app_context():
        return None
    metrics = current_app.extensions.get(RAG_RUNTIME_METRICS_EXTENSION)
    from app.services.rag_core.metrics import RagRuntimeMetrics

    return metrics if isinstance(metrics, RagRuntimeMetrics) else None
