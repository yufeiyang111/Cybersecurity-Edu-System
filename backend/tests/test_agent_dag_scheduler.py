# -*- coding: utf-8 -*-
"""T06 DAG Scheduler 测试：拓扑无关、多前置、失败传播、SKIPPED 语义。"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanEdge,
    AgentPlanEdgeType,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
)
from app.services.security_agent.planning.scheduler import PlanScheduler


def _make_plan(
    app,
    *,
    node_keys,
    edges,
    statuses=None,
):
    with app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="DAG 测试",
            mode="hybrid",
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective="DAG 测试",
        )
        db.session.add(plan)
        db.session.flush()
        nodes = {}
        for index, key in enumerate(node_keys):
            node = AgentPlanNode(
                plan_id=plan.id,
                node_key=key,
                node_type=AgentPlanNodeType.REPOSITORY_MAPPING.value,
                status=(statuses or {}).get(
                    key, AgentPlanNodeStatus.PENDING.value
                ),
                title=key,
                tool_name="map_repository",
            )
            db.session.add(node)
            db.session.flush()
            nodes[key] = node
        for from_key, to_key in edges:
            db.session.add(
                AgentPlanEdge(
                    plan_id=plan.id,
                    from_node=from_key,
                    to_node=to_key,
                    edge_type=AgentPlanEdgeType.SUCCESS.value,
                )
            )
        db.session.commit()
        plan_id = plan.id
        return plan_id


def _load_plan(app, plan_id):
    from sqlalchemy.orm import selectinload

    with app.app_context():
        return db.session.get(
            AgentPlan,
            plan_id,
            options=[
                selectinload(AgentPlan.nodes),
                selectinload(AgentPlan.edges),
            ],
        )


def test_scheduler_order_independent_of_node_ids(app):
    """节点 ID 顺序与依赖顺序相反时，仍按依赖执行。"""
    plan_id = _make_plan(
        app,
        node_keys=["a", "b"],
        edges=[("b", "a")],
        statuses={"b": AgentPlanNodeStatus.SUCCEEDED.value},
    )
    plan = _load_plan(app, plan_id)
    ready = PlanScheduler().ready_nodes(plan)
    assert [node.node_key for node in ready] == ["a"]

    plan_id = _make_plan(
        app,
        node_keys=["a", "b"],
        edges=[("b", "a")],
        statuses={"a": AgentPlanNodeStatus.SUCCEEDED.value},
    )
    plan = _load_plan(app, plan_id)
    ready = PlanScheduler().ready_nodes(plan)
    assert [node.node_key for node in ready] == ["b"]


def test_multi_parent_requires_all_succeeded(app):
    plan_id = _make_plan(
        app,
        node_keys=["x", "y", "z"],
        edges=[("x", "z"), ("y", "z")],
        statuses={
            "x": AgentPlanNodeStatus.SUCCEEDED.value,
            "y": AgentPlanNodeStatus.PENDING.value,
        },
    )
    plan = _load_plan(app, plan_id)
    ready = PlanScheduler().ready_nodes(plan)
    assert [node.node_key for node in ready] == ["y"], "y 自身无依赖可执行"
    assert "z" not in [node.node_key for node in ready], "z 的多前置未全部满足"
    with app.app_context():
        node = AgentPlanNode.query.filter_by(
            plan_id=plan_id, node_key="y"
        ).one()
        node.status = AgentPlanNodeStatus.SUCCEEDED.value
        db.session.commit()
    plan = _load_plan(app, plan_id)
    assert [node.node_key for node in PlanScheduler().ready_nodes(plan)] == ["z"]


def test_failed_parent_blocks_descendant(app):
    plan_id = _make_plan(
        app,
        node_keys=["a", "b"],
        edges=[("a", "b")],
        statuses={"a": AgentPlanNodeStatus.FAILED.value},
    )
    plan = _load_plan(app, plan_id)
    scheduler = PlanScheduler()
    assert [node.node_key for node in scheduler.ready_nodes(plan)] == []
    blocked = scheduler.blocked_nodes(plan)
    assert blocked == ["b"]


def test_failed_node_never_satisfies_dependency(app):
    plan_id = _make_plan(
        app,
        node_keys=["a", "b"],
        edges=[("a", "b")],
        statuses={"a": AgentPlanNodeStatus.FAILED.value},
    )
    plan = _load_plan(app, plan_id)
    assert PlanScheduler().ready_nodes(plan) == []


def test_skipped_satisfies_dependency_only_when_allowed(app):
    plan_id = _make_plan(
        app,
        node_keys=["a", "b"],
        edges=[("a", "b")],
        statuses={"a": AgentPlanNodeStatus.SKIPPED.value},
    )
    plan = _load_plan(app, plan_id)
    strict = PlanScheduler(allow_skipped_to_satisfy=False)
    assert strict.ready_nodes(plan) == []
    permissive = PlanScheduler(allow_skipped_to_satisfy=True)
    assert [node.node_key for node in permissive.ready_nodes(plan)] == ["b"]


def test_ready_set_is_deterministic(app):
    plan_id = _make_plan(
        app,
        node_keys=["c", "a", "b"],
        edges=[],
        statuses={},
    )
    plan = _load_plan(app, plan_id)
    keys = [node.node_key for node in PlanScheduler().ready_nodes(plan)]
    id_order = [
        node.node_key
        for node in sorted(plan.nodes, key=lambda item: item.id)
    ]
    assert keys == id_order, "READY 集合必须按节点 ID 确定性排序"


def test_already_running_or_succeeded_nodes_not_ready(app):
    plan_id = _make_plan(
        app,
        node_keys=["a", "b"],
        edges=[],
        statuses={
            "a": AgentPlanNodeStatus.SUCCEEDED.value,
            "b": AgentPlanNodeStatus.RUNNING.value,
        },
    )
    plan = _load_plan(app, plan_id)
    assert PlanScheduler().ready_nodes(plan) == []


def test_canceled_parent_blocks_descendant(app):
    plan_id = _make_plan(
        app,
        node_keys=["a", "b"],
        edges=[("a", "b")],
        statuses={"a": AgentPlanNodeStatus.CANCELED.value},
    )
    plan = _load_plan(app, plan_id)
    assert PlanScheduler().blocked_nodes(plan) == ["b"]
