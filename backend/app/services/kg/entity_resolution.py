# -*- coding: utf-8 -*-
"""
实体消歧与知识融合（Entity Resolution & Fusion）

把 LLM 抽取出的原始三元组清洗为统一图谱：
- 名称规范化（去空白/全半角/括号变体）
- 同义名称合并（embedding 语义相似度 + 编辑距离兜底）
- 关系去重与置信度聚合
- 输出 canonical 名称映射，供入库使用全局共享实体 id
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.kg.ontology import ENTITY_TYPES, entity_type_label

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.88
EDIT_DISTANCE_THRESHOLD = 2

# 常见同义/缩写映射（安全领域高频别名）
SYNONYM_MAP = {
    "sqli": "SQL注入",
    "sql injection": "SQL注入",
    "xss": "XSS",
    "cross-site scripting": "XSS",
    "跨站脚本攻击": "XSS",
    "csrf": "CSRF",
    "cross-site request forgery": "CSRF",
    "跨站请求伪造": "CSRF",
    "ssrf": "SSRF",
    "server-side request forgery": "SSRF",
    "服务端请求伪造": "SSRF",
    "rce": "远程代码执行",
    "remote code execution": "远程代码执行",
    "lfi": "本地文件包含",
    "local file inclusion": "本地文件包含",
    "rfi": "远程文件包含",
    "remote file inclusion": "远程文件包含",
    "uaf": "释放后使用",
    "use-after-free": "释放后使用",
    "pt": "路径遍历",
    "path traversal": "路径遍历",
    "id": "身份标识",
    "im": "即时通讯",
    "ldap": "LDAP",
    "smb": "SMB",
    "ntlm": "NTLM",
    "kerberos": "Kerberos",
    "privesc": "权限提升",
    "privilege escalation": "权限提升",
    "lateral movement": "横向移动",
    "recon": "信息收集",
    "reconnaissance": "信息收集",
    "osint": "开源情报",
    "waf": "WAF",
    "web application firewall": "WAF",
    "ids": "入侵检测系统",
    "ips": "入侵防御系统",
    "2fa": "双因素认证",
    "mfa": "多因素认证",
    "zero-day": "零日漏洞",
    "0day": "零日漏洞",
    "webshell": "WebShell",
    "c2": "命令与控制",
    "command and control": "命令与控制",
    "cve": "CVE漏洞",
}


def normalize_name(name: str) -> str:
    """名称规范化：去空白、统一全半角、去多余括号注释。"""
    if not name:
        return ""
    text = name.strip()
    # 全角转半角
    text = text.translate(str.maketrans("，。；：（）【】", ",.;:()[]"))
    # 压缩空白
    text = re.sub(r"\s+", " ", text)
    # 去掉括号内的冗余补充（保留主体名）
    text = re.sub(r"\s*[\(\[][^)\]]*[\)\]]\s*$", "", text).strip()
    return text


def canonicalize(name: str, entity_type: str) -> str:
    """同义词归一：小写查询同义词表，命中返回规范名。"""
    key = name.strip().lower()
    return SYNONYM_MAP.get(key, name)


def _levenshtein(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > EDIT_DISTANCE_THRESHOLD:
        return EDIT_DISTANCE_THRESHOLD + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def _same_name_close(a: str, b: str) -> bool:
    """名称是否算"同一个实体"：仅当名称足够长（>=4 字符）且编辑距离相对小。

    短名称（如 A/B、SQL 与 XSS）不做编辑距离合并，避免误合并。
    阈值随长度缩放：len>=8 允许 2，len>=4 允许 1。
    """
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    min_len = min(len(a), len(b))
    if min_len < 4:
        return False
    max_dist = 2 if min_len >= 8 else 1
    return _levenshtein(a, b) <= max_dist


class EntityResolver:
    """实体消歧：把原始实体名映射到全局 canonical 名。"""

    def __init__(self, embedding_service: Optional[Any] = None, threshold: float = SIMILARITY_THRESHOLD):
        self.embedding_service = embedding_service
        self.threshold = threshold
        # canonical -> {"type": str, "aliases": [str], "count": int}
        self._entities: Dict[str, Dict[str, Any]] = {}
        # (type, normalized_name) -> canonical
        self._lookup: Dict[Tuple[str, str], str] = {}
        self._embeddings: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    def add_triples(self, triples: List[Dict[str, Any]]) -> None:
        """注册一批三元组中的实体，返回时通过 canonical_name 查询。"""
        for triple in triples:
            for side in ("source", "target"):
                name = (triple.get(side) or "").strip()
                etype = triple.get(f"{side}_type") or "concept"
                if not name or etype not in ENTITY_TYPES:
                    continue
                self._register(name, etype)

    def _register(self, name: str, entity_type: str) -> None:
        norm = normalize_name(name)
        canon = canonicalize(norm, entity_type)
        key = (entity_type, norm.lower())
        existing = self._lookup.get(key)
        if existing:
            self._entities[existing]["count"] += 1
            if norm not in self._entities[existing]["aliases"]:
                self._entities[existing]["aliases"].append(norm)
            return
        # 同义词映射到的规范名已是实体 → 合并到它（如 SQLi → 已有 SQL注入）
        canon_key = (entity_type, canon.lower())
        canon_existing = self._lookup.get(canon_key)
        if canon_existing:
            self._lookup[key] = canon_existing
            self._entities[canon_existing]["count"] += 1
            if norm not in self._entities[canon_existing]["aliases"]:
                self._entities[canon_existing]["aliases"].append(norm)
            return
        # 尝试合并到已有实体（embedding 相似度 / 编辑距离）
        merged = self._match_existing(norm, entity_type)
        if merged:
            self._lookup[key] = merged
            self._entities[merged]["count"] += 1
            if norm not in self._entities[merged]["aliases"]:
                self._entities[merged]["aliases"].append(norm)
            return
        # 新建实体（优先保留规范名）
        self._entities[canon] = {
            "type": entity_type,
            "aliases": [norm],
            "count": 1,
        }
        self._lookup[key] = canon
        # 同义词规范名与实体名不同时，也登记规范名 lookup，方便后续合并
        if canon.lower() != norm.lower():
            self._lookup.setdefault(canon_key, canon)

    def _match_existing(self, norm: str, entity_type: str) -> Optional[str]:
        """与已有实体匹配：同类型内编辑距离 / embedding 相似度。"""
        for canon, info in self._entities.items():
            if info["type"] != entity_type:
                continue
            for alias in info["aliases"]:
                if _same_name_close(norm, alias):
                    return canon
        # embedding 语义相似（同类型、候选数量大时跳过避免 O(n²)）
        if self.embedding_service is not None and not getattr(self.embedding_service, "is_degraded", True):
            if len(self._entities) > 200:
                return None
            vec = self._embed(norm)
            if vec is None:
                return None
            best: Tuple[float, str] = (0.0, "")
            for canon, info in self._entities.items():
                if info["type"] != entity_type:
                    continue
                other = self._embed(info["aliases"][0])
                if other is None:
                    continue
                sim = _cosine(vec, other)
                if sim > best[0]:
                    best = (sim, canon)
            if best[0] >= self.threshold:
                return best[1]
        return None

    def _embed(self, text: str) -> Optional[Any]:
        if text in self._embeddings:
            return self._embeddings[text]
        try:
            vec = self.embedding_service.encode_query([text])[0]
            self._embeddings[text] = vec
            return vec
        except Exception as exc:  # noqa: BLE001
            logger.warning("实体 embedding 失败: %s", type(exc).__name__)
            return None

    # ------------------------------------------------------------------
    def canonical_name(self, name: str, entity_type: str) -> str:
        """查询原始名称的 canonical 名（未注册时原样返回）。"""
        norm = normalize_name(name)
        return self._lookup.get((entity_type, norm.lower()), norm)

    def entities(self) -> Dict[str, Dict[str, Any]]:
        """全部 canonical 实体（含类型/别名/引用计数）。"""
        return dict(self._entities)

    def entity_type(self, canon: str) -> str:
        return self._entities.get(canon, {}).get("type", "concept")

    def labels(self) -> Dict[str, str]:
        """实体名 -> 中文类型标签（供入库/展示）。"""
        return {c: entity_type_label(info["type"]) for c, info in self._entities.items()}


def _cosine(a, b) -> float:
    import numpy as np

    va = np.asarray(a, dtype="float32").flatten()
    vb = np.asarray(b, dtype="float32").flatten()
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def resolve_triples(
    triples: List[Dict[str, Any]],
    embedding_service: Optional[Any] = None,
) -> Tuple[List[Dict[str, Any]], EntityResolver]:
    """清洗三元组：返回 canonical 化后的三元组列表与解析器（含实体表）。"""
    resolver = EntityResolver(embedding_service=embedding_service)
    resolver.add_triples(triples)
    cleaned: List[Dict[str, Any]] = []
    seen: set = set()
    for t in triples:
        source = (t.get("source") or "").strip()
        target = (t.get("target") or "").strip()
        relation = (t.get("relation") or "related_to").strip()
        stype = t.get("source_type") or "concept"
        ttype = t.get("target_type") or "concept"
        if not source or not target or source == target:
            continue
        src_canon = resolver.canonical_name(source, stype)
        tgt_canon = resolver.canonical_name(target, ttype)
        if src_canon == tgt_canon:
            continue
        key = (src_canon, relation, tgt_canon)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({
            "source": src_canon,
            "source_type": resolver.entity_type(src_canon),
            "relation": relation,
            "target": tgt_canon,
            "target_type": resolver.entity_type(tgt_canon),
            "confidence": float(t.get("confidence") or 0.8),
            "_source": t.get("_source", "llm"),
        })
    return cleaned, resolver
