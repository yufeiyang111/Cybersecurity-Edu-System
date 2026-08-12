# -*- coding: utf-8 -*-
"""T03 并发 Event Writer 测试：多线程写同一 Run，sequence 必须唯一且连续。

使用文件 SQLite（agent_api_app）而不是 :memory:，让多个线程连接共享同一
数据库文件；原子递增依赖 UPDATE agent_runs.last_event_sequence 行级原子性。
"""
from __future__ import annotations

import threading

from app import db
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter

THREADS = 4
EVENTS_PER_THREAD = 25
TOTAL = THREADS * EVENTS_PER_THREAD


def _create_run(application) -> AgentRun:
    with application.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="并发测试",
            mode="baseline",
        )
        db.session.add(run)
        db.session.commit()
        return run.id


def test_concurrent_writers_produce_unique_contiguous_sequence(agent_api_app):
    run_id = _create_run(agent_api_app)
    sequences: list[int] = []
    lock = threading.Lock()
    errors: list[BaseException] = []

    def worker(worker_index: int):
        try:
            with agent_api_app.app_context():
                run = db.session.get(AgentRun, run_id)
                writer = EventWriter()
                for index in range(EVENTS_PER_THREAD):
                    event = writer.emit(
                        run,
                        event_type="warning.raised",
                        payload={"worker": worker_index, "index": index},
                        trace_id=f"t-{worker_index}-{index}",
                    )
                    with lock:
                        sequences.append(event.sequence)
                    db.session.commit()
        except BaseException as exc:  # noqa: BLE001 - 收集线程错误便于断言
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(index,))
        for index in range(THREADS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"并发写入出现异常：{errors[0]!r}"
    assert len(sequences) == TOTAL
    assert sorted(sequences) == list(range(1, TOTAL + 1)), "sequence 必须唯一且连续"

    with agent_api_app.app_context():
        run = db.session.get(AgentRun, run_id)
        assert run.last_event_sequence == TOTAL


def test_sequential_writes_are_contiguous(agent_api_app):
    run_id = _create_run(agent_api_app)
    with agent_api_app.app_context():
        run = db.session.get(AgentRun, run_id)
        writer = EventWriter()
        sequences = []
        for index in range(20):
            event = writer.emit(
                run,
                event_type="budget.updated",
                payload={"index": index},
                trace_id=f"seq-{index}",
            )
            sequences.append(event.sequence)
            db.session.commit()
        assert sequences == list(range(1, 21))
        assert run.last_event_sequence == 20
