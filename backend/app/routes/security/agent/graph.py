"""Project security graph endpoints for agent runs (A4)."""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.models.agent_runtime import AgentRun
from app.models.security import ProjectSnapshot
from app.services.project_security_graph import graph_queries
from app.services.project_security_graph.code_slice import (
    CodeSliceError,
    CodeSliceForbidden,
    read_code_slice,
)
from app.services.project_security_graph.contracts import (
    DEFAULT_MAPPER_VERSION,
    DEFAULT_MAX_NEIGHBOR_PAGE,
)
from app.services.project_security_graph.graph_builder import build_project_graph

from .. import projects_bp
from ..common import AuthorizationError, READ_ROLES, _current_user_id, require_workspace_role

_MAX_PAGE = DEFAULT_MAX_NEIGHBOR_PAGE


def _run_or_404(run_id: int) -> AgentRun | None:
    run = db.session.get(AgentRun, run_id)
    if run is None:
        return None
    require_workspace_role(run.workspace_id, _current_user_id(), READ_ROLES)
    return run


def _snapshot_or_404(snapshot_id: int) -> ProjectSnapshot | None:
    snapshot = db.session.get(ProjectSnapshot, snapshot_id)
    if snapshot is None:
        return None
    from app.models.security import SecurityProject

    project = db.session.get(SecurityProject, snapshot.project_id)
    if project is None:
        return None
    require_workspace_role(project.workspace_id, _current_user_id(), READ_ROLES)
    return snapshot


def _page_params() -> tuple[int, int]:
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    if not 1 <= limit <= _MAX_PAGE or offset < 0:
        raise ValueError(f"limit 必须在 1 至 {_MAX_PAGE} 之间，offset 不能小于 0")
    return limit, offset


@projects_bp.route("/agent-runs/<int:run_id>/graph", methods=["GET"])
@jwt_required()
def get_agent_run_graph(run_id: int):
    try:
        run = _run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        mapper_version = request.args.get("mapper_version", DEFAULT_MAPPER_VERSION)
        summary = graph_queries.graph_summary(run.snapshot_id, mapper_version)
        if summary is None:
            return jsonify(
                {
                    "graph": None,
                    "message": "该快照尚未建图，可通过 map_repository 工具触发",
                }
            ), 200
        limit, offset = _page_params()
        nodes, total = graph_queries.entry_nodes(
            run.snapshot_id, mapper_version, limit, offset
        )
        return jsonify(
            {
                "graph": summary,
                "entry_nodes": [node.to_dict() for node in nodes],
                "pagination": {"total": total, "limit": limit, "offset": offset},
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/agent-runs/<int:run_id>/graph/build", methods=["POST"])
@jwt_required()
def build_agent_run_graph(run_id: int):
    try:
        run = _run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        snapshot = db.session.get(ProjectSnapshot, run.snapshot_id)
        if snapshot is None:
            return jsonify({"error": "快照不存在"}), 404
        result = build_project_graph(
            snapshot, mapper_version=DEFAULT_MAPPER_VERSION
        )
        status_code = 200 if result.status in {"built", "cached"} else 409
        return jsonify(
            {
                "status": result.status,
                "node_count": result.node_count,
                "edge_count": result.edge_count,
                "file_count": result.file_count,
                "mapper_version": result.mapper_version,
                "message": result.message,
            }
        ), status_code
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-runs/<int:run_id>/graph/nodes/<int:node_id>/neighbors", methods=["GET"])
@jwt_required()
def get_graph_node_neighbors(run_id: int, node_id: int):
    try:
        run = _run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        mapper_version = request.args.get("mapper_version", DEFAULT_MAPPER_VERSION)
        node = graph_queries.node_or_none(node_id, run.snapshot_id, mapper_version)
        if node is None:
            return jsonify({"error": "图节点不存在"}), 404
        limit, offset = _page_params()
        edge_types = request.args.getlist("edge_types") or None
        edges, total = graph_queries.node_neighbors(node, limit, offset, edge_types)
        return jsonify(
            {
                "node": node.to_dict(),
                "edges": [edge.to_dict() for edge in edges],
                "pagination": {"total": total, "limit": limit, "offset": offset},
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route("/agent-runs/<int:run_id>/graph/by-file", methods=["GET"])
@jwt_required()
def get_graph_nodes_by_file(run_id: int):
    try:
        run = _run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        file_path = request.args.get("file_path")
        if not file_path or len(file_path) > 512:
            return jsonify({"error": "file_path 必填且不能超过 512 字符"}), 400
        nodes = graph_queries.nodes_for_file(
            run.snapshot_id, DEFAULT_MAPPER_VERSION, file_path
        )
        return jsonify({"file_path": file_path, "nodes": [node.to_dict() for node in nodes]})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403


@projects_bp.route("/agent-runs/<int:run_id>/graph/code-slice", methods=["GET"])
@jwt_required()
def get_graph_code_slice(run_id: int):
    try:
        run = _run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        file_path = request.args.get("file")
        start_line = request.args.get("start_line", type=int)
        end_line = request.args.get("end_line", type=int)
        reason = request.args.get("reason")
        if not file_path or len(file_path) > 512:
            return jsonify({"error": "file 必填且不能超过 512 字符"}), 400
        snapshot = db.session.get(ProjectSnapshot, run.snapshot_id)
        if snapshot is None:
            return jsonify({"error": "快照不存在"}), 404
        payload = read_code_slice(snapshot, file_path, start_line, end_line, reason)
        return jsonify(payload)
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except CodeSliceForbidden as exc:
        return jsonify({"error": str(exc)}), 403
    except CodeSliceError as exc:
        return jsonify({"error": str(exc)}), 400
