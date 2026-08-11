# -*- coding: utf-8 -*-
"""
管理员-知识图谱社区接口（社区检测/社区节点/社区摘要/GraphRAG 查询）

权限划分（与 /admin/graph/nodes 等图谱接口一致：登录即可）：
- 只读与按需生成（所有登录用户）：社区列表/社区节点/摘要查询/摘要按需生成/
  Global Search/Local Search（图谱页是公开浏览功能，社区视图与图谱问答
  属于浏览体验的一部分）
- 批量与回填（仅 admin）：批量预生成摘要、实体描述回填（大量消耗 LLM 额度）

- GET  /api/admin/graph/communities                   社区列表与节点归属（按 size 降序）
- GET  /api/admin/graph/communities/<cid>/nodes       指定社区节点（分页）
- GET  /api/admin/graph/communities/<cid>/summary     查询社区摘要（缓存命中返回，未生成 404）
- POST /api/admin/graph/communities/<cid>/summary     生成/重新生成社区摘要（force 强制重生成）
- POST /api/admin/graph/communities/summaries/batch   批量生成 Top N 社区摘要（admin）
- POST /api/admin/graph/global-search                 全局检索（社区摘要 Map-Reduce）
- POST /api/admin/graph/local-search                  局部检索（实体匹配+邻居+社区摘要）
- POST /api/admin/graph/entities/backfill-descriptions 存量实体描述回填（admin，后台任务）
- GET  /api/admin/graph/entities/backfill-descriptions/status 回填任务状态（admin）
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt

from app.services.graph_communities import get_community_detector
from app.services.graph_store import get_knowledge_graph
from app.services.kg.community_summarizer import (
    CommunitySummaryError,
    get_community_summarizer,
)
from app.services.kg.description_backfill import get_description_backfill_service
from app.services.kg.graphrag_search import get_graphrag_searcher

admin_graph_bp = Blueprint("admin_graph", __name__)


def _require_admin() -> bool:
    claims = get_jwt()
    return claims.get("role", "guest") == "admin"


def _community_members(community_id: str, graph_data) -> list:
    """指定社区的全部节点 id（按 degree 降序）。"""
    detector = get_community_detector()
    result = detector.detect(graph_data)
    node_community = result["node_community"]
    members = [
        node_id for node_id, cid in node_community.items() if cid == str(community_id)
    ]
    members.sort(key=lambda nid: graph_data.degree(nid), reverse=True)
    return members


@admin_graph_bp.route("/graph/communities", methods=["GET"])
@jwt_required()
def get_graph_communities():
    """社区检测结果：community 列表 + 节点归属映射。"""
    try:
        graph = get_knowledge_graph()
        detector = get_community_detector()
        result = detector.detect(graph.graph)

        # 仅返回轻量摘要（不含全量 nodes 列表，避免大响应）
        communities = {}
        for cid, info in result["communities"].items():
            communities[cid] = {
                "size": info["size"],
                "sample": info["sample"][:3],
            }
        return jsonify({
            "communities": communities,
            "node_community": result["node_community"],
            "community_count": result["community_count"],
            "algorithm": result["algorithm"],
            "elapsed_seconds": result["elapsed_seconds"],
        }), 200
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@admin_graph_bp.route("/graph/communities/<community_id>/nodes", methods=["GET"])
@jwt_required()
def get_community_nodes(community_id):
    """指定社区内的节点（带 title/type/degree）。"""
    limit = request.args.get("limit", 100, type=int)
    limit = max(1, min(limit, 500))
    offset = request.args.get("offset", 0, type=int)

    try:
        graph = get_knowledge_graph()
        detector = get_community_detector()
        result = detector.detect(graph.graph)
        node_community = result["node_community"]

        graph_data = graph.graph
        members = [
            node_id for node_id, cid in node_community.items() if cid == str(community_id)
        ]
        members.sort(key=lambda nid: graph_data.degree(nid), reverse=True)
        page = members[offset : offset + limit]

        nodes = []
        for node_id in page:
            data = graph_data.nodes[node_id]
            nodes.append({
                "id": node_id,
                "type": data.get("type", "unknown"),
                "title": data.get("title", node_id),
                "category": data.get("category", ""),
                "degree": graph_data.degree(node_id),
            })
        return jsonify({
            "nodes": nodes,
            "total": len(members),
            "offset": offset,
            "limit": limit,
        }), 200
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@admin_graph_bp.route("/graph/communities/<community_id>/summary", methods=["GET"])
@jwt_required()
def get_community_summary(community_id):
    """查询社区摘要（已有缓存直接返回；未生成返回 404 由前端触发生成）。"""
    try:
        graph = get_knowledge_graph()
        graph_data = graph.graph
        members = _community_members(community_id, graph_data)
        if not members:
            return jsonify({"error": "社区不存在"}), 404

        summarizer = get_community_summarizer()
        summary = summarizer.get_cached_summary(community_id, graph_data)
        if summary is None:
            return jsonify({"error": "摘要尚未生成"}), 404
        return jsonify(summary), 200
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@admin_graph_bp.route("/graph/communities/<community_id>/summary", methods=["POST"])
@jwt_required()
def generate_community_summary(community_id):
    """生成/重新生成社区摘要（body.force=true 强制重生成，默认复用缓存）。"""
    force = bool((request.get_json(silent=True) or {}).get("force", False))
    try:
        graph = get_knowledge_graph()
        graph_data = graph.graph
        members = _community_members(community_id, graph_data)
        if not members:
            return jsonify({"error": "社区不存在"}), 404

        summarizer = get_community_summarizer()
        summary = summarizer.get_summary(community_id, members, graph_data, force=force)
        if summary is None:
            return jsonify({"error": "摘要生成失败（LLM 不可用或输出解析失败）"}), 503
        return jsonify(summary), 200
    except CommunitySummaryError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@admin_graph_bp.route("/graph/communities/summaries/batch", methods=["POST"])
@jwt_required()
def generate_community_summaries_batch():
    """批量生成 Top N 社区摘要（body: {limit, force}），逐个报告状态。

    批量消耗 LLM 额度较多，仅管理员可用。
    """
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    body = request.get_json(silent=True) or {}
    limit = max(1, min(int(body.get("limit", 10)), 50))
    force = bool(body.get("force", False))
    try:
        graph = get_knowledge_graph()
        detector = get_community_detector()
        result = detector.detect(graph.graph)
        communities = result["communities"]
        if not communities:
            return jsonify({"results": [], "total": 0}), 200

        summarizer = get_community_summarizer()
        results = summarizer.generate_batch(communities, graph.graph, limit=limit, force=force)
        total_generated = sum(1 for r in results if r["status"] == "generated")
        total_cached = sum(1 for r in results if r["status"] == "cached")
        total_failed = sum(1 for r in results if r["status"] == "failed")
        return jsonify({
            "results": results,
            "requested": len(results),
            "generated": total_generated,
            "cached": total_cached,
            "failed": total_failed,
        }), 200
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@admin_graph_bp.route("/graph/global-search", methods=["POST"])
@jwt_required()
def global_graph_search():
    """GraphRAG 全局检索：基于社区摘要 Map-Reduce 回答全局性问题。"""
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query 不能为空"}), 400
    top_k = max(1, min(int(body.get("top_k", 10)), 30))
    try:
        searcher = get_graphrag_searcher()
        return jsonify(searcher.global_search(query, top_k=top_k)), 200
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@admin_graph_bp.route("/graph/local-search", methods=["POST"])
@jwt_required()
def local_graph_search():
    """GraphRAG 局部检索：实体匹配 + 邻居扩展 + 社区摘要。"""
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query 不能为空"}), 400
    max_depth = max(1, min(int(body.get("max_depth", 2)), 4))
    try:
        searcher = get_graphrag_searcher()
        return jsonify(searcher.local_search(query, max_depth=max_depth)), 200
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@admin_graph_bp.route("/graph/entities/backfill-descriptions", methods=["POST"])
@jwt_required()
def backfill_entity_descriptions():
    """启动存量实体描述回填任务（后台，body: {limit, force}）。

    批量消耗 LLM 额度，仅管理员可用。
    """
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    body = request.get_json(silent=True) or {}
    limit = max(1, min(int(body.get("limit", 500)), 5000))
    force = bool(body.get("force", False))
    try:
        service = get_description_backfill_service()
        return jsonify(service.start(limit=limit, force=force)), 200
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@admin_graph_bp.route("/graph/entities/backfill-descriptions/status", methods=["GET"])
@jwt_required()
def backfill_entity_descriptions_status():
    """查询实体描述回填任务状态。"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403
    try:
        service = get_description_backfill_service()
        return jsonify(service.status()), 200
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500
