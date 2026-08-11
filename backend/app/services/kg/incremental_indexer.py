# -*- coding: utf-8 -*-
"""
知识图谱增量索引器（Incremental Indexer）

对齐 GraphRAG 的增量索引理念：知识条目变化（新增/更新/删除）时，
只处理变化的文档，而不是全量重建图谱：

- on_knowledge_imported(items)：后台线程对新增/更新的文档跑 LLM 抽取与入库
  （builder 的 MERGE 幂等保证已有实体/关系不重复），完成后失效社区检测与
  图谱同步缓存
- on_knowledge_deleted(doc_id)：同步清理 Neo4j 中的知识节点、contains 边与
  孤儿实体

设计：
- 进程内 daemon 线程 + 单飞（同一时刻只允许一个增量任务，排队语义为
  "合并后续请求"，避免导入大量文档时反复触发）
- 与 vector_rebuild_service / description_backfill 一致：RQ 不可用时
  线程降级，状态存进程内存
"""
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class IncrementalIndexer:
    """增量图谱索引器（导入异步构建 + 删除同步清理）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: List[Dict[str, Any]] = []
        self._worker: Optional[threading.Thread] = None
        self._state: Dict[str, Any] = {
            "status": "idle",  # idle / running / success / error
            "message": "",
            "started_at": None,
            "finished_at": None,
            "elapsed_seconds": 0.0,
            "queued_items": 0,
            "processed_items": 0,
            "nodes_added": 0,
            "edges_added": 0,
        }

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def on_knowledge_imported(self, items: List[Dict[str, Any]]) -> None:
        """知识条目新增/更新后触发增量图谱构建（异步，合并排队）。"""
        if not items:
            return
        with self._lock:
            self._pending.extend(items)
            self._state["queued_items"] += len(items)
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run_pending,
                name="kg-incremental-index-worker",
                daemon=True,
            )
            self._worker.start()

    def on_knowledge_deleted(self, doc_id: str) -> None:
        """知识条目删除后同步清理图谱节点/边。"""
        try:
            from app.services.graph_store import get_knowledge_graph

            graph = get_knowledge_graph()
            removed = graph.remove_knowledge_node(str(doc_id))
            if removed:
                from app.services.graph_communities import get_community_detector

                get_community_detector().invalidate()
        except Exception as exc:  # noqa: BLE001
            logger.warning("图谱节点清理失败 doc=%s err=%s", doc_id, type(exc).__name__)

    def status(self) -> Dict[str, Any]:
        """查询增量索引任务状态。"""
        with self._lock:
            state = dict(self._state)
            state["elapsed_seconds"] = round(
                time.time() - (state.get("started_at") or time.time()), 2
            )
            return state

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _run_pending(self) -> None:
        from flask import current_app

        try:
            app = current_app._get_current_object()
        except RuntimeError:
            app = None

        with self._lock:
            self._state["status"] = "running"
            self._state["message"] = "增量图谱构建中"
            self._state["started_at"] = time.time()
            self._state["processed_items"] = 0

        try:
            if app is not None:
                with app.app_context():
                    report = self._build_pending()
            else:
                report = self._build_pending()
        except Exception as exc:  # noqa: BLE001
            logger.warning("增量图谱构建失败: %s", type(exc).__name__)
            with self._lock:
                self._state["status"] = "error"
                self._state["message"] = f"增量构建失败：{type(exc).__name__}"
                self._state["finished_at"] = time.time()
            return

        with self._lock:
            self._state.update(report)
            self._state["status"] = "success"
            self._state["message"] = "增量图谱构建完成"
            self._state["finished_at"] = time.time()
            # 构建期间又有新请求：继续处理
            if self._pending:
                self._worker = threading.Thread(
                    target=self._run_pending,
                    name="kg-incremental-index-worker",
                    daemon=True,
                )
                self._worker.start()
                return
            self._worker = None

    def _build_pending(self) -> Dict[str, Any]:
        """取出排队文档，构建图谱；完成后失效缓存。"""
        with self._lock:
            items = self._pending
            self._pending = []
        if not items:
            return {
                "processed_items": 0,
                "nodes_added": 0,
                "edges_added": 0,
                "queued_items": 0,
            }
        # 按 doc id 去重（同一文档多次更新只构建一次）
        unique: Dict[str, Dict[str, Any]] = {}
        for item in items:
            unique[str(item["id"])] = item
        docs = list(unique.values())

        def _progress(done: int, total: int) -> None:
            with self._lock:
                self._state["processed_items"] = done

        from app.services.kg.builder import build_knowledge_graph_llm

        report = build_knowledge_graph_llm(docs, progress_callback=_progress)
        # 图谱变化：社区检测与 NetworkX 同步缓存失效
        try:
            from app.services.graph_communities import get_community_detector

            get_community_detector().invalidate()
            from app.services.graph_store import get_knowledge_graph

            get_knowledge_graph()._invalidate_sync()
        except Exception:  # noqa: BLE001
            pass
        return {
            "processed_items": len(docs),
            "nodes_added": report.get("nodes_added", 0),
            "edges_added": report.get("edges_added", 0),
            "queued_items": len(self._pending),
            "usage_tokens": report.get("usage_tokens", 0),
        }


_indexer: Optional[IncrementalIndexer] = None
_indexer_lock = threading.Lock()


def get_incremental_indexer() -> IncrementalIndexer:
    """获取增量索引器单例。"""
    global _indexer
    with _indexer_lock:
        if _indexer is None:
            _indexer = IncrementalIndexer()
        return _indexer


__all__ = ["IncrementalIndexer", "get_incremental_indexer"]
