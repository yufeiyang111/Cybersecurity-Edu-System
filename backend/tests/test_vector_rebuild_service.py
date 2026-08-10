# -*- coding: utf-8 -*-
"""向量索引重建任务服务测试：真实进度累加、量化报告、busy 互斥、失败兜底。"""
import time

import pytest

from app.services.vector_rebuild_service import VectorRebuildService


class _FakeEmbedding:
    def encode(self, texts):
        import numpy as np

        return np.zeros((len(texts), 4), dtype="float32")


class _FakeBackend:
    def __init__(self):
        self.deleted = []
        self.upserted = []

    def delete(self, *, where):
        self.deleted.append(where)

    def upsert(self, *, ids, vectors, texts, metadatas):
        self.upserted.append((ids, texts, metadatas))
        return len(ids)


class _FakeGraph:
    def __init__(self):
        self.calls = 0

    def add_entities_from_knowledge(self, items):
        self.calls += 1
        return len(items)


def _make_items(count: int = 5):
    return [
        {
            "id": i,
            "title": f"标题{i}",
            "content": "网络安全知识内容 " * 200,
            "category_name": "测试分类",
            "source": f"test-{i}.md",
            "difficulty": "medium",
        }
        for i in range(1, count + 1)
    ]


class _FakeEngine:
    def __init__(self, backend=None):
        self.vector_store = type("VS", (), {})()
        self.vector_store.backend = backend or _FakeBackend()
        self.vector_store.embedding_service = _FakeEmbedding()
        self.knowledge_graph = _FakeGraph()


def _build_service(monkeypatch, backend=None, items=None):
    import app.services.vector_rebuild_service as module

    engine = _FakeEngine(backend)
    monkeypatch.setattr(module, "get_rag_engine", lambda: engine)
    service = VectorRebuildService()
    monkeypatch.setattr(service, "_load_published_items", lambda: items or _make_items())

    class FakeApp:
        class _Ctx:
            def __enter__(self):
                return None

            def __exit__(self, *args):
                return False

        def app_context(self):
            return self._Ctx()

    monkeypatch.setattr(service, "_flask_app_factory", lambda: FakeApp())
    return service


def _wait_done(service):
    for _ in range(200):
        status = service.status()
        if status["status"] in ("success", "error"):
            return status
        time.sleep(0.05)
    return service.status()


def test_start_runs_and_reports_progress(monkeypatch):
    service = _build_service(monkeypatch)
    result = service.start(include_graph=False)
    assert result["started"] is True
    assert result["busy"] is False

    status = _wait_done(service)
    assert status["status"] == "success", status.get("message")
    assert status["total_docs"] == 5
    assert status["processed_docs"] == 5
    assert status["vector_count"] >= 5
    assert status["progress_percent"] == 100.0
    assert status["elapsed_seconds"] >= 0
    assert status["chunks_per_doc_max"] > 0
    assert status["chunks_per_doc_avg"] > 0
    assert status["failed_docs"] == []
    assert status["recent_processed"], "运行中应有最近处理列表"
    assert status["recent_processed"][-1]["doc_id"] == "5"


def test_progress_is_reported_during_run(monkeypatch):
    """运行期间 progress_percent 应随处理进度增长（真实进度，非一次性 100%）。"""

    class SlowBackend(_FakeBackend):
        def upsert(self, *, ids, vectors, texts, metadatas):
            time.sleep(0.05)
            return super().upsert(ids=ids, vectors=vectors, texts=texts, metadatas=metadatas)

    service = _build_service(monkeypatch, backend=SlowBackend(), items=_make_items(10))
    service.start(include_graph=False)
    time.sleep(0.2)
    mid = service.status()
    assert mid["status"] == "running"
    assert 0 < mid["progress_percent"] < 100, "运行中进度应处于 0-100 之间"
    assert mid["processed_docs"] > 0
    assert mid["vector_count"] > 0
    status = _wait_done(service)
    assert status["status"] == "success"
    assert status["progress_percent"] == 100.0


def test_busy_when_already_running(monkeypatch):
    service = _build_service(monkeypatch, items=_make_items(3))
    result = service.start(include_graph=False)
    assert result["started"] is True

    second = service.start(include_graph=False)
    assert second["started"] is False
    assert second["busy"] is True

    status = _wait_done(service)
    assert status["status"] == "success"


def test_failed_doc_recorded_but_task_completes(monkeypatch):
    """单个文档处理失败时记录失败明细，任务仍能成功完成。"""

    class FlakyBackend(_FakeBackend):
        def __init__(self):
            super().__init__()
            self.fail_once = True

        def upsert(self, *, ids, vectors, texts, metadatas):
            if self.fail_once:
                self.fail_once = False
                raise RuntimeError("mock upsert 失败")
            return super().upsert(ids=ids, vectors=vectors, texts=texts, metadatas=metadatas)

    service = _build_service(monkeypatch, backend=FlakyBackend())
    service.start(include_graph=False)
    status = _wait_done(service)
    assert status["status"] == "success"
    assert len(status["failed_docs"]) == 1
    assert status["failed_docs"][0]["id"] == "1"
    assert "mock upsert" in status["failed_docs"][0]["error"]
    assert status["processed_docs"] == 5


def test_include_graph_reports_graph_counts(monkeypatch):
    import app.services.vector_rebuild_service as module

    service = _build_service(monkeypatch, items=_make_items(2))
    monkeypatch.setattr(service, "_graph_builder", lambda: lambda items: {"nodes_added": 42, "edges_added": 7})
    service.start(include_graph=True)
    status = _wait_done(service)
    assert status["status"] == "success"
    assert status["graph_nodes"] == 42
    assert status["graph_edges"] == 7
