"""Scanner Registry：统一注册、实例化和能力发现。"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from typing import TypeAlias

from .base import BaseLanguageScanner
from .contracts import ScannerDescriptor

ScannerFactory: TypeAlias = Callable[[], BaseLanguageScanner]
ScannerRegistration: TypeAlias = type[BaseLanguageScanner] | ScannerFactory | BaseLanguageScanner


class ScannerRegistry:
    """按注册顺序维护 Scanner，避免核心编排依赖具体实现列表。"""

    def __init__(self) -> None:
        self._entries: OrderedDict[str, tuple[ScannerDescriptor, ScannerFactory]] = OrderedDict()

    def register(self, registration: ScannerRegistration) -> None:
        """注册 Scanner 类、工厂或实例，并拒绝重复稳定名称。"""
        factory, probe = _factory_and_probe(registration)
        descriptor = descriptor_for(probe)
        if descriptor.name in self._entries:
            raise ValueError(f"duplicate scanner name: {descriptor.name}")
        self._entries[descriptor.name] = (descriptor, factory)

    def create_scanners(self) -> list[BaseLanguageScanner]:
        """按稳定注册顺序创建 Scanner 实例。"""
        return [factory() for _, factory in self._entries.values()]

    def describe(self) -> list[ScannerDescriptor]:
        """返回可安全展示给上层的能力描述。"""
        return [descriptor for descriptor, _ in self._entries.values()]

    def supports_language(self, language: str) -> bool:
        normalized = str(language or "").strip().lower()
        return any(normalized in descriptor.supported_languages for descriptor in self.describe())


def descriptor_for(scanner: BaseLanguageScanner) -> ScannerDescriptor:
    """从 Scanner 的显式能力属性构造描述，兼容旧 Scanner。"""
    language = str(getattr(scanner, "language", "unknown")).strip().lower() or "unknown"
    name = str(getattr(scanner, "scanner_name", "")).strip() or language
    version = str(getattr(scanner, "scanner_version", "1.0.0")).strip() or "1.0.0"
    languages = tuple(
        str(item).strip().lower()
        for item in getattr(scanner, "supported_languages", (language,))
        if str(item).strip()
    ) or (language,)
    categories = tuple(
        str(item).strip().lower()
        for item in getattr(scanner, "categories", ("sast",))
        if str(item).strip()
    ) or ("sast",)
    return ScannerDescriptor(name, version, languages, categories)


def _factory_and_probe(registration: ScannerRegistration) -> tuple[ScannerFactory, BaseLanguageScanner]:
    if isinstance(registration, BaseLanguageScanner):
        scanner_type = type(registration)
        return scanner_type, registration
    if isinstance(registration, type) and issubclass(registration, BaseLanguageScanner):
        instance = registration()
        return registration, instance
    if not callable(registration):
        raise TypeError("scanner registration must be a scanner, scanner class, or factory")
    instance = registration()
    if not isinstance(instance, BaseLanguageScanner):
        raise TypeError("scanner factory must return BaseLanguageScanner")
    return registration, instance
