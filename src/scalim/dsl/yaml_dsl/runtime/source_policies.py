"""`Source` 缓存与 `rows` 复用策略(`typed`;`Python` 可覆盖 YAML).

与 `sources.*.cache_mode` / `$rows.cache_mode` 拆名拆类型,禁止共用一个平铺 `cache_mode` API 字段.
覆盖优先级:显式 `Python` > YAML 声明 > `builtin` 默认.
"""

from ....typedefs import RowsReuseMode, SourceSpecIrCacheMode
from ....vendor.dataclassesx import dataclass


@dataclass(frozen=True)
class SourceCache:
    """`sources.*.cache_mode` 的 `Python` 覆盖策略."""

    _mode: SourceSpecIrCacheMode = SourceSpecIrCacheMode.NONE

    @classmethod
    def none(cls) -> "SourceCache":
        return cls(_mode=SourceSpecIrCacheMode.NONE)

    @classmethod
    def preload_forever(cls) -> "SourceCache":
        return cls(_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER)

    def __post_init__(self) -> None:
        if not isinstance(self._mode, SourceSpecIrCacheMode):
            msg = "SourceCache._mode must be a SourceSpecIrCacheMode"
            raise TypeError(msg)

    def to_ir_mode(self) -> SourceSpecIrCacheMode:
        return self._mode


@dataclass(frozen=True)
class RowsReuse:
    """`params` 内 `$rows.cache_mode` 的 `Python` 覆盖策略(批次内 `relation` 复用)."""

    _mode: RowsReuseMode = RowsReuseMode.BATCH

    @classmethod
    def batch(cls) -> "RowsReuse":
        return cls(_mode=RowsReuseMode.BATCH)

    @classmethod
    def none(cls) -> "RowsReuse":
        return cls(_mode=RowsReuseMode.NONE)

    def __post_init__(self) -> None:
        if not isinstance(self._mode, RowsReuseMode):
            msg = "RowsReuse._mode must be a RowsReuseMode"
            raise TypeError(msg)

    def to_binding_cache_mode(self) -> str:
        return str(self._mode.value)


__all__ = ("RowsReuse", "SourceCache")
