"""Regression tests for the services package import boundary."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_services_package_does_not_eager_import_optional_ai_modules() -> None:
    """轻量服务包入口不应在导入时加载可选 AI 和图谱实现。"""
    probe = """
import json
import sys
import app.services
modules = {
    'enhanced_rag_engine': 'app.services.enhanced_rag_engine' in sys.modules,
    'vector_store': 'app.services.vector_store' in sys.modules,
    'neo4j_graph': 'app.services.neo4j_graph' in sys.modules,
    'secbert_embedding': 'app.services.secbert_embedding' in sys.modules,
}
print(json.dumps(modules))
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=BACKEND_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert result.stdout.strip() == '{"enhanced_rag_engine": false, "vector_store": false, "neo4j_graph": false, "secbert_embedding": false}'
