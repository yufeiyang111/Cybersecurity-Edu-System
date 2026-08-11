# -*- coding: utf-8 -*-
"""
知识图谱本体定义（Ontology）

参考 MITRE ATT&CK 与安全运营/教育场景，定义实体类型与关系类型。
LLM 抽取器按此本体约束输出 JSON 三元组，保证图谱结构一致。
"""

# ------------------------------------------------------------------
# 实体类型（节点）
# ------------------------------------------------------------------
ENTITY_TYPES = {
    "vulnerability": "漏洞",
    "attack_technique": "攻击技术",
    "defense_measure": "防御措施",
    "security_tool": "安全工具",
    "concept": "概念",
    "regulation": "法规标准",
    "threat_actor": "威胁行为体",
}

ENTITY_TYPE_LABELS = {
    "vulnerability": "漏洞",
    "attack_technique": "攻击技术",
    "defense_measure": "防御措施",
    "security_tool": "安全工具",
    "concept": "概念",
    "regulation": "法规标准",
    "threat_actor": "威胁行为体",
}

# ------------------------------------------------------------------
# 关系类型（边）
# ------------------------------------------------------------------
RELATION_TYPES = {
    "exploits": "利用（漏洞 → 攻击技术）",
    "mitigates": "缓解（防御措施 → 攻击技术）",
    "detects": "检测（工具 → 漏洞/攻击技术）",
    "uses": "使用（攻击技术 → 工具）",
    "prerequisite": "前置知识（概念 → 概念）",
    "causes": "导致（攻击技术 → 漏洞/后果）",
    "belongs_to": "属于（实体 → 更宏观实体）",
    "related_to": "相关（通用）",
}

# 关系允许的（source_type → target_type）组合提示（供 prompt 使用，不强制校验）
RELATION_SOURCE_TARGET_HINTS = {
    "exploits": ("vulnerability", "attack_technique"),
    "mitigates": ("defense_measure", "attack_technique"),
    "detects": ("security_tool", ("vulnerability", "attack_technique")),
    "uses": ("attack_technique", "security_tool"),
    "prerequisite": ("concept", "concept"),
    "causes": ("attack_technique", ("vulnerability", "concept")),
    "belongs_to": (None, None),
    "related_to": (None, None),
}

# 系统内部关系（非 LLM 输出，入库时附加）
INTERNAL_RELATION_TYPES = {"contains": "包含（知识条目 → 实体）"}

ALL_RELATION_TYPES = {**RELATION_TYPES, **INTERNAL_RELATION_TYPES}


def entity_type_label(entity_type: str) -> str:
    """实体类型中文标签（未知类型归为概念）。"""
    return ENTITY_TYPE_LABELS.get(entity_type, ENTITY_TYPE_LABELS["concept"])


def build_ontology_prompt() -> str:
    """生成本体说明文本，嵌入 LLM 抽取提示词。"""
    entity_lines = "、".join(f"{key}（{label}）" for key, label in ENTITY_TYPES.items())
    relation_lines = "；".join(f"{key}（{label}）" for key, label in RELATION_TYPES.items())
    return (
        "实体类型仅限以下 7 类：\n"
        f"  {entity_lines}\n"
        "关系类型仅限以下 8 类（关系方向见说明）：\n"
        f"  {relation_lines}\n"
        "常见关系方向约定：漏洞→攻击技术用 exploits；防御措施→攻击技术用 mitigates；"
        "工具→漏洞/攻击技术用 detects；攻击技术→工具用 uses；概念→概念用 prerequisite；"
        "攻击技术→漏洞/后果用 causes；不确定时一律用 related_to。"
    )
