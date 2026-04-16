"""`workflow` 阶段调度性能印象示例的 `loader` 集合.

说明:
- 这些 `loader` 用 `sleep` 来放大调度差异,便于在 `notebook` 中直观看到 `pipeline` 与 `stage_barrier` 的对比.
- 该文件属于用户材料(`notebooks/`),仅依赖稳定入口,避免引用内部实现路径.
"""

import time
from typing import Iterable, Mapping


def _sleep_rows(seconds: float) -> Iterable[Mapping[str, object]]:
    time.sleep(float(seconds))
    return [{"order_id": 1}]


def load_orders_fast() -> Iterable[Mapping[str, object]]:
    return _sleep_rows(0.05)


def load_orders_medium() -> Iterable[Mapping[str, object]]:
    return _sleep_rows(0.10)


def load_orders_slow() -> Iterable[Mapping[str, object]]:
    return _sleep_rows(0.40)
