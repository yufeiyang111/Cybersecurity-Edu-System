# -*- coding: utf-8 -*-
"""
LLM 信息抽取器（Knowledge Graph Extraction）

从文档文本块中抽取"实体-关系-实体"三元组：
- 主路径：MiniMax LLM 按本体输出 JSON 三元组（真实语义抽取）
- 兜底：LLM 不可用/超时/解析失败时降级为轻量正则抽取（保证流程不断）
- 支持批量并发调用与失败重试
"""
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests

from app.config import Config
from app.services.kg.ontology import build_ontology_prompt

logger = logging.getLogger(__name__)

# 额度耗尽/余额不足的错误信号（HTTP 状态码或响应体关键词）
_QUOTA_HTTP_CODES = (429, 402, 403)
_QUOTA_KEYWORDS = ("quota", "balance", "insufficient", "额度", "余额", "limit reached", "out of credits")


class QuotaExhaustedError(RuntimeError):
    """LLM 额度/余额耗尽，任务应暂停等待恢复（不降级正则）。"""


def _is_quota_error(resp: requests.Response) -> bool:
    if resp.status_code in _QUOTA_HTTP_CODES:
        return True
    body = ""
    try:
        body = (resp.text or "")[:2000].lower()
    except Exception:  # noqa: BLE001
        return False
    return any(kw in body for kw in _QUOTA_KEYWORDS)

EXTRACTION_SYSTEM_PROMPT = (
    "你是一名资深网络安全知识工程师，负责把安全技术文档转化为结构化知识图谱三元组。\n"
    + build_ontology_prompt()
    + "\n"
    "抽取规则：\n"
    "1. 只抽取文档中**明确出现且有实际含义**的实体，禁止臆造不在文本中的实体；\n"
    "2. 实体名称使用文本中的原文（可去掉多余修饰，保留核心技术名词）；\n"
    "3. 实体和关系都要落在给定类型内，无法归类时用 concept / related_to；\n"
    "4. 忽略纯格式性内容（导航、示例代码中的变量名、无意义的连接词）；\n"
    "5. 输出必须是合法的 JSON 数组，每个元素格式为：\n"
    '   {"source": "实体1", "source_type": "类型", "relation": "关系", "target": "实体2", "target_type": "类型", "confidence": 0.0-1.0}\n'
    "6. 只输出 JSON 数组本身，不要输出解释、markdown 代码块或多余文字。"
)

USER_TEMPLATE = "请从以下安全技术文档文本中抽取知识图谱三元组：\n\n{chunk_text}"


def _strip_code_fence(text: str) -> str:
    """去掉 LLM 常见的 markdown 代码块包裹。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    """从 LLM 输出中稳健解析 JSON 数组（支持围栏/前后缀噪声）。"""
    text = _strip_code_fence(text)
    # 直接解析
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    # 截取第一个 [ 到最后一个 ] 再解析（容忍前后解释文字）
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    return None


class LLMExtractor:
    """LLM 三元组抽取器（多 Provider 自动切换 + 正则降级）。

    Provider 顺序：主（MiniMax）→ fallback（备用，如 deepseek-v4-flash）。
    主 Provider 额度耗尽时自动切换到 fallback 继续抽取；
    所有 Provider 都额度耗尽时才抛 QuotaExhaustedError 暂停任务。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        fallback_api_key: Optional[str] = None,
        fallback_api_base: Optional[str] = None,
        fallback_model: Optional[str] = None,
        max_workers: int = 6,
        max_retries: int = 2,
        max_tokens: int = 16000,
    ) -> None:
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        # Provider 列表（按优先级）
        self.providers: List[Dict[str, str]] = []
        if api_key or Config.MINIMAX_API_KEY:
            self.providers.append({
                "name": "minimax",
                "api_key": api_key if api_key is not None else Config.MINIMAX_API_KEY,
                "api_base": api_base if api_base is not None else Config.MINIMAX_API_BASE,
                "model": model if model is not None else Config.MINIMAX_MODEL,
                "endpoint": "chatcompletion_v2",
            })
        fallback_key = fallback_api_key if fallback_api_key is not None else Config.KG_FALLBACK_API_KEY
        if fallback_key:
            self.providers.append({
                "name": "fallback",
                "api_key": fallback_key,
                "api_base": fallback_api_base if fallback_api_base is not None else Config.KG_FALLBACK_API_BASE,
                "model": fallback_model if fallback_model is not None else Config.KG_FALLBACK_MODEL,
                "endpoint": "chat/completions",
            })
        # token 用量统计（跨线程累计，按 provider 拆分）
        self.usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        self.usage_by_provider: Dict[str, Dict[str, int]] = {}
        self._usage_lock = threading.Lock()
        self._session = requests.Session()
        # 直连，绕过本机系统代理（Windows 系统代理会拦截 https 导致 ProxyError）
        self._session.trust_env = False
        self._call_lock = threading.Lock()

    # ------------------------------------------------------------------
    # 主路径：LLM 抽取
    # ------------------------------------------------------------------
    def _call_llm(self, chunk_text: str) -> Optional[str]:
        """按 Provider 优先级调用抽取三元组；全部额度耗尽抛 QuotaExhaustedError。"""
        last_quota_error: Optional[QuotaExhaustedError] = None
        for provider in self.providers:
            try:
                return self._call_provider(provider, chunk_text)
            except QuotaExhaustedError as exc:
                # 当前 Provider 额度耗尽：切换到下一个
                last_quota_error = exc
                logger.warning("Provider %s 额度耗尽，切换到备用 Provider", provider["name"])
        if last_quota_error is not None:
            raise last_quota_error
        return None

    def _call_provider(self, provider: Dict[str, str], chunk_text: str) -> Optional[str]:
        """调用单个 Provider 抽取三元组，返回原始文本；失败返回 None。"""
        if provider["endpoint"] == "chatcompletion_v2":
            url = f"{provider['api_base']}/text/chatcompletion_v2"
        else:
            url = f"{provider['api_base']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(chunk_text=chunk_text[:24000])},
            ],
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
        }
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.post(url, headers=headers, json=payload, timeout=180)
                if resp.status_code != 200:
                    # 额度耗尽：抛异常（由 _call_llm 决定切换 Provider 或暂停）
                    if _is_quota_error(resp):
                        raise QuotaExhaustedError(
                            f"LLM 额度耗尽（HTTP {resp.status_code}，provider={provider['name']}）"
                        )
                    logger.warning(
                        "LLM 抽取请求失败 provider=%s status=%d attempt=%d",
                        provider["name"], resp.status_code, attempt,
                    )
                    last_error = RuntimeError(f"status={resp.status_code}")
                    continue
                data = resp.json()
                # 记录 token 用量（跨线程安全）
                usage = data.get("usage") or {}
                with self._usage_lock:
                    self.usage["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                    self.usage["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                    provider_usage = self.usage_by_provider.setdefault(
                        provider["name"], {"prompt_tokens": 0, "completion_tokens": 0}
                    )
                    provider_usage["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                    provider_usage["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                choices = data.get("choices") or []
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                output = data.get("output")
                if isinstance(output, dict):
                    return output.get("text", "")
                if isinstance(output, str):
                    return output
                return None
            except QuotaExhaustedError:
                raise
            except (requests.RequestException, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "LLM 抽取请求异常 provider=%s type=%s attempt=%d",
                    provider["name"], type(exc).__name__, attempt,
                )
        if last_error is not None:
            logger.warning("LLM 抽取最终失败: %s", type(last_error).__name__)
        return None

    def extract_from_chunk(self, chunk_text: str) -> List[Dict[str, Any]]:
        """单块抽取：LLM 优先，解析失败/调用失败降级为正则。"""
        triples: List[Dict[str, Any]] = []
        used_llm = False
        if self.providers:
            raw = self._call_llm(chunk_text)
            if raw:
                parsed = _extract_json_array(raw)
                if parsed is not None:
                    triples = [t for t in parsed if isinstance(t, dict)]
                    used_llm = True
        if not triples:
            triples = self._regex_fallback(chunk_text)
        for triple in triples:
            triple["_source"] = "llm" if used_llm else "regex"
        return triples

    def extract_batch(self, chunks: List[str]) -> List[List[Dict[str, Any]]]:
        """批量并发抽取（保持输入顺序）。"""
        results: List[List[Dict[str, Any]]] = [None] * len(chunks)  # type: ignore[list-item]
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self.extract_from_chunk, chunk): idx for idx, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("抽取任务异常 chunk=%d err=%s", idx, type(exc).__name__)
                    results[idx] = []
        return results

    # ------------------------------------------------------------------
    # 兜底：轻量正则（保证流程不中断，非主路径）
    # ------------------------------------------------------------------
    def _regex_fallback(self, text: str) -> List[Dict[str, Any]]:
        """在 LLM 不可用时从文本中提取粗粒度三元组（词表匹配）。"""
        patterns = {
            "attack_technique": [
                r"SQL\s*注入|XSS|跨站脚本|CSRF|跨站请求伪造|SSRF|远程代码执行|RCE|文件上传|WebShell|反弹\s*Shell|暴力破解|钓鱼|嗅探|ARP欺骗|DNS劫持|中间人攻击|提权|权限维持|内网渗透|横向移动|信息收集|端口扫描|缓存投毒|点击劫持|SSRF|模板注入|反序列化|命令注入|路径遍历|目录穿越",
                r"缓冲区溢出|栈溢出|堆溢出|格式化字符串|空指针|越界访问|整型溢出|释放后使用|UAF",
            ],
            "vulnerability": [
                r"漏洞|注入漏洞|文件包含|代码执行|命令执行|路径遍历|信息泄露|配置错误|弱口令",
            ],
            "security_tool": [
                r"Nmap|Metasploit|Burp Suite|SQLMap|OWASP ZAP|Nessus|Acunetix|Wireshark|tcpdump|hydra|john|hashcat|mimikatz|sqlmap|nuclei",
            ],
            "defense_measure": [
                r"防火墙|入侵检测|入侵防御|WAF|VPN|堡垒机|安全审计|补丁|加固|最小权限|白名单|黑名单|双因素认证|MFA|加密传输|访问控制|日志监控",
            ],
            "concept": [
                r"TCP|IP|UDP|HTTP|HTTPS|DNS|DHCP|ARP|ICMP|SMTP|POP3|IMAP|TLS|SSL|加密|解密|哈希|签名|证书|公钥|私钥|对称加密|非对称加密|零信任|纵深防御",
            ],
        }
        triples: List[Dict[str, Any]] = []
        seen: set = set()
        found_entities: List[Dict[str, str]] = []
        for etype, pats in patterns.items():
            for pat in pats:
                for m in re.finditer(pat, text, re.IGNORECASE):
                    name = m.group(0).strip()
                    key = (etype, name.lower())
                    if key not in seen:
                        seen.add(key)
                        found_entities.append({"name": name, "type": etype})
        # 共现关系：同一块内实体两两相关（限制数量）
        for i in range(len(found_entities)):
            for j in range(i + 1, len(found_entities)):
                if len(triples) >= 30:
                    break
                a, b = found_entities[i], found_entities[j]
                triples.append({
                    "source": a["name"],
                    "source_type": a["type"],
                    "relation": "related_to",
                    "target": b["name"],
                    "target_type": b["type"],
                    "confidence": 0.5,
                })
        return triples


def get_llm_extractor() -> LLMExtractor:
    """获取 LLM 抽取器单例（配置来自 Config）。"""
    return LLMExtractor()
