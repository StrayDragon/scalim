from collections.abc import Hashable, Sequence
from typing import TYPE_CHECKING

from ....sinks.sink_base import IRowSink
from ...context import BatchContext
from ...executor.runtime.runtime import ExecutionRuntime

if TYPE_CHECKING:
    from ....typedefs import RowData


class RowEmissionCoordinator:
    _runtime: ExecutionRuntime
    _sink: IRowSink
    _context: BatchContext
    _target_fields: list[str]
    _target_fields_set: set[str]
    _global_ready_fields: set[str]
    _required_non_global_targets: int
    _ready_counts: dict[Hashable, int]
    _write_row_ids: list[Hashable]
    _next_write_idx: int
    _next_release_idx: int
    _allow_release: bool
    _rows_to_remove: set[Hashable]
    _retained_fields: set[str]

    def __init__(
        self,
        *,
        runtime: ExecutionRuntime,
        sink: IRowSink,
        target_fields: Sequence[str],
        retained_fields: set[str],
        global_ready_fields: set[str],
        allow_release: bool,
    ) -> None:
        self._runtime = runtime
        self._sink = sink
        self._context = BatchContext()
        self._target_fields = list(target_fields)
        self._target_fields_set = set(self._target_fields)
        self._global_ready_fields = set(global_ready_fields)
        self._required_non_global_targets = max(0, len(self._target_fields) - len(self._global_ready_fields))
        self._ready_counts = {}
        self._write_row_ids = []
        self._next_write_idx = 0
        self._next_release_idx = 0
        self._allow_release = bool(allow_release)
        self._rows_to_remove = set()
        self._retained_fields = set(retained_fields)

    def attach_context(self, context: BatchContext) -> None:
        self._context = context

    def set_write_order(self, write_row_ids: list[Hashable]) -> None:
        self._write_row_ids = list(write_row_ids)

    def on_field_set(self, field_key: str, row_id: Hashable) -> None:
        if field_key not in self._target_fields_set:
            return
        if field_key in self._global_ready_fields:
            return

        self._ready_counts[row_id] = int(self._ready_counts.get(row_id, 0)) + 1
        self.flush_ready_rows()

    def enable_release(self) -> None:
        if self._allow_release:
            return
        self._allow_release = True
        self._maybe_release_written_prefix()

    def drain_rows_to_remove(self) -> set[Hashable]:
        if not self._rows_to_remove:
            return set()
        drained = set(self._rows_to_remove)
        self._rows_to_remove.clear()
        return drained

    def flush_ready_rows(self) -> None:
        if not self._write_row_ids:
            return

        while self._next_write_idx < len(self._write_row_ids):
            row_id = self._write_row_ids[self._next_write_idx]
            if not self._is_row_ready(row_id):
                break
            self._write_row(row_id=row_id, row_index=self._next_write_idx)
            self._next_write_idx += 1
            self._maybe_release_written_prefix()

    def finalize(self) -> None:
        self.enable_release()
        self.flush_ready_rows()
        while self._next_write_idx < len(self._write_row_ids):
            row_id = self._write_row_ids[self._next_write_idx]
            self._write_row(row_id=row_id, row_index=self._next_write_idx)
            self._next_write_idx += 1
            self._maybe_release_written_prefix()

    def _is_row_ready(self, row_id: Hashable) -> bool:
        if self._required_non_global_targets <= 0:
            return True
        return int(self._ready_counts.get(row_id, 0)) >= int(self._required_non_global_targets)

    def _write_row(self, *, row_id: Hashable, row_index: int) -> None:
        row: RowData = self._context.get_field_values_for_row(row_id, self._target_fields)
        self._sink.write_row(row)
        self._runtime.instrumentation.emit_row_write(
            row_id=row_id,
            field_count=len(row),
            batch_num=self._runtime.batch_num,
            row_index=int(row_index),
        )

    def _maybe_release_written_prefix(self) -> None:
        if not self._allow_release:
            return

        while self._next_release_idx < self._next_write_idx:
            row_id = self._write_row_ids[self._next_release_idx]
            released_fields = self._context.delete_row_from_all_fields(row_id, exclude_fields=self._retained_fields)
            self._context.disable_row(row_id)
            self._runtime.instrumentation.emit_row_release(
                row_id=row_id,
                released_fields=released_fields,
                retained_fields=sorted(self._retained_fields),
                batch_num=self._runtime.batch_num,
            )
            self._rows_to_remove.add(row_id)
            self._next_release_idx += 1


__all__ = [
    "RowEmissionCoordinator",
]
