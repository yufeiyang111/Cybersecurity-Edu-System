"""Windows 系统代理 scheme 规范化工具测试。"""
from __future__ import annotations

import os
from unittest.mock import patch

from app.utils.proxy import normalize_system_proxy_env


class TestNormalizeSystemProxyEnv:
    def _clear_proxy_env(self):
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            os.environ.pop(key, None)

    def test_normalizes_https_system_proxy_to_http(self):
        self._clear_proxy_env()
        try:
            with patch(
                "urllib.request.getproxies",
                return_value={
                    "http": "http://127.0.0.1:7897",
                    "https": "https://127.0.0.1:7897",
                },
            ):
                normalize_system_proxy_env()
            assert os.environ.get("HTTP_PROXY") == "http://127.0.0.1:7897"
            assert os.environ.get("HTTPS_PROXY") == "http://127.0.0.1:7897"
        finally:
            self._clear_proxy_env()

    def test_skips_when_no_system_proxy(self):
        self._clear_proxy_env()
        try:
            with patch("urllib.request.getproxies", return_value={}):
                normalize_system_proxy_env()
            assert "HTTP_PROXY" not in os.environ
            assert "HTTPS_PROXY" not in os.environ
        finally:
            self._clear_proxy_env()

    def test_respects_explicit_https_proxy_env(self):
        self._clear_proxy_env()
        try:
            os.environ["HTTPS_PROXY"] = "http://my-corporate-proxy:8080"
            with patch(
                "urllib.request.getproxies",
                return_value={"https": "https://127.0.0.1:7897"},
            ):
                normalize_system_proxy_env()
            assert os.environ["HTTPS_PROXY"] == "http://my-corporate-proxy:8080"
            assert os.environ.get("HTTP_PROXY") is None
        finally:
            self._clear_proxy_env()
