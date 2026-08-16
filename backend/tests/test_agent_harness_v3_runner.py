# -*- coding: utf-8 -*-
"""Harness V3 运行器分流测试。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.security_agent.artifact_service import ArtifactService
from app.services.security_agent.checkpoint_service import CheckpointService
from app.services.security_agent.event_service import EventService
from app.services.security_agent.runner import InlinePlanRunner
from app.services.security_agent.state_machine import AgentStateMachine

from test_agent_harness_v3_deep_review import _make_v3_run


def test_inline_runner_routes_v3_hybrid_and_deep_runs_to_coordinator(app, tmp_path: Path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        runner = InlinePlanRunner(
            state=AgentStateMachine(),
            events=EventService(),
            artifacts=ArtifactService(),
            checkpoints=CheckpointService(),
        )
        with patch(
            "app.services.security_agent.harness_v3.coordinator.HarnessV3Coordinator"
        ) as coordinator_cls, patch(
            "app.services.security_agent.loop.engine.AgentLoopEngine.run_until_interrupt"
        ) as legacy_loop:
            runner.run(run.id, "v3-runner-route", app)

    coordinator_cls.return_value.run_hybrid_or_deep.assert_called_once_with(
        run.id,
        "v3-runner-route",
    )
    legacy_loop.assert_not_called()
