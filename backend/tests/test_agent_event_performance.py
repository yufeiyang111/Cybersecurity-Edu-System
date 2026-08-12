# -*- coding: utf-8 -*-
"""T13 性能测试：并发 Event Writer 无重复序列、Snapshot 规模基线。"""
from __future__ import annotations

import threading
import time

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.event_writer import EventWriter
from app.services.security_agent.timeline.snapshot_service import SnapshotService

WRITERS = 4
EVENTS_PER_WRITER = 50
TOTAL = WRITERS * EVENTS_PER_WRITER


def test_concurrent_event_writers_no_duplicate_sequence(agent_api_app):
    with agent_api_app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="性能测试",
            mode="baseline",
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    sequences: list[int] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(index: int):
        try:
            with agent_api_app.app_context():
                run = db.session.get(AgentRun, run_id)
                writer = EventWriter()
                for offset in range(EVENTS_PER_WRITER):
                    event = writer.emit(
                        run,
                        event_type="warning.raised",
                        payload={"w": index, "i": offset},
                        trace_id=f"perf-{index}-{offset}",
                    )
                    with lock:
                        sequences.append(event.sequence)
                    db.session.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    started = time.monotonic()
    threads = [
        threading.Thread(target=worker, args=(index,))
        for index in range(WRITERS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.monotonic() - started

    assert not errors, f"并发写入异常：{errors[0]!r}"
    assert len(sequences) == TOTAL
    assert sorted(sequences) == list(range(1, TOTAL + 1)), "序列必须唯一且连续"
    with agent_api_app.app_context():
        run = db.session.get(AgentRun, run_id)
        assert run.last_event_sequence == TOTAL
    print(f"concurrent writers: {TOTAL} events in {elapsed:.2f}s")


def test_snapshot_builds_with_many_events(agent_api_app):
    with agent_api_app.app_context():
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text="快照规模测试",
            mode="baseline",
        )
        db.session.add(run)
        db.session.flush()
        writer = EventWriter()
        batch_size = 200
        for index in range(batch_size):
            writer.emit(
                run,
                event_type="item.observation.created",
                item_id=f"obs-{index}",
                payload={"summary": f"观察 {index}"},
                trace_id=f"snap-{index}",
            )
        db.session.commit()
        run_id = run.id

        started = time.monotonic()
        snapshot = SnapshotService().build_snapshot(run_id)
        elapsed = time.monotonic() - started
        assert snapshot["snapshot_watermark"] == batch_size
        assert len(snapshot["events"]) == batch_size
        print(f"snapshot {batch_size} events in {elapsed * 1000:.1f}ms")
