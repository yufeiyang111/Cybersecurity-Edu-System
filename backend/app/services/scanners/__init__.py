"""Scanner Plugin 注册入口和兼容公共 API。"""
from __future__ import annotations

from .base import BaseLanguageScanner, ProjectProfile, RawFinding
from .contracts import NormalizedFinding, ScannerDescriptor
from .go_scanner import GoScanner
from .java_scanner import JavaScanner
from .javascript_scanner import JavaScriptTypeScriptScanner
from .normalizer import finding_fingerprint, normalize_finding
from .python_scanner import PythonScanner
from .registry import ScannerRegistry, descriptor_for


def _build_default_registry() -> ScannerRegistry:
    registry = ScannerRegistry()
    registry.register(PythonScanner)
    registry.register(JavaScriptTypeScriptScanner)
    registry.register(JavaScanner)
    registry.register(GoScanner)
    return registry


_DEFAULT_REGISTRY = _build_default_registry()


def get_scanners() -> list[BaseLanguageScanner]:
    """按稳定注册顺序返回新的 Scanner 实例。"""
    return _DEFAULT_REGISTRY.create_scanners()


def get_scanner_descriptors() -> list[ScannerDescriptor]:
    """返回已注册 Scanner 的安全能力描述。"""
    return _DEFAULT_REGISTRY.describe()


def scanner_registry() -> ScannerRegistry:
    """返回默认 Registry；调用方不应直接修改其注册项。"""
    return _DEFAULT_REGISTRY


__all__ = [
    "BaseLanguageScanner",
    "ProjectProfile",
    "RawFinding",
    "NormalizedFinding",
    "ScannerDescriptor",
    "ScannerRegistry",
    "GoScanner",
    "JavaScanner",
    "JavaScriptTypeScriptScanner",
    "PythonScanner",
    "descriptor_for",
    "finding_fingerprint",
    "get_scanner_descriptors",
    "get_scanners",
    "normalize_finding",
    "scanner_registry",
]
