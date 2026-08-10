"""Python repository mapper tests: AST-based symbol/route/call extraction."""
from __future__ import annotations

from app.services.project_security_graph.contracts import GraphBuildBudget
from app.services.project_security_graph.python_mapper import map_python_file

SAMPLE = '''"""sample service."""
from app.models.user import User
from flask import Blueprint, request

bp = Blueprint("sample", __name__)

class UserRepository:
    def find_by_id(self, user_id):
        return User.query.get(user_id)

class UserService:
    def __init__(self, repo):
        self.repo = repo

    def get_user(self, user_id):
        return self.repo.find_by_id(user_id)

class ApiMiddleware:
    def handle(self):
        pass

@bp.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    service = UserService(UserRepository())
    return service.get_user(user_id)

def unused_helper():
    return "x"
'''


def test_python_mapper_emits_file_and_symbol_nodes():
    nodes, edges = map_python_file("app/service.py", SAMPLE, GraphBuildBudget())
    keys = {node.node_key for node in nodes}
    assert "py:file:app/service.py" in keys
    assert "py:class:app/service.py:UserRepository" in keys
    assert "py:func:app/service.py:get_user" in keys
    assert "py:route:app/service.py:/api/users/<int:user_id>:GET" in keys


def test_python_mapper_infers_class_types():
    nodes, _ = map_python_file("app/service.py", SAMPLE, GraphBuildBudget())
    by_key = {node.node_key: node.node_type for node in nodes}
    assert by_key["py:class:app/service.py:UserRepository"] == "repository"
    assert by_key["py:class:app/service.py:UserService"] == "service"
    assert by_key["py:class:app/service.py:ApiMiddleware"] == "middleware"


def test_python_mapper_class_inheriting_model_is_model():
    source = "from app import db\nclass FindingModel(db.Model):\n    id = 1\n"
    nodes, _ = map_python_file("m.py", source, GraphBuildBudget())
    model_nodes = [
        node for node in nodes if node.node_key == "py:class:m.py:FindingModel"
    ]
    assert model_nodes[0].node_type == "model"


def test_python_mapper_route_handles_edge():
    _, edges = map_python_file("app/service.py", SAMPLE, GraphBuildBudget())
    route_edges = [
        edge
        for edge in edges
        if edge.edge_type == "route_handles"
        and edge.source_key.startswith("py:route:app/service.py")
    ]
    assert len(route_edges) == 1
    assert route_edges[0].target_key == "py:func:app/service.py:get_user"
    assert route_edges[0].confidence == "exact"


def test_python_mapper_same_file_call_edges():
    _, edges = map_python_file("app/service.py", SAMPLE, GraphBuildBudget())
    call_edges = [
        edge
        for edge in edges
        if edge.edge_type == "calls" and edge.confidence == "exact"
    ]
    assert any(
        edge.source_key == "py:func:app/service.py:UserService.get_user"
        and edge.target_key == "py:func:app/service.py:UserRepository.find_by_id"
        for edge in call_edges
    )


def test_python_mapper_ambiguous_calls_are_skipped():
    source = (
        "class A:\n"
        "    def run(self):\n"
        "        return self.do()\n"
        "    def do(self):\n"
        "        return 1\n"
        "class B:\n"
        "    def run(self):\n"
        "        return self.do()\n"
        "    def do(self):\n"
        "        return 2\n"
    )
    _, edges = map_python_file("dup.py", source, GraphBuildBudget())
    call_edges = [
        edge for edge in edges if edge.edge_type == "calls" and edge.confidence == "exact"
    ]
    assert len(call_edges) == 2
    assert any(
        edge.source_key == "py:func:dup.py:A.run"
        and edge.target_key == "py:func:dup.py:A.do"
        for edge in call_edges
    )
    assert any(
        edge.source_key == "py:func:dup.py:B.run"
        and edge.target_key == "py:func:dup.py:B.do"
        for edge in call_edges
    )


def test_python_mapper_syntax_error_file_degrades_gracefully():
    nodes, edges = map_python_file("broken.py", "def broken(:\n", GraphBuildBudget())
    assert len(nodes) == 0
    assert len(edges) == 0


def test_python_mapper_contains_edges_for_members():
    _, edges = map_python_file("app/service.py", SAMPLE, GraphBuildBudget())
    contains = [
        edge for edge in edges if edge.edge_type == "contains"
    ]
    assert any(
        edge.source_key == "py:file:app/service.py"
        and edge.target_key == "py:class:app/service.py:UserService"
        for edge in contains
    )
    assert any(
        edge.source_key == "py:class:app/service.py:UserService"
        and edge.target_key == "py:func:app/service.py:UserService.get_user"
        for edge in contains
    )
