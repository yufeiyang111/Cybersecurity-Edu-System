# -*- coding: utf-8 -*-
"""
索引重建服务（任务式，向量 / 图谱 / 全部）

将同步阻塞的重建改造为后台任务，支持三种模式：
- mode="vector"：仅重建向量索引（逐文档分块、embedding、写入，实时上报真实进度）
- mode="graph" ：仅重建知识图谱（逐文档实体抽取与关系构建，实时上报进度）
- mode="all"   ：先向量后图谱（分两个阶段执行）

- get_status() 返回当前状态与完成后的量化报告（向量块数、图谱节点/边、耗时、失败明细、分块分布）

仅支持单实例进程内任务（与 Redis 降级线程模式一致）：同一时刻只允许一个重建任务，
重复启动返回 busy。状态存于进程内存，服务重启后丢失（属预期，任务本身幂等）。
"""
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from app.services.rag_engine import get_rag_engine
from app.services.text_chunker import chunk_text

REBUILD_MODES = ("vector", "graph", "all")


class VectorRebuildService:
    """后台重建索引（向量/图谱/全部）并产出量化报告。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            "status": "idle",  # idle / running / success / error
            "message": "",
            "started_at": None,
            "finished_at": None,
            "elapsed_seconds": 0.0,
            "mode": "vector",  # vector / graph / all
            "stage": "",  # 当前阶段：vector / graph（mode=all 时用于区分）
            # 进度（真实处理数量）
            "total_docs": 0,
            "processed_docs": 0,
            "vector_count": 0,
            "graph_nodes": 0,
            "graph_edges": 0,
            "graph_processed_docs": 0,
            # 量化报告
            "chunks_per_doc_max": 0,
            "chunks_per_doc_avg": 0.0,
            "failed_docs": [],
            "recent_processed": [],
        }
        self._worker: Optional[threading.Thread] = None
        # 可注入：后台线程获取 Flask app 的工厂（测试可替换为假 app）
        self._flask_app_factory = get_flask_app

    def start(self, mode: str = "vector", resume: bool = False) -> Dict[str, Any]:
        """启动重建任务；已在运行时返回 busy 状态。

        mode: "vector" 仅向量 / "graph" 仅图谱 / "all" 向量+图谱
        resume: 是否从断点继续（仅 graph 模式有效，跳过已完成文档）
        """
        if mode not in REBUILD_MODES:
            raise ValueError(f"mode 必须是 {REBUILD_MODES} 之一，收到: {mode!r}")
        with self._lock:
            if self._state["status"] == "running":
                return {"started": False, "busy": True, **self._public_state()}
            self._state = {
                "status": "running",
                "message": "重建任务已启动",
                "started_at": time.time(),
                "finished_at": None,
                "elapsed_seconds": 0.0,
                "mode": mode,
                "resume": resume,
                "stage": "",
                "total_docs": 0,
                "processed_docs": 0,
                "vector_count": 0,
                "graph_nodes": 0,
                "graph_edges": 0,
                "graph_processed_docs": 0,
                "chunks_per_doc_max": 0,
                "chunks_per_doc_avg": 0.0,
                "failed_docs": [],
                "recent_processed": [],
                "usage_tokens": 0,
                "checkpoint_docs": 0,
            }
            self._worker = threading.Thread(
                target=self._run,
                args=(mode, resume),
                name="index-rebuild-worker",
                daemon=True,
            )
            self._worker.start()
            return {"started": True, "busy": False, **self._public_state()}

    def status(self) -> Dict[str, Any]:
        """查询当前任务状态与报告。"""
        with self._lock:
            return self._public_state()

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _load_published_items(self) -> List[Dict[str, Any]]:
        """加载全部已发布知识条目（独立方法便于测试替换）。"""
        from app.models.knowledge import KnowledgeItem

        items = KnowledgeItem.query.filter_by(status="published").all()
        return [item.to_dict() for item in items]

    def _graph_builder(self):
        """知识图谱构建器（LLM 抽取式，独立方法便于测试替换）。"""
        from app.services.kg.builder import build_knowledge_graph_llm

        return build_knowledge_graph_llm

    def _checkpoint_path(self) -> str:
        """图谱抽取断点文件路径（DATA_DIR 下，额度耗尽时保留供 resume）。"""
        from app.config import DATA_DIR

        return str(DATA_DIR / "kg_llm_checkpoint.json")

    def _checkpoint_docs(self) -> int:
        """当前断点中已完成的文档数（0 表示无断点）。"""
        try:
            from app.services.kg.checkpoint import CheckpointStore

            store = CheckpointStore(self._checkpoint_path())
            if not store.exists():
                return 0
            return len(store.load().get("completed_docs", []))
        except Exception:  # noqa: BLE001
            return 0

    def _public_state(self) -> Dict[str, Any]:
        state = dict(self._state)
        total = state["total_docs"] or 1
        # 进度折算：vector 阶段看向量进度，graph 阶段看图谱进度，all 模式两阶段各占一半
        if state["mode"] == "graph":
            state["progress_percent"] = round(state["graph_processed_docs"] / total * 100, 1)
        elif state["mode"] == "all" and state["stage"] == "graph":
            vector_part = 50.0
            graph_part = round(state["graph_processed_docs"] / total * 50, 1)
            state["progress_percent"] = round(vector_part + graph_part, 1)
        else:
            state["progress_percent"] = round(state["processed_docs"] / total * 100, 1)
        state["progress_percent"] = min(state["progress_percent"], 100.0)
        if state["status"] == "idle":
            state["progress_percent"] = 0.0
        return state

    def _set_state(self, **kwargs: Any) -> None:
        with self._lock:
            self._state.update(kwargs)

    def _run(self, mode: str, resume: bool = False) -> None:
        try:
            app = self._flask_app_factory()
            with app.app_context():
                self._run_with_context(mode, resume)
        except Exception as exc:  # noqa: BLE001
            elapsed = 0.0
            if self._state.get("started_at"):
                elapsed = round(time.time() - self._state["started_at"], 2)
            self._set_state(
                status="error",
                message=f"重建失败: {str(exc)[:200]}",
                finished_at=time.time(),
                elapsed_seconds=elapsed,
            )

    def _run_with_context(self, mode: str, resume: bool = False) -> None:
        try:
            items_data = self._load_published_items()
            total = len(items_data)
            self._set_state(total_docs=total, message=f"共 {total} 个知识条目待处理")

            failed: List[Dict[str, Any]] = []
            vector_count = 0
            chunk_counts: List[int] = []
            graph_nodes = 0
            graph_edges = 0
            usage_tokens = 0

            # ---------- 阶段一：向量索引 ----------
            if mode in ("vector", "all"):
                self._set_state(stage="vector", message=f"正在重建向量索引（{total} 篇）…")
                vector_count, chunk_counts, failed = self._run_vector(items_data, failed)

            # ---------- 阶段二：知识图谱（LLM 抽取，分片断点续传） ----------
            if mode in ("graph", "all"):
                self._set_state(stage="graph", message=f"正在构建知识图谱（{total} 篇）…")
                try:
                    from app.services.kg.llm_extractor import QuotaExhaustedError

                    builder = self._graph_builder()
                    graph_result = builder(
                        items_data,
                        progress_callback=self._graph_progress,
                        checkpoint_path=self._checkpoint_path(),
                        resume=resume,
                    )
                    graph_nodes = int(graph_result.get("nodes_added", 0))
                    graph_edges = int(graph_result.get("edges_added", 0))
                    usage_tokens = int(graph_result.get("usage_tokens", 0))
                except QuotaExhaustedError as exc:
                    # 额度耗尽：任务暂停（断点已保存），等待恢复后继续
                    self._set_state(
                        status="quota_exhausted",
                        message=f"LLM 额度已耗尽：{str(exc)}。请等待额度恢复后点击「继续」",
                        finished_at=time.time(),
                        elapsed_seconds=round(time.time() - self._state["started_at"], 2),
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    failed.append({
                        "id": "-",
                        "title": "知识图谱",
                        "error": f"图谱构建失败: {str(exc)[:200]}",
                    })

            # ---------- 汇总报告 ----------
            chunks_per_doc_avg = (
                round(sum(chunk_counts) / len(chunk_counts), 2) if chunk_counts else 0.0
            )
            chunks_per_doc_max = max(chunk_counts) if chunk_counts else 0

            elapsed = round(time.time() - self._state["started_at"], 2)
            checkpoint_docs = 0
            if mode in ("graph", "all"):
                checkpoint_docs = self._checkpoint_docs()
            self._set_state(
                status="success",
                message=f"重建完成：{total} 个文档，{vector_count} 个向量块，{graph_nodes} 个图节点",
                finished_at=time.time(),
                elapsed_seconds=elapsed,
                graph_nodes=graph_nodes,
                graph_edges=graph_edges,
                chunks_per_doc_avg=chunks_per_doc_avg,
                chunks_per_doc_max=chunks_per_doc_max,
                failed_docs=failed,
                usage_tokens=usage_tokens,
                checkpoint_docs=checkpoint_docs,
                stage="",
            )
        except Exception as exc:  # noqa: BLE001
            # 单文档级失败已在循环内兜底；此处兜底整体失败（数据库断开等）
            elapsed = 0.0
            if self._state.get("started_at"):
                elapsed = round(time.time() - self._state["started_at"], 2)
            self._set_state(
                status="error",
                message=f"重建失败: {str(exc)[:200]}",
                finished_at=time.time(),
                elapsed_seconds=elapsed,
            )

    def _run_vector(
        self,
        items_data: List[Dict[str, Any]],
        failed: List[Dict[str, Any]],
    ) -> tuple[int, List[int], List[Dict[str, Any]]]:
        """逐文档重建向量索引，实时更新进度。"""
        rag_engine = get_rag_engine()
        backend = rag_engine.vector_store.backend
        embedding_service = rag_engine.vector_store.embedding_service

        vector_count = 0
        chunk_counts: List[int] = []

        for index, item in enumerate(items_data, start=1):
            doc_id = str(item["id"])
            text = f"{item.get('title', '')}。{item.get('content', '')}"
            try:
                chunks = chunk_text(
                    text,
                    doc_id=doc_id,
                    metadata={
                        "title": item.get("title", ""),
                        "category": item.get("category_name", ""),
                        "source": item.get("source", ""),
                        "difficulty": item.get("difficulty", "medium"),
                        "title_path": item.get("title", ""),
                    },
                    strategy="smart",
                )
                if not chunks:
                    failed.append({
                        "id": doc_id,
                        "title": item.get("title", ""),
                        "error": "内容为空或分块失败",
                    })
                else:
                    backend.delete(where={"doc_id": doc_id})
                    vectors = embedding_service.encode([chunk["text"] for chunk in chunks])
                    written = backend.upsert(
                        ids=[chunk["id"] for chunk in chunks],
                        vectors=vectors.tolist(),
                        texts=[chunk["text"] for chunk in chunks],
                        metadatas=[
                            {
                                "doc_id": doc_id,
                                "chunk_index": ci,
                                "start_line": chunk.get("start_line", 0),
                                "end_line": chunk.get("end_line", 0),
                                "start_char": chunk.get("start_char", 0),
                                "end_char": chunk.get("end_char", 0),
                                "title_path": item.get("title", ""),
                                "title": item.get("title", ""),
                                "category": item.get("category_name", ""),
                                "source": item.get("source", ""),
                                "difficulty": item.get("difficulty", "medium"),
                                "parent_text": chunk.get("metadata", {}).get("parent_text", ""),
                            }
                            for ci, chunk in enumerate(chunks)
                        ],
                    )
                    vector_count += written
                    chunk_counts.append(written)
            except Exception as exc:  # noqa: BLE001
                failed.append({
                    "id": doc_id,
                    "title": item.get("title", ""),
                    "error": str(exc)[:200],
                })

            # 实时进度（每处理一个文档更新一次）
            recent = self._state.get("recent_processed", [])
            recent.append({
                "doc_id": doc_id,
                "title": (item.get("title") or "")[:40],
                "chunks": chunk_counts[-1] if chunk_counts else 0,
            })
            self._set_state(
                processed_docs=index,
                vector_count=vector_count,
                recent_processed=recent[-5:],
            )

        return vector_count, chunk_counts, failed

    def _graph_progress(self, processed: int, total: int) -> None:
        """图谱构建进度回调：实时更新 graph_processed_docs。"""
        self._set_state(
            graph_processed_docs=processed,
            message=f"正在构建知识图谱（{processed}/{total} 篇）…",
        )


_service: Optional[VectorRebuildService] = None
_service_lock = threading.Lock()
_flask_app = None
_flask_app_lock = threading.Lock()


def get_flask_app():
    """获取全局 Flask app 实例（后台线程执行 DB 操作需要 app context）。"""
    global _flask_app
    with _flask_app_lock:
        if _flask_app is None:
            from app import create_app

            _flask_app = create_app()
        return _flask_app


def get_vector_rebuild_service() -> VectorRebuildService:
    """获取重建服务单例。"""
    global _service
    with _service_lock:
        if _service is None:
            _service = VectorRebuildService()
        return _service
