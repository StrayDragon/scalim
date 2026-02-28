# region imports

import time
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

# endregion


@dataclass(frozen=True)
class Event:
    """观察事件统一封装.

    说明:
        - `seq` 在同一个 `ObserverManager`/`run_id` 内单调递增,不是全局顺序.
        - 在线程/进程/异步并发中,`seq` 仅保证局部有序,事件可能交错.
        - 需要并发上下文时,请通过 `meta` 传递 `worker_id`、`batch_num` 等信息.
    """

    event_type: str
    """事件类型名称 (来自 `events/catalog.py` 的稳定标识)."""

    timestamp: float
    """事件发出时的 UNIX 时间戳 (秒)."""

    run_id: str
    """一次执行的运行标识."""

    payload: Any
    """事件负载 (数据类或原始数据)."""

    meta: dict[str, Any] = field(default_factory=dict)
    """可选元数据,用于传输/调试/并发上下文提示."""

    seq: int = 0
    """发送端序号 (0 表示未设置; 由 ObserverManager 填充)."""

    def to_dict(self) -> dict[str, Any]:
        payload = self.payload
        if is_dataclass(payload) and not isinstance(payload, type):
            payload = asdict(payload)
        result: dict[str, Any] = {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "payload": payload,
            "meta": dict(self.meta) if self.meta else {},
            "seq": self.seq,
        }
        return result


def now_ts() -> float:
    return time.time()


def generate_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{int(time.time() * 1000)}"


__all__ = [
    "Event",
    "generate_run_id",
    "now_ts",
]
