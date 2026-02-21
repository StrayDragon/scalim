# region imports

from collections.abc import Callable, Hashable

from ..typedefs import FieldValue

# endregion


class BatchContext:
    _data: dict[str, dict[Hashable, FieldValue]]
    _required_fields: set[str] | None
    _on_field_set: Callable[[str, Hashable], None] | None
    _disabled_rows: set[Hashable] | None

    def __init__(
        self,
        required_fields: set[str] | None = None,
        *,
        on_field_set: Callable[[str, Hashable], None] | None = None,
    ) -> None:
        self._data = {}
        self._required_fields = required_fields
        self._on_field_set = on_field_set
        self._disabled_rows = None

    def set_field_value(self, field_key: str, row_id: Hashable, value: FieldValue) -> None:
        if self._disabled_rows is not None and row_id in self._disabled_rows:
            return

        # NOTE: 内存优化 - 剪枝: 只存储需要的字段
        if self._required_fields is not None and field_key not in self._required_fields:
            return

        if field_key not in self._data:
            self._data[field_key] = {}
        self._data[field_key][row_id] = value
        if self._on_field_set is not None:
            self._on_field_set(field_key, row_id)

    def get_field_value(self, field_key: str, row_id: Hashable, default: FieldValue | None = None) -> FieldValue:
        field_data = self._data.get(field_key)
        if field_data is None:
            return default
        return field_data.get(row_id, default)

    def has_field(self, field_key: str) -> bool:
        return field_key in self._data

    def delete_field(self, field_key: str) -> None:
        # NOTE: 内存优化 - 及时删除不再需要的字段: 当一个字段的值已经被所有依赖它的字段使用完毕后, 可以调用此方法删除该字段,释放内存
        if field_key in self._data:
            del self._data[field_key]

    def delete_row_from_field(self, field_key: str, row_id: Hashable) -> None:
        """FR023 行级释放: 删除特定行在特定字段中的值.

        row_id 为批次内行号(batch_row_nth),不是主键.
        触发点:该行在该字段已不再被后续计算/联结使用时调用,用于释放内存.
        """
        field_data = self._data.get(field_key)
        if field_data and row_id in field_data:
            del field_data[row_id]
            if not field_data:
                del self._data[field_key]

    def delete_row_from_all_fields(self, row_id: Hashable, exclude_fields: set[str] | None = None) -> list[str]:
        """FR023 行级释放: 删除特定行在所有字段中的值,但保留 exclude_fields 中的字段.

        row_id 为批次内行号(batch_row_nth),不是主键.
        触发点:该行已被写出且不再被后续步骤使用时调用,以清理上下文内存.
        """
        exclude = exclude_fields or set()
        released_fields: list[str] = []
        for field_key in list(self._data.keys()):
            if field_key not in exclude:
                field_data = self._data.get(field_key)
                if field_data and row_id in field_data:
                    del field_data[row_id]
                    released_fields.append(field_key)
                    if not field_data:
                        del self._data[field_key]
        return released_fields

    def disable_row(self, row_id: Hashable) -> None:
        if self._disabled_rows is None:
            self._disabled_rows = set()
        self._disabled_rows.add(row_id)

    def get_field_values_for_row(self, row_id: Hashable, field_keys: list[str]) -> dict[str, FieldValue]:
        # NOTE: 内存优化 - 批量获取减少查找开销
        return {key: self.get_field_value(key, row_id) for key in field_keys}

    def clear(self) -> None:
        # NOTE: 内存优化 - 批次结束后清空所有数据
        self._data.clear()
        if self._disabled_rows:
            self._disabled_rows.clear()

    def get_all_rows_for_field(self, field_key: str) -> set[Hashable]:
        field_data = self._data.get(field_key)
        if field_data is None:
            return set()
        return set(field_data.keys())

    def get_field_keys(self) -> set[str]:
        return set(self._data.keys())

    def get_field_count(self) -> int:
        return len(self._data)
