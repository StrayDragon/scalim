"""流式列式 `Excel` 写出器(可选接入):行字段齐备即刷入 `write_only` `sheet`.

用于降低宽表 `pre_close` 驻留;默认请继续使用 `ColumnExcelSink`.
运行时需兼容 `Python 3.6`.
"""

import logging
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Hashable, List, Optional, Sequence, Set, Type

from ..._internal.loggingx import prefix
from ..._internal.utils.excel import escape_excel_formula
from ..._internal.utils.openpyxl_helpers import (
    best_effort_close_write_only_workbook_worksheets,
    save_openpyxl_workbook_atomic,
)
from ...typedefs import CellValue, RowData, SinkRowKeySeq
from ...vendor.compact.importlibx import require_optional_dependency
from ...vendor.compact.typing_extensionsx import Self, override
from .accept_types import (
    SinkTypePrecheck,
    ensure_sink_accepted_cell,
    is_excel_accepted_cell,
    require_sink_type_precheck,
)
from .base import ColumnBatch, ColumnValues, IColumnSink, exit_sink

if TYPE_CHECKING:
    import types

_LOGGER = logging.getLogger("scalim.sinks.streaming_column_excel")
_SINKS_PREFIX = prefix("sinks")

STREAMING_COLUMN_EXCEL_SINK_SAVE_FAILED = _SINKS_PREFIX + "StreamingColumnExcelSink 保存失败"
STREAMING_COLUMN_EXCEL_SINK_SAVE_FAILED_LOG = STREAMING_COLUMN_EXCEL_SINK_SAVE_FAILED + ": %s"


def _default_workbook_factory(*args: Any, **kwargs: Any) -> Any:
    openpyxl_mod: Any = require_optional_dependency("openpyxl", context="scalim.sinks")
    workbook_cls: Any = openpyxl_mod.Workbook
    return workbook_cls(*args, **kwargs)


Workbook: Any = _default_workbook_factory


class StreamingColumnExcelSink(IColumnSink):
    """流式列式 `Excel` 写入器(可选接入):行字段齐备即 `append` 并释放行缓冲.

    与 `ColumnExcelSink` 的差异:
    - 首次 `set_row_ids` 打开 `write_only` `Workbook`;后续调用追加行窗(对齐 `pipeline` 多 `batch`)
    - 某行 `field_names` 全集齐备后,按行序刷入 `sheet` 并释放该行缓冲
    - 适合行窗写出(每窗写满全部列);对先写完整列再写下一批列的全量模式峰值收益有限

    参数与 `ColumnExcelSink` 对齐;不改变默认 `ColumnExcelSink` 行为.
    """

    output_path: str
    field_names: List[str]
    header_names: List[str]
    sheet_name: str
    include_header: bool
    _row_ids: List[Hashable]
    _row_index: Dict[Hashable, int]
    _pending: List[Optional[Set[str]]]
    _values: List[Optional[List[CellValue]]]
    _field_index: Dict[str, int]
    _workbook: Any
    _worksheet: Any
    _next_flush_index: int
    _flushed_rows: int
    _closed: bool
    _allow_formulas: bool
    _type_precheck: SinkTypePrecheck

    def __init__(
        self,
        output_path: str,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        sheet_name: str = "Sheet1",
        include_header: bool = True,  # noqa: FBT001, FBT002
        allow_formulas: bool = True,  # noqa: FBT001, FBT002
        type_precheck: SinkTypePrecheck = SinkTypePrecheck.OFF,
    ) -> None:
        self._type_precheck = require_sink_type_precheck(type_precheck, where="StreamingColumnExcelSink.type_precheck")
        self.output_path = output_path
        self.field_names = list(field_names)
        self.header_names = list(header_names) if header_names is not None else list(field_names)
        self.sheet_name = sheet_name
        self.include_header = include_header
        self._row_ids = []
        self._row_index = {}
        self._pending = []
        self._values = []
        self._field_index = {name: idx for idx, name in enumerate(self.field_names)}
        self._workbook = None
        self._worksheet = None
        self._next_flush_index = 0
        self._flushed_rows = 0
        self._closed = False
        self._allow_formulas = bool(allow_formulas)

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        if self._closed:
            msg = "Sink 已关闭"
            raise RuntimeError(msg)

        new_ids = list(row_ids)
        if not new_ids:
            return

        for pk in new_ids:
            if pk in self._row_index:
                msg = "重复 `row_id`: {!r}".format(pk)
                raise RuntimeError(msg)

        start = len(self._row_ids)
        first_batch = start == 0
        self._row_ids.extend(new_ids)
        for offset, pk in enumerate(new_ids):
            self._row_index[pk] = start + offset

        n = len(new_ids)
        self._pending.extend(set(self.field_names) for _ in range(n))
        empty_row: List[CellValue] = [None] * len(self.field_names)  # type: ignore[list-item]
        self._values.extend(list(empty_row) for _ in range(n))

        if not first_batch:
            return

        self._workbook = Workbook(write_only=True)
        self._worksheet = self._workbook.create_sheet(self.sheet_name)
        if self.include_header:
            _ = self._worksheet.append([escape_excel_formula(x, allow_formulas=self._allow_formulas) for x in self.header_names])

    def _flush_ready_prefix(self) -> None:
        """按行序刷入已齐备的连续前缀(满足 `write_only` 顺序约束)."""

        while self._next_flush_index < len(self._row_ids):
            pending = self._pending[self._next_flush_index]
            if pending is None or pending:
                break
            row_vals = self._values[self._next_flush_index]
            if row_vals is None:
                break
            _ = self._worksheet.append([escape_excel_formula(x, allow_formulas=self._allow_formulas) for x in row_vals])
            self._values[self._next_flush_index] = None
            self._pending[self._next_flush_index] = None
            self._next_flush_index += 1
            self._flushed_rows += 1

    @override
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        if self._closed:
            msg = "Sink 已关闭"
            raise RuntimeError(msg)
        if not self._row_ids:
            msg = "必须先调用 `set_row_ids`"
            raise RuntimeError(msg)
        field = str(field_key)
        if field not in self._field_index:
            raise KeyError(field)

        fidx = self._field_index[field]
        for pk, raw_value in values.items():
            ridx = self._row_index.get(pk)
            if ridx is None:
                continue
            pending = self._pending[ridx]
            row_vals = self._values[ridx]
            if pending is None or row_vals is None:
                continue
            value = raw_value
            if self._type_precheck is SinkTypePrecheck.ON:
                value = ensure_sink_accepted_cell(
                    value,
                    field_id=field,
                    sink_name="StreamingColumnExcelSink",
                    accepted=is_excel_accepted_cell,
                )
            row_vals[fidx] = value
            pending.discard(field)

        self._flush_ready_prefix()

    @override
    def write_columns(self, columns: ColumnBatch) -> None:
        for field_key, values in columns.items():
            self.write_column(field_key, values)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        _ = rows
        msg = "`StreamingColumnExcelSink` 请使用行窗 `write_column`/`write_columns`"
        raise RuntimeError(msg)

    def _abandon_open_workbook(self) -> None:
        if self._workbook is None:
            return
        # 只关 `worksheet`,避免 `write_only` 生成器在 `Workbook.close` 后对已关文件做 I/O.
        best_effort_close_write_only_workbook_worksheets(self._workbook)
        self._workbook = None
        self._worksheet = None

    @override
    def discard(self) -> None:
        if self._closed:
            return
        self._abandon_open_workbook()
        self._pending = []
        self._closed = True

    @override
    def close(self) -> None:
        if self._closed:
            return

        leftover = sum(1 for p in self._pending if p is not None)
        if leftover:
            self._abandon_open_workbook()
            self._closed = True
            msg = "仍有未齐备行: {}".format(leftover)
            raise RuntimeError(msg)

        output_dir = Path(self.output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        if self._workbook is None:
            msg = "未调用 `set_row_ids`,无法保存"
            raise RuntimeError(msg)

        try:
            save_openpyxl_workbook_atomic(self._workbook, output_path=self.output_path)
        except Exception:
            _LOGGER.exception(STREAMING_COLUMN_EXCEL_SINK_SAVE_FAILED_LOG, self.output_path)
            best_effort_close_write_only_workbook_worksheets(self._workbook)
            raise
        finally:
            with suppress(Exception):
                self._workbook.close()

        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional["types.TracebackType"],  # noqa: PYI036
    ) -> None:
        exit_sink(self, exc_type)


__all__ = ()
