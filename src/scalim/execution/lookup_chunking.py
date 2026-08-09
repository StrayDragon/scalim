"""`Keys` 模式 `LoadRef` 分片策略(`typed` `oneof`;`Python` `SSOT`).

YAML `sources.*.lookup_chunk_size` 已迁出:通过 `DemandRunRuntimeOptions.lookup_chunking` 配置.
片间并行仅允许挂在 `sized(...)` 上,且仍须 `parallel_mode=adaptive` 等既有护栏.
"""

from typing import Optional

from ..vendor.dataclassesx import dataclass


def normalize_optional_max_chunk_workers(workers: Optional[int], *, label: str) -> Optional[int]:
    """校验并规范化可选的 `max_chunk_workers`(>=1 的 `int`,或 `None`)."""
    if workers is None:
        return None
    if isinstance(workers, bool) or not isinstance(workers, int):
        msg = "{} must be an int or None".format(label)
        raise TypeError(msg)
    if int(workers) < 1:
        msg = "{} must be >= 1 when provided".format(label)
        raise ValueError(msg)
    return int(workers)


@dataclass(frozen=True)
class LookupChunking:
    """`Keys` 分片策略.

    使用工厂构造:
    - `LookupChunking.off()`: 不分片
    - `LookupChunking.sized(size=..., parallel=..., max_chunk_workers=...)`: 按 `size` 分片;
      `parallel=True` 时允许片间并行(仅 `sized` 可表达)
    """

    size: Optional[int] = None
    parallel: bool = False
    max_chunk_workers: Optional[int] = None
    _kind: str = "off"

    @classmethod
    def off(cls) -> "LookupChunking":
        return cls(size=None, parallel=False, max_chunk_workers=None, _kind="off")

    @classmethod
    def sized(
        cls,
        size: int,
        *,
        parallel: bool = False,
        max_chunk_workers: Optional[int] = None,
    ) -> "LookupChunking":
        if isinstance(size, bool) or not isinstance(size, int):
            msg = "LookupChunking.sized(size=...) must be an int >= 1"
            raise TypeError(msg)
        if int(size) < 1:
            msg = "LookupChunking.sized(size=...) must be >= 1"
            raise ValueError(msg)
        workers = normalize_optional_max_chunk_workers(
            max_chunk_workers,
            label="LookupChunking.sized(max_chunk_workers=...)",
        )
        return cls(size=int(size), parallel=bool(parallel), max_chunk_workers=workers, _kind="sized")

    def __post_init__(self) -> None:
        kind = str(self._kind or "").strip() or "off"
        if kind not in ("off", "sized"):
            msg = "LookupChunking._kind must be 'off' or 'sized'"
            raise ValueError(msg)
        object.__setattr__(self, "_kind", kind)

        if kind == "off":
            if self.size is not None or self.parallel or self.max_chunk_workers is not None:
                msg = "LookupChunking.off() must not set size/parallel/max_chunk_workers; use sized(...)"
                raise ValueError(msg)
            return

        if self.size is None or int(self.size) < 1:
            msg = "LookupChunking.sized requires size >= 1"
            raise ValueError(msg)
        if not isinstance(self.parallel, bool):
            msg = "LookupChunking.parallel must be a boolean"
            raise TypeError(msg)
        object.__setattr__(
            self,
            "max_chunk_workers",
            normalize_optional_max_chunk_workers(
                self.max_chunk_workers,
                label="LookupChunking.max_chunk_workers",
            ),
        )

    def is_off(self) -> bool:
        return self._kind == "off"

    def is_sized(self) -> bool:
        return self._kind == "sized"

    def effective_chunk_size(self) -> Optional[int]:
        """写入 `SourceIr.lookup_chunk_size` 的有效值;`off` → `None`."""
        if self.is_off():
            return None
        return int(self.size) if self.size is not None else None

    def wants_parallel(self) -> bool:
        return self.is_sized() and bool(self.parallel)


__all__ = ("LookupChunking", "normalize_optional_max_chunk_workers")
