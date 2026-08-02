"""出站网络环境适配：修复 Windows 系统代理 scheme 解析问题。

Windows 下 urllib.request.getproxies() 会把注册表里的本地代理
（如 127.0.0.1:7897，Clash 等工具的明文 HTTP 端口）为 https 协议
解析成 https:// 形式，导致 requests 对代理自身发起 TLS 握手失败
（SSLEOFError: EOF occurred in violation of protocol）。

本模块把系统代理统一规范化为 http:// 并写入环境变量，requests 会
优先使用环境变量；若用户已显式配置 HTTP_PROXY/HTTPS_PROXY，则不干预。
"""

from __future__ import annotations

import os
import urllib.request


def normalize_system_proxy_env() -> None:
    """将系统代理规范化为 http:// 写入环境变量，供 requests 使用。"""
    if os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"):
        return
    if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
        return

    proxies = urllib.request.getproxies()
    if not proxies:
        return

    proxy = proxies.get("http") or proxies.get("https")
    if not proxy:
        return

    host = proxy.split("://", 1)[-1]
    normalized = f"http://{host}"
    os.environ["HTTP_PROXY"] = normalized
    os.environ["HTTPS_PROXY"] = normalized
