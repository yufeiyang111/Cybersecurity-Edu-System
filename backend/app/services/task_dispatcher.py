"""Queue boundary for security scan orchestration."""
from __future__ import annotations

from abc import ABC, abstractmethod

from flask import current_app
from redis import Redis
from rq import Queue

from app.services.scan_orchestrator import run_queued_scan_task, run_scan_task


class ScanTaskDispatcher(ABC):
    @abstractmethod
    def enqueue(self, task_id: int) -> str:
        """Schedule a task using only its database identifier."""


class InlineScanTaskDispatcher(ScanTaskDispatcher):
    def enqueue(self, task_id: int) -> str:
        run_scan_task(task_id)
        return f"inline-{task_id}"


class RQScanTaskDispatcher(ScanTaskDispatcher):
    def __init__(self, redis_url: str, queue_name: str) -> None:
        self._queue = Queue(queue_name, connection=Redis.from_url(redis_url))

    def enqueue(self, task_id: int) -> str:
        job = self._queue.enqueue(run_queued_scan_task, task_id)
        return job.id


def get_scan_task_dispatcher() -> ScanTaskDispatcher:
    if current_app.config.get("RQ_ASYNC", False):
        return RQScanTaskDispatcher(
            current_app.config["REDIS_URL"],
            current_app.config["RQ_QUEUE_NAME"],
        )
    return InlineScanTaskDispatcher()
