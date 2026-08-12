# -*- coding: utf-8 -*-
"""工具 Deadline（T05，spec §10.3）：硬截止时间与取消轮询。

线程模式无法安全中止的工具必须自行轮询 ctx.cancelled() 与 deadline；
Executor 在结果落库前做硬检查，超时后的迟到结果不得写入成功状态。
"""
from __future__ import annotations

import time
from dataclasses import dataclass


class DeadlineExceeded(RuntimeError):
    """工具执行已超过硬截止时间。"""


@dataclass(frozen=True)
class Deadline:
    """基于 time.monotonic 的绝对截止时间。"""

    epoch: float

    def remaining_seconds(self) -> float:
        return max(0.0, self.epoch - time.monotonic())

    def expired(self) -> bool:
        return time.monotonic() > self.epoch

    def ensure_not_expired(self) -> None:
        if self.expired():
            raise DeadlineExceeded("工具执行已超过硬截止时间")


def deadline_for(timeout_seconds: int | float) -> Deadline:
    """按超时秒数构造截止时间。"""
    timeout = max(0.0, float(timeout_seconds or 0))
    return Deadline(epoch=time.monotonic() + timeout)
