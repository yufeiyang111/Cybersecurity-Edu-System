# -*- coding: utf-8 -*-
"""
存量实体描述回填服务（Description Backfill）

LLM 抽取链路升级后新实体会自带 description，但存量实体（升级前构建）没有。
本服务从 Neo4j 找出缺少 description 的实体（按 degree 降序取 Top N），
批量调用 LLM 生成一句话中文描述并写回节点属性，供：
- GraphRAG Local Search 上下文（实体描述是查询输入的核心）
- 社区摘要采样的代表性实体说明

设计（与 vector_rebuild_service 一致）：
- 进程内 daemon 线程 + 状态机（idle/running/success/error），单飞（busy 拒绝）
- 分批并发：每批 15 个实体一个 LLM 调用（并发 3 批），失败项跳过不阻塞
- Neo4j 不可用时服务返回错误（回填依赖 Neo4j 属性更新）
"""
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from app.services.kg.llm_provider import get_llm_provider_client
from app.services.graph_store import get_knowledge_graph

logger = logging.getLogger(__name__)

BATCH_SIZE = 15  # 每批实体数（一个 LLM 调用生成一批描述）
BATCH_WORKERS = 3

BACKFILL_SYSTEM_PROMPT = (
    "你是一名网络安全知识工程师。为给定的实体列表生成一句话中文描述。\n"
    "要求：\n"
    "1. 每个描述 15-40 字，说明该实体在网络安全领域的含义/作用（漏洞/攻击技术/防御措施/"
    "安全工具/概念/法规标准/威胁行为体等）；\n"
    "2. 只依据实体名称推断，禁止臆造具体漏洞编号或文档细节；\n"
    "3. 输出必须是合法的 JSON 数组，元素格式为 "
    '{"name": "实体名（与输入完全一致）", "description": "一句话描述"}；\n'
    "4. 只输出 JSON 数组本身，不要输出解释、markdown 代码块或多余文字。"
)


class DescriptionBackfillService:
    """后台回填实体描述（单飞，带进度状态）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            "status": "idle",  # idle / running / success / error
            "message": "",
            "started_at": None,
            "finished_at": None,
            "elapsed_seconds": 0.0,
            "total_entities": 0,
            "processed_entities": 0,
            "updated_entities": 0,
            "failed_batches": 0,
            "usage_tokens": 0,
        }
        self._worker: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    def start(self, limit: int = 500, force: bool = False) -> Dict[str, Any]:
        """启动回填任务；已在运行时返回 busy 状态。"""
        with self._lock:
            if self._state["status"] == "running":
                return {"started": False, "busy": True, **self._public_state()}
            self._state = {
                "status": "running",
                "message": "实体描述回填已启动",
                "started_at": time.time(),
                "finished_at": None,
                "elapsed_seconds": 0.0,
                "total_entities": 0,
                "processed_entities": 0,
                "updated_entities": 0,
                "failed_batches": 0,
                "usage_tokens": 0,
            }
            self._worker = threading.Thread(
                target=self._run,
                args=(limit, force),
                name="description-backfill-worker",
                daemon=True,
            )
            self._worker.start()
            return {"started": True, "busy": False, **self._public_state()}

    def status(self) -> Dict[str, Any]:
        """查询当前任务状态。"""
        with self._lock:
            return self._public_state()

    # ------------------------------------------------------------------
    def _public_state(self) -> Dict[str, Any]:
        state = dict(self._state)
        state["elapsed_seconds"] = round(
            time.time() - (state.get("started_at") or time.time()), 2
        )
        return state

    def _run(self, limit: int, force: bool) -> None:
        from flask import current_app

        try:
            app = current_app._get_current_object()
        except RuntimeError:
            app = None
        try:
            if app is not None:
                with app.app_context():
                    report = self._backfill(limit, force)
            else:
                report = self._backfill(limit, force)
        except Exception as exc:  # noqa: BLE001
            logger.warning("实体描述回填失败: %s", type(exc).__name__)
            with self._lock:
                self._state["status"] = "error"
                self._state["message"] = f"回填失败：{type(exc).__name__}"
                self._state["finished_at"] = time.time()
            return
        with self._lock:
            self._state.update(report)
            self._state["status"] = "success"
            self._state["message"] = "实体描述回填完成"
            self._state["finished_at"] = time.time()

    # ------------------------------------------------------------------
    # 内部实现（可注入以便测试）
    # ------------------------------------------------------------------
    def _load_entities(self, limit: int) -> List[Dict[str, Any]]:
        """从 Neo4j 取缺 description 的实体（按 degree 降序）。"""
        graph = get_knowledge_graph()
        if not graph.use_neo4j or graph._neo4j_graph is None:
            raise RuntimeError("Neo4j 不可用，无法回填描述")
        with graph._neo4j_graph.driver.session() as session:
            result = session.run(
                "MATCH (e:Entity) "
                "WHERE e.description IS NULL OR e.description = '' "
                "OPTIONAL MATCH (e)-[r]-() "
                "WITH e, count(r) AS deg "
                "RETURN e.id AS id, e.name AS name, e.type AS type, deg "
                "ORDER BY deg DESC, e.id LIMIT $limit",
                {"limit": limit},
            )
            return [
                {"id": record["id"], "name": record["name"], "type": record["type"] or "concept"}
                for record in result
            ]

    def _update_descriptions(self, updates: List[Dict[str, str]]) -> None:
        """把 {id: description} 写回 Neo4j 节点属性。"""
        graph = get_knowledge_graph()
        if not graph.use_neo4j or graph._neo4j_graph is None:
            return
        with graph._neo4j_graph.driver.session() as session:
            for entity_id, description in updates.items():
                session.run(
                    "MATCH (e:Entity {id: $id}) SET e.description = $description",
                    {"id": entity_id, "description": description},
                )

    def _backfill(self, limit: int, force: bool) -> Dict[str, Any]:
        """核心逻辑：分批 LLM 生成描述并写回。"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        entities = self._load_entities(limit)
        total = len(entities)
        with self._lock:
            self._state["total_entities"] = total
        if total == 0:
            return {
                "total_entities": 0,
                "processed_entities": 0,
                "updated_entities": 0,
                "failed_batches": 0,
                "usage_tokens": 0,
            }

        client = get_llm_provider_client()
        batches = [
            entities[i : i + BATCH_SIZE]
            for i in range(0, len(entities), BATCH_SIZE)
        ]
        updated: Dict[str, str] = {}
        failed_batches = 0
        processed = 0
        usage_tokens = 0

        def _handle_batch(batch: List[Dict[str, Any]]) -> List[Dict[str, str]]:
            names = "\n".join(f"- {b['name']}（{b['type']}）" for b in batch)
            raw = client.call(names, system_prompt=BACKFILL_SYSTEM_PROMPT, temperature=0.2)
            if not raw:
                return []
            parsed = self._parse_batch(raw)
            if not parsed:
                return []
            by_name = {b["name"]: b["id"] for b in batch}
            return [
                {"id": by_name[item["name"]], "description": item["description"]}
                for item in parsed
                if item.get("name") in by_name and item.get("description")
            ]

        with ThreadPoolExecutor(max_workers=BATCH_WORKERS) as pool:
            futures = {pool.submit(_handle_batch, batch): batch for batch in batches}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        updated.update({item["id"]: item["description"] for item in result})
                    else:
                        failed_batches += 1
                except Exception as exc:  # noqa: BLE001
                    failed_batches += 1
                    logger.warning("描述回填批次失败: %s", type(exc).__name__)
                processed += BATCH_SIZE
                with self._lock:
                    self._state["processed_entities"] = min(processed, total)
                    self._state["failed_batches"] = failed_batches

        # 写回 Neo4j
        if updated:
            self._update_descriptions(updated)
        # 描述变化后图谱缓存失效（NetworkX 视图 + 社区检测）
        try:
            graph = get_knowledge_graph()
            graph._invalidate_sync()
        except Exception:  # noqa: BLE001
            pass
        from app.services.graph_communities import get_community_detector

        get_community_detector().invalidate()

        usage = client.usage
        usage_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        return {
            "total_entities": total,
            "processed_entities": total,
            "updated_entities": len(updated),
            "failed_batches": failed_batches,
            "usage_tokens": usage_tokens,
        }

    @staticmethod
    def _parse_batch(raw: str) -> List[Dict[str, Any]]:
        """解析 LLM 批量描述 JSON 数组（容错围栏/前后缀）。"""
        import json

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        text = text.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end <= start:
                return []
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return []
        if not isinstance(parsed, list):
            return []
        result = []
        for item in parsed:
            if isinstance(item, dict) and item.get("name") and item.get("description"):
                result.append({
                    "name": str(item["name"]),
                    "description": str(item["description"]).strip(),
                })
        return result


_service: Optional[DescriptionBackfillService] = None
_service_lock = threading.Lock()


def get_description_backfill_service() -> DescriptionBackfillService:
    """获取回填服务单例。"""
    global _service
    with _service_lock:
        if _service is None:
            _service = DescriptionBackfillService()
        return _service
