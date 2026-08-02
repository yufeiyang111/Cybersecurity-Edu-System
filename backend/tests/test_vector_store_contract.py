"""VectorStore 协议契约测试：Qdrant/Chroma 双后端 + legacy 兼容层 + 工厂。"""
from __future__ import annotations

import socket
import uuid

import numpy as np
import pytest

from app.services.vector_stores.contracts import VectorHit, to_2d_list
from app.services.vector_stores.factory import create_vector_backend, get_vector_backend, get_vector_store
from app.services.vector_stores.legacy import VectorStore


# ---------------------------------------------------------------------------
# to_2d_list 形状归一化
# ---------------------------------------------------------------------------


def test_to_2d_list_normalizes_all_shapes():
    assert to_2d_list(np.zeros(4)) == [[0.0, 0.0, 0.0, 0.0]]
    assert to_2d_list(np.zeros((1, 4))) == [[0.0, 0.0, 0.0, 0.0]]
    assert to_2d_list(np.zeros((2, 4)))[0] == [0.0, 0.0, 0.0, 0.0]
    assert to_2d_list(np.zeros((1, 1, 4)))[0] == [0.0, 0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# Qdrant 后端（本地持久化模式）
# ---------------------------------------------------------------------------


@pytest.fixture
def qdrant_backend(tmp_path):
    from app.services.vector_stores.qdrant import QdrantVectorBackend

    backend = QdrantVectorBackend(
        collection_name=f"test_kb_{uuid.uuid4().hex[:8]}",
        path=str(tmp_path / "qdrant"),
        dimension=4,
    )
    yield backend
    backend.delete_all()


def _vector(*values):
    return [float(value) for value in values]


def test_qdrant_roundtrip_preserves_string_ids_and_text(qdrant_backend):
    backend = qdrant_backend
    written = backend.upsert(
        ids=["doc-a", "doc-b"],
        vectors=[_vector(1, 0, 0, 0), _vector(0, 1, 0, 0)],
        texts=["sql injection guidance", "password policy"],
        metadatas=[{"workspace_id": 1}, {"workspace_id": 2}],
    )
    assert written == 2
    assert backend.count() == 2

    hits = backend.search(vector=_vector(1, 0, 0, 0), where=None, top_k=5)
    assert [hit.id for hit in hits] == ["doc-a", "doc-b"]
    assert hits[0].text == "sql injection guidance"
    assert hits[0].metadata["workspace_id"] == 1
    assert hits[0].similarity == pytest.approx(1.0, abs=1e-6)


def test_qdrant_upsert_is_idempotent_and_int_vectors_work(qdrant_backend):
    backend = qdrant_backend
    backend.upsert(
        ids=["doc-a"],
        vectors=[[1, 0, 0, 0]],
        texts=["first"],
        metadatas=[{"workspace_id": 1}],
    )
    backend.upsert(
        ids=["doc-a"],
        vectors=[[1, 0, 0, 0]],
        texts=["second"],
        metadatas=[{"workspace_id": 1}],
    )
    assert backend.count() == 1
    hits = backend.search(vector=_vector(1, 0, 0, 0), where=None, top_k=5)
    assert hits[0].text == "second"


def test_qdrant_search_respects_metadata_filter(qdrant_backend):
    backend = qdrant_backend
    backend.upsert(
        ids=["doc-1", "doc-2"],
        vectors=[_vector(1, 0, 0, 0), _vector(1, 0, 0, 0)],
        texts=["one", "two"],
        metadatas=[{"workspace_id": 1, "kind": "a"}, {"workspace_id": 2, "kind": "b"}],
    )
    hits = backend.search(
        vector=_vector(1, 0, 0, 0),
        where={"workspace_id": 1},
        top_k=5,
    )
    assert [hit.id for hit in hits] == ["doc-1"]
    hits = backend.search(
        vector=_vector(1, 0, 0, 0),
        where={"kind": "b"},
        top_k=5,
    )
    assert [hit.id for hit in hits] == ["doc-2"]


def test_qdrant_delete_by_where_and_by_ids(qdrant_backend):
    backend = qdrant_backend
    backend.upsert(
        ids=["doc-1", "doc-2", "doc-3"],
        vectors=[_vector(1, 0, 0, 0)] * 3,
        texts=["one", "two", "three"],
        metadatas=[{"workspace_id": 1}, {"workspace_id": 2}, {"workspace_id": 2}],
    )
    backend.delete(where={"workspace_id": 1})
    assert backend.count() == 2
    backend.delete_by_ids(ids=["doc-2"])
    assert backend.count() == 1
    assert backend.search(vector=_vector(1, 0, 0, 0), where=None, top_k=5)[0].id == "doc-3"


def test_qdrant_delete_all_recreates_empty_collection(qdrant_backend):
    backend = qdrant_backend
    backend.upsert(
        ids=["doc-1"],
        vectors=[_vector(1, 0, 0, 0)],
        texts=["one"],
        metadatas=[{"workspace_id": 1}],
    )
    assert backend.delete_all() is True
    assert backend.count() == 0
    backend.upsert(
        ids=["doc-2"],
        vectors=[_vector(0, 1, 0, 0)],
        texts=["two"],
        metadatas=[{"workspace_id": 2}],
    )
    assert backend.count() == 1


# ---------------------------------------------------------------------------
# Qdrant 后端（server 模式，本机已部署 6333；CI 无 server 时自动跳过）
# ---------------------------------------------------------------------------


def _qdrant_server_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 6333), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _qdrant_server_available(), reason="本机 Qdrant server 未运行")
def test_qdrant_server_mode_roundtrip_and_cleanup():
    from app.services.vector_stores.qdrant import QdrantVectorBackend

    backend = QdrantVectorBackend(
        collection_name=f"test_server_{uuid.uuid4().hex[:8]}",
        url="http://127.0.0.1:6333",
        dimension=4,
    )
    try:
        backend.upsert(
            ids=["server-doc"],
            vectors=[_vector(1, 0, 0, 0)],
            texts=["server content"],
            metadatas=[{"workspace_id": 7}],
        )
        assert backend.count() == 1
        hits = backend.search(
            vector=_vector(1, 0, 0, 0),
            where={"workspace_id": 7},
            top_k=5,
        )
        assert hits[0].id == "server-doc"
        assert hits[0].similarity == pytest.approx(1.0, abs=1e-6)
    finally:
        backend.delete_all()
        backend._client.delete_collection(collection_name=backend.collection_name)


# ---------------------------------------------------------------------------
# Chroma 后端（本地持久化模式）
# ---------------------------------------------------------------------------


@pytest.fixture
def chroma_backend(tmp_path):
    pytest.importorskip("chromadb")
    from app.services.vector_stores.chroma import ChromaVectorBackend

    backend = ChromaVectorBackend(
        collection_name=f"test_kb_{uuid.uuid4().hex[:8]}",
        persist_directory=str(tmp_path / "chroma"),
    )
    yield backend
    backend.delete_all()


def test_chroma_roundtrip_filter_and_delete(chroma_backend):
    backend = chroma_backend
    backend.upsert(
        ids=["doc-1", "doc-2"],
        vectors=[_vector(1, 0, 0, 0), _vector(0, 1, 0, 0)],
        texts=["alpha", "beta"],
        metadatas=[{"workspace_id": 1}, {"workspace_id": 2}],
    )
    assert backend.count() == 2
    hits = backend.search(vector=_vector(1, 0, 0, 0), where=None, top_k=5)
    assert hits[0].id == "doc-1"
    assert hits[0].similarity == pytest.approx(1.0, abs=1e-6)
    hits = backend.search(vector=_vector(1, 0, 0, 0), where={"workspace_id": 2}, top_k=5)
    assert [hit.id for hit in hits] == ["doc-2"]
    hits = backend.search(vector=_vector(1, 0, 0, 0), where={"workspace_id": 999}, top_k=5)
    assert hits == []
    backend.delete_by_ids(ids=["doc-1"])
    assert backend.count() == 1
    backend.delete(where={"workspace_id": 2})
    assert backend.count() == 0


def test_chroma_delete_all_recreates_empty_collection(chroma_backend):
    backend = chroma_backend
    backend.upsert(
        ids=["doc-1"],
        vectors=[_vector(1, 0, 0, 0)],
        texts=["one"],
        metadatas=[{"workspace_id": 1}],
    )
    assert backend.delete_all() is True
    assert backend.count() == 0


# ---------------------------------------------------------------------------
# legacy VectorStore 兼容层（注入 FakeBackend，不碰真实 SDK / 模型）
# ---------------------------------------------------------------------------


class _FakeEmbedding:
    def encode(self, text):
        return np.zeros((1, 4))

    def encode_query(self, query):
        return np.zeros(4)


class _FakeBackend:
    def __init__(self):
        self.upsert_calls = []
        self.search_calls = []
        self.delete_calls = []
        self.delete_by_ids_calls = []
        self.delete_all_calls = 0
        self.hits: list[VectorHit] = []
        self.count_value = 3

    def upsert(self, *, ids, vectors, texts, metadatas):
        self.upsert_calls.append((ids, vectors, texts, metadatas))
        return len(ids)

    def search(self, *, vector, where, top_k):
        self.search_calls.append((vector, where, top_k))
        return self.hits

    def delete(self, *, where):
        self.delete_calls.append(where)

    def delete_by_ids(self, *, ids):
        self.delete_by_ids_calls.append(ids)

    def delete_all(self):
        self.delete_all_calls += 1
        return True

    def count(self):
        return self.count_value


@pytest.fixture
def legacy_store(monkeypatch):
    fake = _FakeEmbedding()
    monkeypatch.setattr("app.services.vector_stores.legacy.get_embedding_service", lambda: fake)
    return VectorStore(backend=_FakeBackend())


def test_legacy_add_document_translates_to_backend_upsert(legacy_store):
    fake = legacy_store.backend
    assert legacy_store.add_document("doc-1", "some text", {"title": "t"}) is True
    ids, vectors, texts, metadatas = fake.upsert_calls[0]
    assert ids == ["doc-1"]
    assert vectors == [[0.0, 0.0, 0.0, 0.0]]
    assert texts == ["some text"]
    assert metadatas == [{"title": "t"}]


def test_legacy_add_document_returns_false_on_backend_failure(monkeypatch):
    class _BrokenBackend:
        def upsert(self, **kwargs):
            raise RuntimeError("backend down")

    fake = _FakeEmbedding()
    monkeypatch.setattr("app.services.vector_stores.legacy.get_embedding_service", lambda: fake)
    store = VectorStore(backend=_BrokenBackend())
    assert store.add_document("doc-1", "text", {}) is False


def test_legacy_search_filters_by_threshold_and_sorts(legacy_store, monkeypatch):
    from app.config import Config

    monkeypatch.setattr(Config, "SIMILARITY_THRESHOLD", 0.5)
    fake = legacy_store.backend
    fake.hits = [
        VectorHit(id="low", text="low", metadata={}, similarity=0.3, distance=2.33),
        VectorHit(id="high", text="high", metadata={}, similarity=0.9, distance=0.11),
        VectorHit(id="mid", text="mid", metadata={}, similarity=0.7, distance=0.43),
    ]
    results = legacy_store.search("query", top_k=10, filters={"workspace_id": 1})
    assert [item["id"] for item in results] == ["high", "mid"]
    assert fake.search_calls[0][1] == {"workspace_id": 1}
    assert fake.search_calls[0][2] == 10


def test_legacy_delete_and_count_forward_to_backend(legacy_store):
    fake = legacy_store.backend
    assert legacy_store.delete_document("doc-1") is True
    assert fake.delete_by_ids_calls == [["doc-1"]]
    assert legacy_store.delete_all() is True
    assert fake.delete_all_calls == 1
    assert legacy_store.count() == 3


# ---------------------------------------------------------------------------
# 工厂：配置选择后端
# ---------------------------------------------------------------------------


def test_factory_creates_qdrant_backend_by_config(tmp_path):
    backend = create_vector_backend(
        settings={
            "VECTOR_BACKEND": "qdrant",
            "QDRANT_PATH": str(tmp_path / "qdrant"),
            "QDRANT_URL": "",
        },
        dimension=4,
    )
    assert type(backend).__name__ == "QdrantVectorBackend"


def test_factory_creates_chroma_backend_by_config(tmp_path):
    pytest.importorskip("chromadb")
    backend = create_vector_backend(
        settings={
            "VECTOR_BACKEND": "chroma",
            "CHROMA_PERSIST_DIRECTORY": str(tmp_path / "chroma"),
        }
    )
    assert type(backend).__name__ == "ChromaVectorBackend"


def test_factory_falls_back_to_qdrant_on_unknown_backend(tmp_path):
    backend = create_vector_backend(
        settings={
            "VECTOR_BACKEND": "weaviate",
            "QDRANT_PATH": str(tmp_path / "qdrant"),
            "QDRANT_URL": "",
        },
        dimension=4,
    )
    assert type(backend).__name__ == "QdrantVectorBackend"


def test_factory_singletons_are_stable(monkeypatch, tmp_path):
    from app.config import Config

    monkeypatch.setattr(Config, "QDRANT_URL", "")
    monkeypatch.setattr(Config, "QDRANT_PATH", str(tmp_path / "qdrant"))
    first_backend = get_vector_backend()
    second_backend = get_vector_backend()
    assert first_backend is second_backend
    first_store = get_vector_store()
    second_store = get_vector_store()
    assert first_store is second_store
