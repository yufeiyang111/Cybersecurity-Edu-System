"""Tool registry: the only whitelist through which tools can be invoked."""
from __future__ import annotations

from app.services.security_agent.tools.contracts import ToolDescriptor, ToolHandler


class ToolRegistry:
    """Registers and resolves tools by name; rejects unknown names."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolDescriptor, ToolHandler]] = {}

    def register(self, descriptor: ToolDescriptor, handler: ToolHandler) -> None:
        if descriptor.name in self._tools:
            raise ValueError(f"工具重复注册：{descriptor.name}")
        self._tools[descriptor.name] = (descriptor, handler)

    def resolve(self, name: str) -> tuple[ToolDescriptor, ToolHandler]:
        entry = self._tools.get(name)
        if entry is None:
            raise KeyError(f"工具未注册：{name}")
        return entry

    def has(self, name: str) -> bool:
        return name in self._tools

    def descriptors(self) -> list[ToolDescriptor]:
        return [descriptor for descriptor, _ in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())


_default_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return the process-wide default registry (lazy, deterministic tools only)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
        _register_builtin_tools(_default_registry)
    return _default_registry


def _register_builtin_tools(registry: ToolRegistry) -> None:
    from app.services.security_agent.tools.coverage_tools import build_coverage_handler
    from app.services.security_agent.tools.inventory_tools import build_inventory_handler
    from app.services.security_agent.tools.report_tools import build_report_handler
    from app.services.security_agent.tools.risk_tools import (
        build_findings_handler,
        build_rank_findings_handler,
    )
    from app.services.security_agent.tools.scan_tools import (
        build_baseline_scan_handler,
        build_dependency_inventory_handler,
    )

    registry.register(
        ToolDescriptor(
            name="inventory_snapshot",
            version="1.0",
            category="repository",
            description="清点不可变快照的文件元数据：文件数、总字节数、扩展名分布和语言推断，不读取源码内容。",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=60,
            idempotent=True,
            produces_artifact_types=["inventory_report"],
        ),
        build_inventory_handler(),
    )
    registry.register(
        ToolDescriptor(
            name="run_baseline_scan",
            version="1.0",
            category="scanner",
            description="通过既有扫描管线对快照执行确定性基线扫描（SAST + SCA + 通用 Secret），返回发现统计与任务引用。",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=600,
            idempotent=True,
            produces_artifact_types=["finding_set"],
        ),
        build_baseline_scan_handler(),
    )
    registry.register(
        ToolDescriptor(
            name="get_dependency_inventory",
            version="1.0",
            category="scanner",
            description="读取快照的依赖坐标库存与生态分布。",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=30,
            idempotent=True,
        ),
        build_dependency_inventory_handler(),
    )
    registry.register(
        ToolDescriptor(
            name="get_scan_coverage",
            version="1.0",
            category="coverage",
            description="生成文件级扫描覆盖报告：基线覆盖、专用 SAST、通用扫描、排除与发现分布。",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=30,
            idempotent=True,
            produces_artifact_types=["coverage_report"],
        ),
        build_coverage_handler(),
    )
    registry.register(
        ToolDescriptor(
            name="rank_findings",
            version="1.0",
            category="risk",
            description="复用可解释风险评分对发现项排序，输出严重/高危统计与 Top 列表。",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=30,
            idempotent=True,
            produces_artifact_types=["risk_ranking"],
        ),
        build_rank_findings_handler(),
    )
    registry.register(
        ToolDescriptor(
            name="get_findings",
            version="1.0",
            category="risk",
            description="查询指定快照最近扫描任务的发现项统计。",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=30,
            idempotent=True,
        ),
        build_findings_handler(),
    )
    registry.register(
        ToolDescriptor(
            name="finalize_agent_report",
            version="1.0",
            category="internal",
            description="确定性内部步骤：把已完成节点证据汇总为运行摘要 Artifact，不调用任何外部服务。",
            input_schema={"type": "object", "properties": {}},
            risk_level="safe_read",
            timeout_seconds=10,
            idempotent=True,
            produces_artifact_types=["agent_report"],
        ),
        build_report_handler(),
    )
