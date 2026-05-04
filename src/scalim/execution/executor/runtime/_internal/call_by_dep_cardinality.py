import os
from typing import Any, Dict, Optional, Set, Tuple

_ENV_ENABLE = "SCALIM_PROBE_CALL_BY_DEP_CARDINALITY"


class CallByDepCardinalityStats:
    """统计(近似) `ctx-free call_by` 字段的依赖元组去重数量.

    隐私/安全契约:
    - 不保存依赖值本身.
    - 仅保存 `hash(dep_args)` 的整数值用于去重探测.
    """

    field_key: str
    max_unique: int
    call_count: int
    hashable_count: int
    unhashable_count: int
    unique_hashes: Set[int]
    unique_overflow: bool

    def __init__(self, field_key: str, *, max_unique: int) -> None:
        self.field_key = str(field_key)
        self.max_unique = int(max_unique)
        self.call_count = 0
        self.hashable_count = 0
        self.unhashable_count = 0
        self.unique_hashes = set()
        self.unique_overflow = False

    def record(self, dep_args: Tuple[Any, ...]) -> None:
        self.call_count += 1
        if self.unique_overflow:
            return
        try:
            h = hash(dep_args)
        except TypeError:
            self.unhashable_count += 1
            return
        self.hashable_count += 1
        self.unique_hashes.add(int(h))
        if len(self.unique_hashes) >= self.max_unique:
            self.unique_overflow = True

    def to_dict(self) -> Dict[str, Any]:
        unique = len(self.unique_hashes)
        hashable = self.hashable_count
        repeat_rate = None
        if hashable > 0:
            repeat_rate = round(1.0 - (float(unique) / float(hashable)), 6)
        return {
            "field_key": self.field_key,
            "call_count": int(self.call_count),
            "hashable_count": int(hashable),
            "unhashable_count": int(self.unhashable_count),
            "unique_hashes": int(unique),
            "unique_overflow": bool(self.unique_overflow),
            "repeat_rate": repeat_rate,
            "max_unique": int(self.max_unique),
        }


class CallByDepCardinalityCollector:
    """单次运行内的 `ctx-free call_by` 依赖元组去重统计器(内存有上限)."""

    max_unique: int
    stats_by_field: Dict[str, CallByDepCardinalityStats]

    def __init__(self, *, max_unique: int) -> None:
        self.max_unique = int(max_unique)
        self.stats_by_field = {}

    def get_or_create(self, field_key: str) -> CallByDepCardinalityStats:
        key = str(field_key)
        stat = self.stats_by_field.get(key)
        if stat is not None:
            return stat
        stat = CallByDepCardinalityStats(key, max_unique=self.max_unique)
        self.stats_by_field[key] = stat
        return stat

    def record(self, *, field_key: str, dep_args: Tuple[Any, ...]) -> None:
        self.get_or_create(field_key).record(dep_args)

    def build_summary(self, *, top_n: int = 20) -> Dict[str, Any]:
        # 先按 `call_count` 降序, 再按 `unique` 升序 (越小越可能可缓存).
        stats = list(self.stats_by_field.values())
        stats.sort(key=lambda s: (-int(s.call_count), len(s.unique_hashes)))
        if top_n > 0:
            stats = stats[: int(top_n)]
        return {
            "enabled": True,
            "max_unique": int(self.max_unique),
            "fields": [s.to_dict() for s in stats],
        }


def build_call_by_dep_cardinality_collector() -> Optional[CallByDepCardinalityCollector]:
    raw = (os.environ.get(_ENV_ENABLE) or "").strip()
    if not raw:
        return None
    max_unique = 8192
    try:
        max_unique = int(raw)
    except ValueError:
        max_unique = 8192
    if max_unique <= 0:
        return None
    return CallByDepCardinalityCollector(max_unique=max_unique)


__all__ = ()
