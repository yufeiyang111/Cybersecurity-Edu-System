# -*- coding: utf-8 -*-
"""Offline CLI for comparing sanitized legacy and V2 RAG evaluation reports."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.rag_core.release_gate import (
    ReleaseGateVerifier,
    release_gate_exit_code,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPORT_NAME = re.compile(r"rag_report_[A-Za-z0-9_-]+\.json")
_OUTPUT_NAME = re.compile(r"rag_release_gate_[A-Za-z0-9_-]+\.json")


def build_argument_parser() -> argparse.ArgumentParser:
    """Build a parser that accepts only local sanitized report names."""
    parser = argparse.ArgumentParser(description="Compare offline RAG evaluation reports")
    parser.add_argument("--legacy-report", required=True)
    parser.add_argument("--v2-report", required=True)
    parser.add_argument("--output-name", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser


def run_release_gate(
    *,
    legacy_report_name: str,
    v2_report_name: str,
    output_name: str | None = None,
    write_output: bool = True,
) -> tuple[dict[str, Any], int]:
    """Load two approved local report paths and return a sanitized decision only."""
    legacy_report = load_report(legacy_report_name)
    v2_report = load_report(v2_report_name)
    result = ReleaseGateVerifier().verify(
        legacy_report=legacy_report,
        v2_report=v2_report,
    )
    payload = result.to_dict(epsilon=1e-9)
    if write_output:
        normalized_output_name = _normalized_output_name(output_name)
        write_result(payload, normalized_output_name)
        payload["result_file"] = normalized_output_name
    return payload, release_gate_exit_code(result)


def load_report(report_name: str) -> dict[str, Any]:
    """Read one JSON object from the backend root without following supplied paths."""
    path = _safe_path(report_name, _REPORT_NAME, "report")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("unable to read sanitized report") from error
    if not isinstance(payload, dict):
        raise ValueError("report must be a JSON object")
    return payload


def write_result(payload: dict[str, Any], output_name: str) -> str:
    """Persist only the sanitized gate result under an ignored backend-root name."""
    path = _safe_path(output_name, _OUTPUT_NAME, "output")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return output_name


def _normalized_output_name(value: str | None) -> str:
    if value is not None:
        _safe_path(value, _OUTPUT_NAME, "output")
        return value
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"rag_release_gate_{timestamp}.json"


def _safe_path(value: str, pattern: re.Pattern[str], label: str) -> Path:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"invalid {label} file name")
    path = (BACKEND_ROOT / value).resolve()
    if path.parent != BACKEND_ROOT.resolve():
        raise ValueError(f"invalid {label} file name")
    return path


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    try:
        payload, exit_code = run_release_gate(
            legacy_report_name=args.legacy_report,
            v2_report_name=args.v2_report,
            output_name=args.output_name,
            write_output=not args.no_write,
        )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
