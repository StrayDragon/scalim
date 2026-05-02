# region imports

from typing import Callable, Dict, Hashable, List, Optional, Sequence, Set, Tuple

from ..typedefs import FieldValue
from ..vendor.compact.typing_extensionsx import override

# endregion


class _DenseFieldStorage:
    """批次字段的 `Dense` 存储表示: `values` + `present` 掩码.

    说明:
    - `present[i]==1` 表示该行有值(即使值为 `None`),`present[i]==0` 表示缺失.
    - 用 `bytearray` 避免缺失哨兵带来的 `pickle` 兼容性问题.
    """

    values: List[FieldValue]
    present: bytearray
    present_count: int

    def __init__(self, row_count: int) -> None:
        self.values = [None] * int(row_count)
        self.present = bytearray(int(row_count))
        self.present_count = 0


class BatchContext:
    _data: Dict[str, Dict[Hashable, FieldValue]]
    _required_fields: Optional[Set[str]]
    _on_field_set: Optional[Callable[[str, Hashable], None]]
    _on_field_set_fields: Optional[Set[str]]
    _disabled_rows: Optional[Set[Hashable]]

    def __init__(
        self,
        required_fields: Optional[Set[str]] = None,
        *,
        on_field_set: Optional[Callable[[str, Hashable], None]] = None,
        on_field_set_fields: Optional[Set[str]] = None,
    ) -> None:
        self._data = {}
        self._required_fields = required_fields
        self._on_field_set = on_field_set
        self._on_field_set_fields = on_field_set_fields
        self._disabled_rows = None

    def set_field_value(self, field_key: str, row_id: Hashable, value: FieldValue) -> None:
        if self._disabled_rows is not None and row_id in self._disabled_rows:
            return

        # 注意: 内存优化 - 剪枝: 只存储需要的字段
        if self._required_fields is not None and field_key not in self._required_fields:
            return

        if field_key not in self._data:
            self._data[field_key] = {}
        self._data[field_key][row_id] = value
        on_field_set = self._on_field_set
        if on_field_set is None:
            return
        on_field_set_fields = self._on_field_set_fields
        if on_field_set_fields is not None and field_key not in on_field_set_fields:
            return
        on_field_set(field_key, row_id)

    def get_field_value(self, field_key: str, row_id: Hashable, default: Optional[FieldValue] = None) -> FieldValue:
        field_data = self._data.get(field_key)
        if field_data is None:
            return default
        return field_data.get(row_id, default)

    def has_field(self, field_key: str) -> bool:
        return field_key in self._data

    def delete_field(self, field_key: str) -> None:
        # 注意: 内存优化 - 及时删除不再需要的字段: 当一个字段的值已经被所有依赖它的字段使用完毕后, 可以调用此方法删除该字段,释放内存
        if field_key in self._data:
            del self._data[field_key]

    def delete_row_from_field(self, field_key: str, row_id: Hashable) -> None:
        """FR023 行级释放: 删除特定行在特定字段中的值.

        `row_id` 为批次内行号(`batch_row_nth`),不是主键.
        触发点:该行在该字段已不再被后续计算/联结使用时调用,用于释放内存.
        """
        field_data = self._data.get(field_key)
        if field_data and row_id in field_data:
            del field_data[row_id]
            if not field_data:
                del self._data[field_key]

    def delete_row_from_all_fields(self, row_id: Hashable, exclude_fields: Optional[Set[str]] = None) -> List[str]:
        """FR023 行级释放: 删除特定行在所有字段中的值,但保留 `exclude_fields` 中的字段.

        `row_id` 为批次内行号(`batch_row_nth`),不是主键.
        触发点:该行已被写出且不再被后续步骤使用时调用,以清理上下文内存.
        """
        exclude = exclude_fields or set()
        released_fields: List[str] = []
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

    def get_field_values_for_row(self, row_id: Hashable, field_keys: List[str]) -> Dict[str, FieldValue]:
        # 注意: 内存优化 - 批量获取减少查找开销
        return {key: self.get_field_value(key, row_id) for key in field_keys}

    def clear(self) -> None:
        # 注意: 内存优化 - 批次结束后清空所有数据
        self._data.clear()
        if self._disabled_rows:
            self._disabled_rows.clear()

    def get_all_rows_for_field(self, field_key: str) -> Set[Hashable]:
        field_data = self._data.get(field_key)
        if field_data is None:
            return set()
        return set(field_data.keys())

    def get_field_keys(self) -> Set[str]:
        return set(self._data.keys())

    def get_field_count(self) -> int:
        return len(self._data)


class DenseBatchContext(BatchContext):
    """针对连续整数 `row_id` 批次的 `BatchContext` `Dense` 优化实现.

    仅用于批次内 `row_id` 为连续 `int` 的场景(例如 `pipeline` 生成的 `range` 行号).
    若需要通用 `row_id`,请使用 `BatchContext`.
    """

    _base_row_id: int
    _row_count: int
    _dense_data: Dict[str, _DenseFieldStorage]

    def __init__(
        self,
        *,
        base_row_id: int,
        row_count: int,
        required_fields: Optional[Set[str]] = None,
        on_field_set: Optional[Callable[[str, Hashable], None]] = None,
        on_field_set_fields: Optional[Set[str]] = None,
    ) -> None:
        super(DenseBatchContext, self).__init__(
            required_fields=required_fields,
            on_field_set=on_field_set,
            on_field_set_fields=on_field_set_fields,
        )
        self._base_row_id = int(base_row_id)
        self._row_count = int(max(0, row_count))
        self._dense_data = {}

    def _idx_of(self, row_id: Hashable) -> Optional[int]:
        if not isinstance(row_id, int):
            return None
        base = self._base_row_id
        row_count = self._row_count
        idx = row_id - base
        if idx < 0 or idx >= row_count:
            return None
        return idx

    def _ensure_storage(self, field_key: str) -> _DenseFieldStorage:
        storage = self._dense_data.get(field_key)
        if storage is None:
            storage = _DenseFieldStorage(self._row_count)
            self._dense_data[field_key] = storage
        return storage

    def dense_base_row_id(self) -> int:
        return int(self._base_row_id)

    def dense_row_count(self) -> int:
        return int(self._row_count)

    def dense_prefill_prepare_storage(
        self,
        field_key: str,
        *,
        row_count: int,
        present_mask: bytes,
    ) -> Optional[List[FieldValue]]:
        """为主数据源预填充准备稠密存储,并返回可写的 `values` 列表.

        说明:
        - 该方法是内部热路径优化支撑,目的是让调用方在不触碰受保护成员的情况下,
          直接写入 `values[idx]` 并一次性设置 `present` 掩码/计数.
        - 若存在 `disabled_rows` 则返回 `None`,让调用方回退到通用 `set_field_value` 逻辑,
          以保证语义一致(按行跳过被禁用行).
        """
        if self._disabled_rows:
            return None

        if self._required_fields is not None and field_key not in self._required_fields:
            return None

        resolved_row_count = int(max(0, min(int(row_count), int(self._row_count))))
        if resolved_row_count <= 0:
            return None

        if len(present_mask) != resolved_row_count:
            msg = "present_mask length mismatch: expected {}, got {}".format(resolved_row_count, len(present_mask))
            raise ValueError(msg)

        storage = self._ensure_storage(field_key)
        storage.present[:resolved_row_count] = present_mask
        storage.present_count = resolved_row_count
        return storage.values

    def dense_on_field_set_callback_for_field(self, field_key: str) -> Optional[Callable[[str, Hashable], None]]:
        on_field_set = self._on_field_set
        if on_field_set is None:
            return None
        on_field_set_fields = self._on_field_set_fields
        if on_field_set_fields is not None and field_key not in on_field_set_fields:
            return None
        return on_field_set

    @override
    def set_field_value(self, field_key: str, row_id: Hashable, value: FieldValue) -> None:
        if self._disabled_rows is not None and row_id in self._disabled_rows:
            return
        if self._required_fields is not None and field_key not in self._required_fields:
            return

        idx = self._idx_of(row_id)
        if idx is None:
            # 该实现仅用于连续 `int row_id`;若不满足条件,让调用方回退到通用实现.
            msg = "`DenseBatchContext` row_id 不在范围内或不是 `int`: {!r}".format(row_id)
            raise ValueError(msg)

        storage = self._ensure_storage(field_key)
        present = storage.present
        if present[idx] == 0:
            present[idx] = 1
            storage.present_count += 1
        storage.values[idx] = value

        on_field_set = self._on_field_set
        if on_field_set is not None:
            on_field_set_fields = self._on_field_set_fields
            if on_field_set_fields is None or field_key in on_field_set_fields:
                on_field_set(field_key, row_id)

    @override
    def get_field_value(self, field_key: str, row_id: Hashable, default: Optional[FieldValue] = None) -> FieldValue:
        storage = self._dense_data.get(field_key)
        if storage is None:
            return default
        idx = self._idx_of(row_id)
        if idx is None:
            return default
        present = storage.present
        if present[idx] == 0:
            return default
        return storage.values[idx]

    @override
    def has_field(self, field_key: str) -> bool:
        return field_key in self._dense_data

    @override
    def delete_field(self, field_key: str) -> None:
        if field_key in self._dense_data:
            del self._dense_data[field_key]

    @override
    def delete_row_from_field(self, field_key: str, row_id: Hashable) -> None:
        storage = self._dense_data.get(field_key)
        if storage is None:
            return
        idx = self._idx_of(row_id)
        if idx is None:
            return
        if storage.present[idx] == 0:
            return
        storage.present[idx] = 0
        storage.values[idx] = None
        storage.present_count -= 1
        if storage.present_count <= 0:
            _ = self._dense_data.pop(field_key, None)

    @override
    def delete_row_from_all_fields(self, row_id: Hashable, exclude_fields: Optional[Set[str]] = None) -> List[str]:
        exclude = exclude_fields or set()
        idx = self._idx_of(row_id)
        if idx is None:
            return []

        released_fields: List[str] = []
        for field_key in list(self._dense_data.keys()):
            if field_key in exclude:
                continue
            storage = self._dense_data[field_key]
            if storage.present[idx] == 0:
                continue
            storage.present[idx] = 0
            storage.values[idx] = None
            storage.present_count -= 1
            released_fields.append(field_key)
            if storage.present_count <= 0:
                _ = self._dense_data.pop(field_key, None)
        return released_fields

    @override
    def get_field_values_for_row(self, row_id: Hashable, field_keys: List[str]) -> Dict[str, FieldValue]:
        return {key: self.get_field_value(key, row_id) for key in field_keys}

    @override
    def clear(self) -> None:
        self._dense_data.clear()
        if self._disabled_rows:
            self._disabled_rows.clear()

    @override
    def get_all_rows_for_field(self, field_key: str) -> Set[Hashable]:
        storage = self._dense_data.get(field_key)
        if storage is None:
            return set()
        out: Set[Hashable] = set()
        base = int(self._base_row_id)
        for idx, present in enumerate(storage.present):
            if present:
                out.add(base + idx)
        return out

    @override
    def get_field_keys(self) -> Set[str]:
        return set(self._dense_data.keys())

    @override
    def get_field_count(self) -> int:
        return len(self._dense_data)


def _try_resolve_dense_range(row_ids: Sequence[Hashable]) -> Optional[Tuple[int, int]]:
    if not row_ids:
        return None
    first = row_ids[0]
    if not isinstance(first, int):
        return None
    base = int(first)
    for idx, row_id in enumerate(row_ids):
        if not isinstance(row_id, int):
            return None
        if int(row_id) != base + int(idx):
            return None
    return base, len(row_ids)


def create_batch_context_for_rows(
    row_ids: Sequence[Hashable],
    *,
    required_fields: Optional[Set[str]] = None,
    on_field_set: Optional[Callable[[str, Hashable], None]] = None,
    on_field_set_fields: Optional[Set[str]] = None,
) -> BatchContext:
    resolved = _try_resolve_dense_range(row_ids)
    if resolved is None:
        return BatchContext(required_fields=required_fields, on_field_set=on_field_set, on_field_set_fields=on_field_set_fields)
    base, row_count = resolved
    return DenseBatchContext(
        base_row_id=base,
        row_count=row_count,
        required_fields=required_fields,
        on_field_set=on_field_set,
        on_field_set_fields=on_field_set_fields,
    )


__all__ = ()
