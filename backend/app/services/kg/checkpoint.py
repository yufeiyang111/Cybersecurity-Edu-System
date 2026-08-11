# -*- coding: utf-8 -*-
"""
LLM 图谱构建断点存储（Checkpoint Store）

任务按文档分片抽取，每片完成后把结果原子落盘：
- 已完成的文档 id 集合（resume 时跳过）
- 已抽取的三元组（追加式）
- token 用量

额度耗尽/任务中断后，断点文件保留；恢复任务时读取断点继续，
已消耗的 LLM 调用不浪费。
"""
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 断点文件版本（数据结构变更时递增，避免读取旧格式）
CHECKPOINT_VERSION = 1


class CheckpointStore:
    """图谱抽取断点存储（JSON 原子写）。"""

    def __init__(self, path: str) -> None:
        self.path = path

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def load(self) -> Dict[str, Any]:
        """读取断点；文件不存在/损坏返回空断点。"""
        if not os.path.exists(self.path):
            return self._empty()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != CHECKPOINT_VERSION:
                logger.warning("断点版本不匹配，忽略旧断点: %s", self.path)
                return self._empty()
            data.setdefault("completed_docs", [])
            data.setdefault("triples", [])
            data.setdefault("usage", {"prompt_tokens": 0, "completion_tokens": 0})
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("断点读取失败（忽略）: %s", exc)
            return self._empty()

    def save(
        self,
        completed_docs: List[str],
        triples: List[Dict[str, Any]],
        usage: Dict[str, int],
    ) -> None:
        """原子写断点（先写临时文件再 rename，避免写一半损坏）。"""
        payload = {
            "version": CHECKPOINT_VERSION,
            "completed_docs": completed_docs,
            "triples": triples,
            "usage": usage,
        }
        directory = os.path.dirname(self.path)
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            os.replace(tmp_path, self.path)
        except Exception:  # noqa: BLE001
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def clear(self) -> None:
        """任务全部完成后删除断点。"""
        if os.path.exists(self.path):
            try:
                os.remove(self.path)
            except OSError as exc:
                logger.warning("断点删除失败: %s", exc)

    @staticmethod
    def _empty() -> Dict[str, Any]:
        return {
            "version": CHECKPOINT_VERSION,
            "completed_docs": [],
            "triples": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
