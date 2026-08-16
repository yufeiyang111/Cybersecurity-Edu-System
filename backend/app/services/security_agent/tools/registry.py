"""Tool registry: the only whitelist through which tools can be invoked."""
from __future__ import annotations

from app.services.security_agent.tools.contracts import ToolDescriptor, ToolHandler

# 全部内置工具显式声明允许的运行模式与治理字段，不使用危险默认值
_ALL_MODES = ("baseline", "hybrid", "deep_audit")
_BASELINE_MODES = ("baseline", "hybrid", "deep_audit")


class ToolRegistry:
    """Registers and resolves tools by name; rejects unknown names."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolDescriptor, ToolHandler]] = {}

    def register(self, descriptor: ToolDescriptor, handler: ToolHandler) -> None:
        descriptor.validate()
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
        build_run_scanner_handler,
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
            retry_policy=None,
            allowed_modes=_ALL_MODES,
            result_schema_version=1,
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
            retry_policy=None,
            allowed_modes=_BASELINE_MODES,
            result_schema_version=1,
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
            retry_policy=None,
            allowed_modes=_ALL_MODES,
            result_schema_version=1,
        ),
        build_dependency_inventory_handler(),
    )
    registry.register(
        ToolDescriptor(
            name="run_scanner",
            version="1.0",
            category="scanner",
            description="定向执行指定扫描器（scanner_names 必填，如 python-baseline/universal_secret），"
            "复用真实扫描管线并返回该次任务的发现统计。",
            input_schema={
                "type": "object",
                "properties": {
                    "scanner_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    }
                },
                "required": ["scanner_names"],
                "additionalProperties": False,
            },
            risk_level="safe_read",
            timeout_seconds=600,
            idempotent=True,
            produces_artifact_types=["finding_set"],
            retry_policy=None,
            allowed_modes=_ALL_MODES,
            result_schema_version=1,
        ),
        build_run_scanner_handler(),
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
            retry_policy=None,
            allowed_modes=_ALL_MODES,
            result_schema_version=1,
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
            retry_policy=None,
            allowed_modes=_ALL_MODES,
            result_schema_version=1,
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
            retry_policy=None,
            allowed_modes=_ALL_MODES,
            result_schema_version=1,
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
            retry_policy=None,
            allowed_modes=_ALL_MODES,
            result_schema_version=1,
        ),
        build_report_handler(),
    )
    _register_graph_tools(registry)


def _register_graph_tools(registry: ToolRegistry) -> None:
    from app.services.security_agent.tools.code_tools import build_read_code_slice_handler
    from app.services.security_agent.tools.graph_tools import (
        build_call_chain_handler,
        build_find_symbol_references_handler,
        build_get_authentication_map_handler,
        build_get_related_files_handler,
        build_get_route_map_handler,
        build_search_code_handler,
    )
    from app.services.security_agent.tools.repository_tools import build_map_repository_handler
    from app.services.security_agent.tools.review_tools import build_run_deep_review_handler

    graph_tools = [
        (
            ToolDescriptor(
                name="map_repository",
                version="1.0",
                category="repository",
                description="为快照构建项目安全有向图（Route/Service/Repository/Model/调用关系），幂等可重跑。",
                input_schema={"type": "object", "properties": {}},
                risk_level="safe_read",
                timeout_seconds=600,
                idempotent=True,
                produces_artifact_types=["security_graph"],
                retry_policy=None,
                allowed_modes=_ALL_MODES,
                result_schema_version=1,
            ),
            build_map_repository_handler(),
        ),
        (
            ToolDescriptor(
                name="get_route_map",
                version="1.0",
                category="graph",
                description="分页读取快照图的路由/文件入口节点。",
                input_schema={"type": "object", "properties": {"limit": {"type": "integer"}, "offset": {"type": "integer"}}},
                risk_level="safe_read",
                timeout_seconds=30,
                idempotent=True,
                retry_policy=None,
                allowed_modes=_ALL_MODES,
                result_schema_version=1,
            ),
            build_get_route_map_handler(),
        ),
        (
            ToolDescriptor(
                name="get_authentication_map",
                version="1.0",
                category="graph",
                description="启发式过滤路由/中间件/含 auth 或 login 的节点，用于鉴权面梳理。",
                input_schema={"type": "object", "properties": {"limit": {"type": "integer"}, "offset": {"type": "integer"}}},
                risk_level="safe_read",
                timeout_seconds=30,
                idempotent=True,
                retry_policy=None,
                allowed_modes=_ALL_MODES,
                result_schema_version=1,
            ),
            build_get_authentication_map_handler(),
        ),
        (
            ToolDescriptor(
                name="search_code",
                version="1.0",
                category="code",
                description=(
                    "按关键字/标签/文件路径模糊搜索图节点（分页）。"
                    "query 为搜索关键字（必填其一）；也可用 path_pattern/pattern/"
                    "labels 列表或 file_path 片段定位目标。"
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "maxLength": 128},
                        "path_pattern": {"type": "string", "maxLength": 128},
                        "pattern": {"type": "string", "maxLength": 128},
                        "labels": {"type": "array", "items": {"type": "string"}},
                        "file_path": {"type": "string", "maxLength": 256},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "offset": {"type": "integer", "minimum": 0},
                    },
                    "required": [],
                },
                risk_level="safe_read",
                timeout_seconds=30,
                idempotent=True,
                retry_policy=None,
                allowed_modes=_ALL_MODES,
                result_schema_version=1,
            ),
            build_search_code_handler(),
        ),
        (
            ToolDescriptor(
                name="find_symbol_references",
                version="1.0",
                category="graph",
                description="查询指向某符号节点的入边（谁引用它），分页。",
                input_schema={"type": "object", "properties": {"symbol": {"type": "string"}, "limit": {"type": "integer"}, "offset": {"type": "integer"}}},
                risk_level="safe_read",
                timeout_seconds=30,
                idempotent=True,
                retry_policy=None,
                allowed_modes=_ALL_MODES,
                result_schema_version=1,
            ),
            build_find_symbol_references_handler(),
        ),
        (
            ToolDescriptor(
                name="get_related_files",
                version="1.0",
                category="graph",
                description="查询某个文件路径下的全部图节点。",
                input_schema={"type": "object", "properties": {"file_path": {"type": "string"}}},
                risk_level="safe_read",
                timeout_seconds=30,
                idempotent=True,
                retry_policy=None,
                allowed_modes=_ALL_MODES,
                result_schema_version=1,
            ),
            build_get_related_files_handler(),
        ),
        (
            ToolDescriptor(
                name="build_call_chain",
                version="1.0",
                category="graph",
                description="按上游调用边追溯符号的调用链（深度受限）。",
                input_schema={"type": "object", "properties": {"symbol": {"type": "string"}, "depth": {"type": "integer"}}},
                risk_level="safe_read",
                timeout_seconds=60,
                idempotent=True,
                retry_policy=None,
                allowed_modes=_ALL_MODES,
                result_schema_version=1,
            ),
            build_call_chain_handler(),
        ),
        (
            ToolDescriptor(
                name="read_code_slice",
                version="1.0",
                category="code",
                description="读取快照内受限源码片段（必须带行号范围与理由，防路径逃逸）。",
                input_schema={"type": "object", "properties": {"file_path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}, "reason": {"type": "string"}}},
                risk_level="sensitive_read",
                timeout_seconds=30,
                idempotent=True,
                retry_policy=None,
                allowed_modes=_ALL_MODES,
                result_schema_version=1,
            ),
            build_read_code_slice_handler(),
        ),
    ]
    for descriptor, handler in graph_tools:
        registry.register(descriptor, handler)

    registry.register(
        ToolDescriptor(
            name="run_deep_review",
            version="1.0",
            category="review",
            description=(
                "对受限代码证据执行深度审查：V3 必须绑定已授权漏洞假设、技能和证据条件；"
                "兼容路径才允许指定焦点。调用 LLM 生成带证据链与背景参考的 Observation 结论。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "focus": {"type": "string", "maxLength": 500},
                    "entrypoints": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                    "file_hints": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                    "hypothesis_id": {"type": "integer", "minimum": 1},
                    "skill_key": {"type": "string", "minLength": 1, "maxLength": 64},
                    "required_evidence": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1, "maxLength": 64},
                        "minItems": 1,
                        "maxItems": 8,
                    },
                    "context_budget_chars": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 20000,
                    },
                    "review_kind": {
                        "type": "string",
                        "enum": ["primary", "supplemental"],
                    },
                },
                "additionalProperties": False,
            },
            risk_level="sensitive_read",
            timeout_seconds=300,
            idempotent=True,
            produces_artifact_types=["agent_observation"],
            retry_policy=None,
            allowed_modes=_ALL_MODES,
            result_schema_version=1,
        ),
        build_run_deep_review_handler(),
    )
