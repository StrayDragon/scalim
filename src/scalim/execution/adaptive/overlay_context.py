from collections.abc import Hashable

from ...typedefs import FieldValue
from ...vendor.compact.typing_extensionsx import override
from ..context import BatchContext


class OverlayBatchContext(BatchContext):
    """用于批次内并行的 `BatchContext` 覆盖层。

    - 读取会回退到基础上下文（只读）。
    - 写入只进入覆盖缓冲区。
    - 删除不会影响基础上下文。
    """

    _base: BatchContext

    def __init__(self, base: BatchContext, *, required_fields: set[str] | None = None) -> None:
        super().__init__(required_fields=required_fields)
        self._base = base

    @override
    def get_field_value(self, field_key: str, row_id: Hashable, default: FieldValue | None = None) -> FieldValue:
        field_data = self._data.get(field_key)
        if field_data is not None and row_id in field_data:
            return field_data.get(row_id, default)
        return self._base.get_field_value(field_key, row_id, default=default)

    @override
    def has_field(self, field_key: str) -> bool:
        return field_key in self._data or self._base.has_field(field_key)

    @override
    def get_field_values_for_row(self, row_id: Hashable, field_keys: list[str]) -> dict[str, FieldValue]:
        return {key: self.get_field_value(key, row_id) for key in field_keys}

    @override
    def get_all_rows_for_field(self, field_key: str) -> set[Hashable]:
        rows = set(self._base.get_all_rows_for_field(field_key))
        overlay_rows = self._data.get(field_key)
        if overlay_rows:
            rows |= set(overlay_rows.keys())
        return rows

    @override
    def get_field_keys(self) -> set[str]:
        keys = set(self._base.get_field_keys())
        keys |= set(self._data.keys())
        return keys

    @override
    def get_field_count(self) -> int:
        return len(self.get_field_keys())

    def drain_overlay(self) -> dict[str, dict[Hashable, FieldValue]]:
        if not self._data:
            return {}
        data: dict[str, dict[Hashable, FieldValue]] = {}
        for field_key in list(self._data.keys()):
            data[field_key] = self._data.pop(field_key)
        return data


__all__ = ["OverlayBatchContext"]
