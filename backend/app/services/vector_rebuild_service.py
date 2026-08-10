# -*- coding: utf-8 -*-
"""
向量索引重建服务（任务式）

将 /admin/vector/rebuild 的同步阻塞重建改造为后台任务：
- start_rebuild() 在后台线程逐文档重建，实时记录已处理文档数与已写入向量块数（真实进度）
- get_status() 返回当前状态与完成后的量化报告（向量块数、图谱节点/边、耗时、失败明细、分块分布）

仅支持单实例进程内任务（与 Redis 降级线程模式一致）：同一时刻只允许一个重建任务，
重复启动返回 busy。状态存于进程内存，服务重启后丢失（属预期，任务本身幂等）。
"""
import threading
import time
from typing import Any, Dict, List, Optional

from app.services.rag_engine import get_rag_engine
from app.services.text_chunker import chunk_text


class VectorRebuildService:
    """后台重建向量索引并产出量化报告。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            "status": "idle",  # idle / running / success / error
            "message": "",
            "started_at": None,
            "finished_at": None,
            "elapsed_seconds": 0.0,
            "include_graph": False,
            # 进度（真实向量化数量）
            "total_docs": 0,
            "processed_docs": 0,
            "vector_count": 0,
            "graph_nodes": 0,
            "graph_edges": 0,
            # 量化报告
            "chunks_per_doc_max": 0,
            "chunks_per_doc_avg": 0.0,
            "failed_docs": [],
            "recent_processed": [],
        }
        self._worker: Optional[threading.Thread] = None
        # 可注入：后台线程获取 Flask app 的工厂（测试可替换为假 app）
        self._flask_app_factory = get_flask_app

    def start(self, include_graph: bool = False) -> Dict[str, Any]:
        """启动重建任务；已在运行时返回 busy 状态。"""
        with self._lock:
            if self._state["status"] == "running":
                return {"started": False, "busy": True, **self._public_state()}
            self._state = {
                "status": "running",
                "message": "重建任务已启动",
                "started_at": time.time(),
                "finished_at": None,
                "elapsed_seconds": 0.0,
                "include_graph": include_graph,
                "total_docs": 0,
                "processed_docs": 0,
                "vector_count": 0,
                "graph_nodes": 0,
                "graph_edges": 0,
                "chunks_per_doc_max": 0,
                "chunks_per_doc_avg": 0.0,
                "failed_docs": [],
                "recent_processed": [],
            }
            self._worker = threading.Thread(
                target=self._run,
                args=(include_graph,),
                name="vector-rebuild-worker",
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
        """知识图谱构建器（独立方法便于测试替换）。"""
        from app.services.data_processor import build_knowledge_graph

        return build_knowledge_graph

    def _public_state(self) -> Dict[str, Any]:
        state = dict(self._state)
        total = state["total_docs"] or 1
        state["progress_percent"] = round(state["processed_docs"] / total * 100, 1)
        state["progress_percent"] = min(state["progress_percent"], 100.0)
        if state["status"] == "idle":
            state["progress_percent"] = 0.0
        return state

    def _set_state(self, **kwargs: Any) -> None:
        with self._lock:
            self._state.update(kwargs)

    def _run(self, include_graph: bool) -> None:
        try:
            app = self._flask_app_factory()
            with app.app_context():
                self._run_with_context(include_graph)
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

    def _run_with_context(self, include_graph: bool) -> None:
        try:
            rag_engine = get_rag_engine()
            backend = rag_engine.vector_store.backend
            embedding_service = rag_engine.vector_store.embedding_service
            graph = rag_engine.knowledge_graph

            items_data = self._load_published_items()
            total = len(items_data)
            self._set_state(total_docs=total, message=f"共 {total} 个知识条目待重建")

            vector_count = 0
            failed: List[Dict[str, Any]] = []
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

            # 图谱构建（可选）
            graph_nodes = 0
            graph_edges = 0
            if include_graph:
                self._set_state(message="向量索引完成，正在构建知识图谱…")
                try:
                    builder = self._graph_builder()
                    graph_result = builder(items_data)
                    graph_nodes = int(graph_result.get("nodes_added", 0))
                    graph_edges = int(graph_result.get("edges_added", 0))
                except Exception as exc:  # noqa: BLE001
                    failed.append({
                        "id": "-",
                        "title": "知识图谱",
                        "error": f"图谱构建失败: {str(exc)[:200]}",
                    })

            # 分块分布统计
            chunks_per_doc_avg = (
                round(sum(chunk_counts) / len(chunk_counts), 2) if chunk_counts else 0.0
            )
            chunks_per_doc_max = max(chunk_counts) if chunk_counts else 0

            elapsed = round(time.time() - self._state["started_at"], 2)
            self._set_state(
                status="success",
                message=f"重建完成：{total} 个文档，{vector_count} 个向量块",
                finished_at=time.time(),
                elapsed_seconds=elapsed,
                graph_nodes=graph_nodes,
                graph_edges=graph_edges,
                chunks_per_doc_avg=chunks_per_doc_avg,
                chunks_per_doc_max=chunks_per_doc_max,
                failed_docs=failed,
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
