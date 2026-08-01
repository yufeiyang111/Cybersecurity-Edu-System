"""请求关联 ID 和安全响应头。"""
from __future__ import annotations

import re
from uuid import uuid4

from flask import Flask, Response, g, request

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