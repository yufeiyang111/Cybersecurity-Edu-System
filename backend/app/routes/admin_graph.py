# -*- coding: utf-8 -*-
"""
管理员-知识图谱社区接口（社区检测/按社区查询）

- GET /api/admin/graph/communities   社区列表与节点归属（按 size 降序）
- GET /api/admin/graph/communities/<cid>/nodes  指定社区节点（分页）
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt

from app.services.graph_communities import get_community_detector
from app.services.graph_store import get_knowledge_graph

admin_graph_bp = Blueprint("admin_graph", __name__)


def _require_admin() -> bool:
    claims = get_jwt()
    return claims.get("role", "guest") == "admin"


@admin_graph_bp.route("/graph/communities", methods=["GET"])
@jwt_required()
def get_graph_communities():
    """社区检测结果：community 列表 + 节点归属映射。"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

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
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

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
