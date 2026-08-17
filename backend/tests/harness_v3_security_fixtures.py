# -*- coding: utf-8 -*-
"""Harness V3 已知漏洞与安全对照的固定源码夹具。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnownSecurityCase:
    """一组同类风险的漏洞/安全源码对照，不包含任何真实项目代码。"""

    key: str
    title: str
    skill_key: str
    file_path: str
    rule_id: str
    category: str
    cwe_id: str
    message: str
    control_evidence_key: str
    sink_role: str
    vulnerable_source: str
    safe_source: str


KNOWN_SECURITY_CASES: tuple[KnownSecurityCase, ...] = (
    KnownSecurityCase(
        key="sql_injection",
        title="SQL 注入",
        skill_key="injection_dataflow",
        file_path="app/sql_lookup.py",
        rule_id="python.sql-injection",
        category="sast",
        cwe_id="CWE-89",
        message="SQL query concatenates untrusted value without parameter binding.",
        control_evidence_key="parameterization_or_absence",
        sink_role="sink",
        vulnerable_source=(
            "from flask import request\n"
            "\n"
            "def lookup_user(db):\n"
            "    user_id = request.args['id']  # MATRIX_SOURCE\n"
            "    return db.execute(f'SELECT * FROM users WHERE id = {user_id}')  # MATRIX_SINK\n"
        ),
        safe_source=(
            "from flask import abort, request\n"
            "\n"
            "def lookup_user(db):\n"
            "    user_id = request.args['id']  # MATRIX_SOURCE\n"
            "    if not user_id.isdigit():  # MATRIX_GUARD\n"
            "        abort(400)\n"
            "    return db.execute('SELECT * FROM users WHERE id = ?', (user_id,))  # MATRIX_SINK\n"
        ),
    ),
    KnownSecurityCase(
        key="idor_authorization",
        title="对象越权（IDOR）",
        skill_key="authorization_boundary",
        file_path="app/invoices.py",
        rule_id="python.authorization.idor",
        category="sast",
        cwe_id="CWE-639",
        message="Object access does not bind the invoice owner to the current subject.",
        control_evidence_key="authorization_guard",
        sink_role="object",
        vulnerable_source=(
            "from flask_login import current_user\n"
            "\n"
            "def get_invoice(invoice_id):\n"
            "    actor_id = current_user.id  # MATRIX_SOURCE\n"
            "    return Invoice.query.get(invoice_id)  # MATRIX_SINK\n"
        ),
        safe_source=(
            "from flask import abort\n"
            "from flask_login import current_user\n"
            "\n"
            "def get_invoice(invoice_id):\n"
            "    actor_id = current_user.id  # MATRIX_SOURCE\n"
            "    invoice = Invoice.query.get(invoice_id)  # MATRIX_SINK\n"
            "    if invoice is None or invoice.owner_id != actor_id:  # MATRIX_GUARD\n"
            "        abort(404)\n"
            "    return invoice\n"
        ),
    ),
    KnownSecurityCase(
        key="ssrf",
        title="服务端请求伪造（SSRF）",
        skill_key="untrusted_file_network",
        file_path="app/fetch.py",
        rule_id="python.ssrf.request",
        category="sast",
        cwe_id="CWE-918",
        message="User controlled URL reaches a network request without an internal-address block.",
        control_evidence_key="allowlist_or_absence",
        sink_role="sink",
        vulnerable_source=(
            "from flask import request\n"
            "import requests\n"
            "\n"
            "def fetch_preview():\n"
            "    target_url = request.args['url']  # MATRIX_SOURCE\n"
            "    return requests.get(target_url, timeout=2)  # MATRIX_SINK\n"
        ),
        safe_source=(
            "from flask import abort, request\n"
            "import requests\n"
            "\n"
            "def fetch_preview():\n"
            "    target_url = request.args['url']  # MATRIX_SOURCE\n"
            "    if not is_public_allowlisted_url(target_url):  # MATRIX_GUARD\n"
            "        abort(400)\n"
            "    return requests.get(target_url, timeout=2)  # MATRIX_SINK\n"
        ),
    ),
    KnownSecurityCase(
        key="path_traversal",
        title="路径穿越",
        skill_key="untrusted_file_network",
        file_path="app/downloads.py",
        rule_id="python.path-traversal",
        category="sast",
        cwe_id="CWE-22",
        message="Untrusted file path is resolved outside the allowed download root.",
        control_evidence_key="allowlist_or_absence",
        sink_role="sink",
        vulnerable_source=(
            "from flask import request\n"
            "\n"
            "def read_download(download_root):\n"
            "    relative_path = request.args['path']  # MATRIX_SOURCE\n"
            "    return (download_root / relative_path).read_text()  # MATRIX_SINK\n"
        ),
        safe_source=(
            "from flask import abort, request\n"
            "\n"
            "def read_download(download_root):\n"
            "    relative_path = request.args['path']  # MATRIX_SOURCE\n"
            "    candidate = (download_root / relative_path).resolve()\n"
            "    if download_root not in candidate.parents:  # MATRIX_GUARD\n"
            "        abort(404)\n"
            "    return candidate.read_text()  # MATRIX_SINK\n"
        ),
    ),
    KnownSecurityCase(
        key="unsafe_dynamic_execution",
        title="不安全动态执行",
        skill_key="unsafe_execution_deserialization",
        file_path="app/evaluator.py",
        rule_id="python.eval",
        category="sast",
        cwe_id="CWE-94",
        message="Untrusted expression reaches eval without a strict allowlist.",
        control_evidence_key="guard_or_absence",
        sink_role="sink",
        vulnerable_source=(
            "from flask import request\n"
            "\n"
            "def evaluate_expression():\n"
            "    expression = request.args['expression']  # MATRIX_SOURCE\n"
            "    return eval(expression)  # MATRIX_SINK\n"
        ),
        safe_source=(
            "from flask import abort, request\n"
            "\n"
            "def evaluate_expression():\n"
            "    expression = request.args['expression']  # MATRIX_SOURCE\n"
            "    if expression not in SAFE_EXPRESSIONS:  # MATRIX_GUARD\n"
            "        abort(400)\n"
            "    return SAFE_EXPRESSIONS[expression]  # MATRIX_SINK\n"
        ),
    ),
    KnownSecurityCase(
        key="unsafe_deserialization",
        title="不安全反序列化",
        skill_key="unsafe_execution_deserialization",
        file_path="app/imports.py",
        rule_id="python.yaml-load",
        category="sast",
        cwe_id="CWE-502",
        message="Unsafe YAML deserialize processes an untrusted payload.",
        control_evidence_key="guard_or_absence",
        sink_role="sink",
        vulnerable_source=(
            "from flask import request\n"
            "import yaml\n"
            "\n"
            "def parse_import():\n"
            "    payload = request.data  # MATRIX_SOURCE\n"
            "    return yaml.load(payload, Loader=yaml.Loader)  # MATRIX_SINK\n"
        ),
        safe_source=(
            "from flask import request\n"
            "import yaml\n"
            "\n"
            "def parse_import():\n"
            "    payload = request.data  # MATRIX_SOURCE\n"
            "    return yaml.safe_load(payload)  # MATRIX_SINK MATRIX_GUARD\n"
        ),
    ),
)


def marker_line(source: str, marker: str) -> int:
    """返回唯一标记所在行，避免夹具行号和源码内容脱节。"""
    matches = [
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if marker in line
    ]
    if len(matches) != 1:
        raise ValueError(f"夹具标记 {marker} 必须恰好出现一次")
    return matches[0]