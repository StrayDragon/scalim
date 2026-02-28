# region imports

import logging
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..vendor.compact.importlibx import require_optional_dependency

if TYPE_CHECKING:
    from openpyxl import Workbook
else:
    _openpyxl = require_optional_dependency("openpyxl", context="scalim.sinks.sink_excel")
    Workbook = _openpyxl.Workbook

from ..typedefs import RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import Self, override
from .sink_base import (
    BaseRowSink,
    ColumnBatch,
    ColumnData,
    ColumnValues,
    IColumnSink,
    create_temp_path,
    iter_row_values,
    store_rows_as_columns,
    update_column,
    update_columns,
)

if TYPE_CHECKING:
    import types

# endregion

_LOGGER = logging.getLogger(__name__)


class ExcelSink(BaseRowSink):
    """`Excel` 行式输出端：支持流式按行写入.

    在内存中缓存数据, `close()` 时一次性写入 `Excel` 文件.
    实现 `IRowSink` 接口, 支持单行流式写入以优化内存使用 (FR023).

    参数：
        `output_path`: 输出文件路径
        `field_names`: 字段 ID 列表, 用于从 `row` 中取值
        `header_names`: 表头名称列表 (可选), 用于输出表头. 默认等于 `field_names`
        `sheet_name`: 工作表名称, 默认 `"Sheet1"`
        `include_header`: 是否包含表头, 默认 `True`

    示例：
        ```python
        with ExcelSink("report.xlsx", field_names=["id", "name"]) as sink:
            sink.write_row({"id": 1, "name": "Alice"})
            sink.write_batch([{"id": 2, "name": "Bob"}])

        # 使用不同的表头名称
        with ExcelSink("report.xlsx", field_names=["id", "name"], header_names=["编号", "姓名"]) as sink:
            sink.write_row({"id": 1, "name": "Alice"})
        ```
    """

    output_path: str
    sheet_name: str
    include_header: bool
    _closed: bool
    field_names: list[str]
    header_names: list[str]
    _workbook: Workbook
    _worksheet: Any

    def __init__(
        self,
        output_path: str,
        field_names: list[str],
        header_names: list[str] | None = None,
        sheet_name: str = "Sheet1",
        include_header: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        self.output_path = output_path
        self.sheet_name = sheet_name
        self.include_header = include_header
        self._closed = False
        self.field_names = field_names
        self.header_names = header_names if header_names is not None else field_names
        self._workbook = Workbook(write_only=True)
        self._worksheet = self._workbook.create_sheet(self.sheet_name)
        if self.include_header:
            _ = self._worksheet.append(self.header_names)

    def _format_row(self, row: RowData) -> list[Any]:
        return [row.get(field_name) for field_name in self.field_names]

    @override
    def write_row(self, row: RowData) -> None:
        _ = self._worksheet.append(self._format_row(row))

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            _ = self._worksheet.append(self._format_row(row))

    @override
    def close(self) -> None:
        if self._closed:
            return

        # 使用临时文件,确保在同一目录以支持原子重命名
        temp_path = create_temp_path(self.output_path, ".xlsx.tmp")
        temp_path_obj = Path(temp_path)

        try:
            self._workbook.save(temp_path_obj)
            # 原子重命名临时文件到目标路径
            _ = temp_path_obj.replace(self.output_path)
        except Exception:
            _LOGGER.exception("ExcelSink save failed: %s", self.output_path)
            # 清理临时文件
            if temp_path_obj.exists():
                try:
                    temp_path_obj.unlink()
                except OSError:
                    _LOGGER.warning("ExcelSink failed to remove temp file: %s", temp_path_obj, exc_info=True)
            # 尽最大努力清理,避免保存失败时出现只写模式生成器的告警.
            try:
                is_closed = self._worksheet.closed
            except AttributeError:
                is_closed = True
            if not is_closed:
                with suppress(Exception):
                    self._worksheet.close()
            raise
        finally:
            with suppress(Exception):
                self._workbook.close()

        self._closed = True


class ColumnExcelSink(IColumnSink):
    """`Excel` 列式输出端：面向生产环境的高性能列式写入 (FR023).

    工作原理:
    1. 在内存中按列缓存数据
    2. `close()` 时一次性将所有数据写入 `Excel` 文件

    优点:
    - 调用方可在 `write_column()` 后立即释放该列的源数据
    - 适合宽表场景 (200+ 列)

    参数：
        `output_path`: 输出文件路径
        `field_names`: 字段 ID 列表, 用于从列数据中取值
        `header_names`: 表头名称列表 (可选), 用于输出表头. 默认等于 `field_names`
        `sheet_name`: 工作表名称, 默认 `"Sheet1"`
        `include_header`: 是否包含表头, 默认 `True`

    示例：
        ```python
        with ColumnExcelSink("/tmp/report.xlsx", ["id", "name"]) as sink:
            sink.set_row_ids([1, 2, 3])
            sink.write_column("id", {1: 1, 2: 2, 3: 3})
            sink.write_column("name", {1: "A", 2: "B", 3: "C"})

        # 使用不同的表头名称
        with ColumnExcelSink("/tmp/report.xlsx", ["id", "name"], header_names=["编号", "姓名"]) as sink:
            sink.set_row_ids([1, 2, 3])
            sink.write_column("id", {1: 1, 2: 2, 3: 3})
        ```
    """

    output_path: str
    field_names: list[str]
    header_names: list[str]
    sheet_name: str
    include_header: bool
    _row_ids: list[Any]
    _columns: ColumnData
    _closed: bool

    def __init__(
        self,
        output_path: str,
        field_names: list[str],
        header_names: list[str] | None = None,
        sheet_name: str = "Sheet1",
        include_header: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        self.output_path = output_path
        self.field_names = field_names
        self.header_names = header_names if header_names is not None else field_names
        self.sheet_name = sheet_name
        self.include_header = include_header
        self._row_ids = []
        self._columns = {}
        self._closed = False

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        self._row_ids.extend(row_ids)

    @override
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        update_column(self._columns, field_key, values)

    @override
    def write_columns(self, columns: ColumnBatch) -> None:
        update_columns(self._columns, columns)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        start_index = len(self._row_ids)

        def _pk_factory(row_idx: int) -> int:
            return start_index + row_idx

        store_rows_as_columns(rows, self._row_ids, self._columns, _pk_factory)

    @override
    def close(self) -> None:
        if self._closed:
            return

        # 使用临时文件,确保在同一目录以支持原子重命名
        temp_path = create_temp_path(self.output_path, ".xlsx.tmp")
        temp_path_obj = Path(temp_path)
        wb = None

        try:
            wb = Workbook()
            ws = wb.active
            if ws is None:
                ws = wb.create_sheet(self.sheet_name)
            else:
                ws.title = self.sheet_name

            if self.include_header:
                _ = ws.append(self.header_names)

            for row_values in iter_row_values(self._row_ids, self.field_names, self._columns):
                _ = ws.append(list(row_values))

            wb.save(temp_path_obj)
            # 原子重命名临时文件到目标路径
            _ = temp_path_obj.replace(self.output_path)
        except Exception:
            _LOGGER.exception("ColumnExcelSink save failed: %s", self.output_path)
            # 清理临时文件
            if temp_path_obj.exists():
                try:
                    temp_path_obj.unlink()
                except OSError:
                    _LOGGER.warning("ColumnExcelSink failed to remove temp file: %s", temp_path_obj, exc_info=True)
            raise
        finally:
            if wb is not None:
                with suppress(Exception):
                    wb.close()

        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "types.TracebackType | None",  # noqa: PYI036
    ) -> None:
        self.close()


__all__ = [
    "ColumnExcelSink",
    "ExcelSink",
]
