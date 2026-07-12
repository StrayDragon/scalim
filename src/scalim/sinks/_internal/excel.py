# pragma: allow-c901-file plan: c60
# region imports

import logging
import zipfile
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, Type

from ..._internal.loggingx import prefix
from ..._internal.utils.excel import escape_excel_formula
from ..._internal.utils.openpyxl_helpers import (
    best_effort_close_write_only_workbook_worksheets as _best_effort_close_write_only_workbook_worksheets,
)
from ..._internal.utils.openpyxl_helpers import (
    best_effort_close_write_only_worksheet as _best_effort_close_write_only_worksheet,
)
from ...typedefs import FieldValue, RowData, SinkRowKeySeq
from ...vendor.compact.importlibx import require_optional_dependency
from ...vendor.compact.typing_extensionsx import Self, override
from .base import (
    BaseRowSink,
    ColumnBatch,
    ColumnData,
    ColumnValues,
    IColumnSink,
    atomic_replace_temp_path,
    best_effort_cleanup_temp_path_dir,
    create_temp_path,
    iter_row_values,
    store_rows_as_columns,
    update_column,
    update_columns,
)

if TYPE_CHECKING:
    import types

# endregion


def _excel_atomic_save_errors() -> Tuple[Type[BaseException], ...]:
    openpyxl_utils_exceptions: Any = require_optional_dependency(
        "openpyxl.utils.exceptions",
        context="scalim.sinks",
        install_name="openpyxl",
    )

    return (
        OSError,
        TypeError,
        zipfile.BadZipFile,
        openpyxl_utils_exceptions.CellCoordinatesException,
        openpyxl_utils_exceptions.IllegalCharacterError,
        openpyxl_utils_exceptions.InvalidFileException,
        openpyxl_utils_exceptions.NamedRangeException,
        openpyxl_utils_exceptions.ReadOnlyWorkbookException,
        openpyxl_utils_exceptions.SheetTitleException,
        openpyxl_utils_exceptions.WorkbookAlreadySaved,
    )


def _excel_sink_outer_close_errors() -> Tuple[Type[BaseException], ...]:
    return (RuntimeError, *_excel_atomic_save_errors())


def _default_workbook_factory(*args: Any, **kwargs: Any) -> Any:
    openpyxl_mod: Any = require_optional_dependency("openpyxl", context="scalim.sinks")
    workbook_cls: Any = openpyxl_mod.Workbook
    return workbook_cls(*args, **kwargs)


Workbook: Any = _default_workbook_factory


_LOGGER = logging.getLogger("scalim.sinks.sink_excel")

_SINKS_PREFIX = prefix("sinks")

EXCEL_SINK_SAVE_FAILED = _SINKS_PREFIX + "ExcelSink 保存失败"
EXCEL_SINK_SAVE_FAILED_LOG = EXCEL_SINK_SAVE_FAILED + ": %s"

EXCEL_SINK_REMOVE_TEMP_FILE_FAILED = _SINKS_PREFIX + "ExcelSink 删除临时文件失败"
EXCEL_SINK_REMOVE_TEMP_FILE_FAILED_LOG = EXCEL_SINK_REMOVE_TEMP_FILE_FAILED + ": %s"

EXCEL_WORKBOOK_SINK_SAVE_FAILED = _SINKS_PREFIX + "ExcelWorkbookSink 保存失败"
EXCEL_WORKBOOK_SINK_SAVE_FAILED_LOG = EXCEL_WORKBOOK_SINK_SAVE_FAILED + ": %s"

EXCEL_WORKBOOK_SINK_REMOVE_TEMP_FILE_FAILED = _SINKS_PREFIX + "ExcelWorkbookSink 删除临时文件失败"
EXCEL_WORKBOOK_SINK_REMOVE_TEMP_FILE_FAILED_LOG = EXCEL_WORKBOOK_SINK_REMOVE_TEMP_FILE_FAILED + ": %s"

COLUMN_EXCEL_SINK_SAVE_FAILED = _SINKS_PREFIX + "ColumnExcelSink 保存失败"
COLUMN_EXCEL_SINK_SAVE_FAILED_LOG = COLUMN_EXCEL_SINK_SAVE_FAILED + ": %s"

COLUMN_EXCEL_SINK_REMOVE_TEMP_FILE_FAILED = _SINKS_PREFIX + "ColumnExcelSink 删除临时文件失败"
COLUMN_EXCEL_SINK_REMOVE_TEMP_FILE_FAILED_LOG = COLUMN_EXCEL_SINK_REMOVE_TEMP_FILE_FAILED + ": %s"


class ExcelSink(BaseRowSink):
    """`Excel` 行写入器:支持流式行写入.

    在内存中缓存数据,并在 `close()` 时一次性写入 `Excel` 文件.
    实现 `IRowSink` 接口,支持单行流式写入以优化内存使用(FR023).

    参数:
        `output_path`: 输出文件路径
        `field_names`: 字段标识列表,用于从行数据中取值
        `header_names`: 表头名称列表(可选),用于输出表头;默认等于 `field_names`
        `sheet_name`: 工作表名称,默认 `"Sheet1"`
        `include_header`: 是否包含表头,默认 `True`

    示例:
    ```python
    with ExcelSink("report.xlsx", field_names=["id", "name"]) as sink:
        sink.write_row({"id": 1, "name": "张三"})
        sink.write_batch([{"id": 2, "name": "李四"}])

    # 使用不同的表头名称
    with ExcelSink("report.xlsx", field_names=["id", "name"], header_names=["编号", "姓名"]) as sink:
        sink.write_row({"id": 1, "name": "张三"})
    ```
    """

    output_path: str
    sheet_name: str
    include_header: bool
    _closed: bool
    field_names: List[str]
    header_names: List[str]
    _workbook: Any
    _worksheet: Any
    _allow_formulas: bool
    _aligned_cache_field_keys: Optional[Tuple[str, ...]]
    _aligned_cache_indexes: Optional[List[Optional[int]]]

    def __init__(
        self,
        output_path: str,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        sheet_name: str = "Sheet1",
        include_header: bool = True,  # noqa: FBT001, FBT002
        allow_formulas: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        self.output_path = output_path
        self.sheet_name = sheet_name
        self.include_header = include_header
        self._closed = False
        self.field_names = field_names
        self.header_names = header_names if header_names is not None else field_names
        self._allow_formulas = bool(allow_formulas)
        self._workbook = Workbook(write_only=True)
        self._worksheet = self._workbook.create_sheet(self.sheet_name)
        self._aligned_cache_field_keys = None
        self._aligned_cache_indexes = None
        if self.include_header:
            _ = self._worksheet.append([escape_excel_formula(x, allow_formulas=self._allow_formulas) for x in self.header_names])

    def _format_row(self, row: RowData) -> List[Any]:
        values: List[Any] = []
        for field_name in self.field_names:
            values.append(escape_excel_formula(row.get(field_name), allow_formulas=self._allow_formulas))
        return values

    @override
    def write_row(self, row: RowData) -> None:
        _ = self._worksheet.append(self._format_row(row))

    def write_row_aligned(self, field_keys: Sequence[str], values: Sequence[FieldValue]) -> None:
        if len(field_keys) != len(values):
            msg = "`write_row_aligned` 长度不一致: field_keys={} values={}".format(len(field_keys), len(values))
            raise ValueError(msg)

        cache_keys = self._aligned_cache_field_keys
        field_keys_tuple = tuple(field_keys)
        if cache_keys != field_keys_tuple:
            index_by_key: Dict[str, int] = {key: i for i, key in enumerate(field_keys_tuple)}
            self._aligned_cache_field_keys = field_keys_tuple
            self._aligned_cache_indexes = [index_by_key.get(name) for name in self.field_names]

        indexes = self._aligned_cache_indexes or []
        row_values: List[Any] = []
        for idx in indexes:
            if idx is None:
                v = None
            else:
                v = values[idx]
            row_values.append(escape_excel_formula(v, allow_formulas=self._allow_formulas))
        _ = self._worksheet.append(row_values)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            _ = self._worksheet.append(self._format_row(row))

    @override
    def close(self) -> None:
        if self._closed:
            return

        # 使用临时文件,确保在同一目录以支持原子重命名
        output_dir = Path(self.output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            try:
                temp_path = create_temp_path(self.output_path, ".xlsx.tmp")
                temp_path_obj = Path(temp_path)

                try:
                    self._workbook.save(temp_path_obj)
                    # 原子重命名临时文件到目标路径
                    atomic_replace_temp_path(temp_path, self.output_path)
                except _excel_atomic_save_errors():
                    _LOGGER.exception(EXCEL_SINK_SAVE_FAILED_LOG, self.output_path)
                    # 清理临时文件
                    try:
                        temp_path_obj.unlink()
                    except FileNotFoundError:  # pragma: no cover  # pragma: allow-no-cover best-effort temp file cleanup
                        pass
                    except OSError:
                        _LOGGER.warning(EXCEL_SINK_REMOVE_TEMP_FILE_FAILED_LOG, temp_path_obj, exc_info=True)
                    best_effort_cleanup_temp_path_dir(temp_path)
                    raise
            except _excel_sink_outer_close_errors():
                # 尽力清理: 在写锁冲突/保存失败等异常路径,避免出现只写生成器告警.
                _best_effort_close_write_only_worksheet(self._worksheet)
                raise
        finally:
            with suppress(Exception):
                self._workbook.close()

        self._closed = True


class ExcelWorkbookSheetRowSink(BaseRowSink):
    """`Excel` `workbook` 中单个 `sheet` 的行写入器(共享同一 `workbook`).

    - 该 `sink` 仅负责向 `worksheet` 追加行.
    - `workbook` 的保存/原子替换由 `ExcelWorkbookSink.close()` 统一完成.
    """

    sheet_name: str
    include_header: bool
    field_names: List[str]
    header_names: List[str]
    _worksheet: Any
    _closed: bool
    _allow_formulas: bool

    def __init__(
        self,
        *,
        worksheet: Any,
        sheet_name: str,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        include_header: bool = True,
        allow_formulas: bool = True,
    ) -> None:
        self._worksheet = worksheet
        self.sheet_name = str(sheet_name)
        self.include_header = bool(include_header)
        self.field_names = list(field_names)
        self.header_names = list(header_names) if header_names is not None else list(self.field_names)
        self._allow_formulas = bool(allow_formulas)
        self._closed = False
        if self.include_header:
            # 关键护栏: `header` 与 `rows` 分离,避免 `header` `list` 被复用污染.
            _ = self._worksheet.append([escape_excel_formula(x, allow_formulas=self._allow_formulas) for x in list(self.header_names)])

    def _format_row(self, row: RowData) -> List[Any]:
        values: List[Any] = []
        for field_name in self.field_names:
            values.append(escape_excel_formula(row.get(field_name), allow_formulas=self._allow_formulas))
        return values

    @override
    def write_row(self, row: RowData) -> None:
        if self._closed:
            msg = "ExcelWorkbookSheetRowSink is closed: {}".format(self.sheet_name)
            raise RuntimeError(msg)
        _ = self._worksheet.append(self._format_row(row))

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        if self._closed:
            msg = "ExcelWorkbookSheetRowSink is closed: {}".format(self.sheet_name)
            raise RuntimeError(msg)
        for row in rows:
            _ = self._worksheet.append(self._format_row(row))

    @override
    def close(self) -> None:
        # `sheet` `sink` 仅标记关闭,不保存文件.
        self._closed = True


class ExcelWorkbookSink:
    """`Excel` `workbook` 容器: 单次保存,支持多 `sheet`.

    设计目标:
    - 多 `sheet` 共享同一 `workbook`,避免重复打开/保存文件
    - 支持 `write_only` 流式写入,避免“全量 `rows` 攒内存”
    - `sheet` 名冲突 `fail-fast`
    - `sheet` 顺序稳定: 由 `create_sheet()` 调用顺序决定
    """

    output_path: str
    _workbook: Any
    _sheet_names: List[str]
    _closed: bool

    def __init__(
        self,
        output_path: str,
    ) -> None:
        self.output_path = str(output_path)
        self._workbook = Workbook(write_only=True)
        self._sheet_names = []
        self._closed = False

    def create_sheet_row_sink(
        self,
        sheet_name: str,
        *,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        include_header: bool = True,
        allow_formulas: bool = True,
    ) -> ExcelWorkbookSheetRowSink:
        if self._closed:
            msg = "ExcelWorkbookSink is closed: {}".format(self.output_path)
            raise RuntimeError(msg)

        name = str(sheet_name)
        if name in self._sheet_names:
            msg = "Duplicate excel sheet name in workbook: {!r}".format(name)
            raise ValueError(msg)

        ws = self._workbook.create_sheet(name)
        self._sheet_names.append(name)
        return ExcelWorkbookSheetRowSink(
            worksheet=ws,
            sheet_name=name,
            field_names=field_names,
            header_names=header_names,
            include_header=include_header,
            allow_formulas=allow_formulas,
        )

    def close(self) -> None:
        if self._closed:
            return

        output_dir = Path(self.output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            try:
                temp_path = create_temp_path(self.output_path, ".xlsx.tmp")
                temp_path_obj = Path(temp_path)

                try:
                    self._workbook.save(temp_path_obj)
                    atomic_replace_temp_path(temp_path, self.output_path)
                except _excel_atomic_save_errors():
                    _LOGGER.exception(EXCEL_WORKBOOK_SINK_SAVE_FAILED_LOG, self.output_path)
                    try:
                        temp_path_obj.unlink()
                    except FileNotFoundError:  # pragma: no cover  # pragma: allow-no-cover best-effort temp file cleanup
                        pass
                    except OSError:
                        _LOGGER.warning(EXCEL_WORKBOOK_SINK_REMOVE_TEMP_FILE_FAILED_LOG, temp_path_obj, exc_info=True)
                    best_effort_cleanup_temp_path_dir(temp_path)
                    raise
            except _excel_sink_outer_close_errors():
                # 尽力清理: 在写锁冲突/保存失败等异常路径,避免出现只写生成器告警.
                _best_effort_close_write_only_workbook_worksheets(self._workbook)
                raise
        finally:
            with suppress(Exception):
                self._workbook.close()

        self._closed = True

    def __enter__(self) -> "Self":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class ColumnExcelSink(IColumnSink):
    """列式 `Excel` 写入器:用于生产环境的高性能列式写入(FR023).

    工作原理:
    1. 在内存中按列缓存数据
    2. 在 `close()` 时用 `openpyxl` 的 `write_only` `Workbook` 按行写出并保存

    优点:
    - 调用方可在 `write_column()` 后立即释放该列的源数据
    - 适合宽表场景(200+ 列)
    - `close()` 使用 `write_only=True`,避免常规 `Workbook` 单元格树与列缓存双峰叠加

    参数:
        `output_path`: 输出文件路径
        `field_names`: 字段标识列表,用于从列数据中取值
        `header_names`: 表头名称列表(可选),用于输出表头;默认等于 `field_names`
        `sheet_name`: 工作表名称,默认 `"Sheet1"`
        `include_header`: 是否包含表头,默认 `True`

    示例:
    ```python
    with ColumnExcelSink("/tmp/report.xlsx", ["id", "name"]) as sink:
        sink.set_row_ids([1, 2, 3])
        sink.write_column("id", {1: 1, 2: 2, 3: 3})
        sink.write_column("name", {1: "甲", 2: "乙", 3: "丙"})

    # 使用不同的表头名称
    with ColumnExcelSink("/tmp/report.xlsx", ["id", "name"], header_names=["编号", "姓名"]) as sink:
        sink.set_row_ids([1, 2, 3])
        sink.write_column("id", {1: 1, 2: 2, 3: 3})
    ```
    """

    output_path: str
    field_names: List[str]
    header_names: List[str]
    sheet_name: str
    include_header: bool
    _row_ids: List[Any]
    _columns: ColumnData
    _closed: bool
    _allow_formulas: bool

    def __init__(
        self,
        output_path: str,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        sheet_name: str = "Sheet1",
        include_header: bool = True,  # noqa: FBT001, FBT002
        allow_formulas: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        self.output_path = output_path
        self.field_names = field_names
        self.header_names = header_names if header_names is not None else field_names
        self.sheet_name = sheet_name
        self.include_header = include_header
        self._row_ids = []
        self._columns = {}
        self._closed = False
        self._allow_formulas = bool(allow_formulas)

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        self._row_ids.extend(row_ids)

    @override
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        update_column(self._columns, field_key, values)

    def write_column_aligned(self, field_key: str, row_ids: "SinkRowKeySeq", values: Sequence[FieldValue]) -> None:
        if len(row_ids) != len(values):
            msg = "`write_column_aligned` 长度不一致: row_ids={} values={}".format(len(row_ids), len(values))
            raise ValueError(msg)
        self.write_column(field_key, dict(zip(row_ids, values)))

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

        output_dir = Path(self.output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 使用临时文件,确保在同一目录以支持原子重命名
        temp_path = create_temp_path(self.output_path, ".xlsx.tmp")
        temp_path_obj = Path(temp_path)
        wb = None

        try:
            # 与行式写出器对齐: 使用只写工作簿降低关闭阶段单元格树峰值(见本变更 `evidence-mvp`)
            wb = Workbook(write_only=True)
            ws = wb.create_sheet(self.sheet_name)

            if self.include_header:
                _ = ws.append([escape_excel_formula(x, allow_formulas=self._allow_formulas) for x in self.header_names])

            for row_values in iter_row_values(self._row_ids, self.field_names, self._columns):
                _ = ws.append([escape_excel_formula(x, allow_formulas=self._allow_formulas) for x in row_values])

            wb.save(temp_path_obj)
            # 原子重命名临时文件到目标路径
            atomic_replace_temp_path(temp_path, self.output_path)
        except _excel_atomic_save_errors():
            _LOGGER.exception(COLUMN_EXCEL_SINK_SAVE_FAILED_LOG, self.output_path)
            # 清理临时文件
            try:
                temp_path_obj.unlink()
            except FileNotFoundError:  # pragma: no cover  # pragma: allow-no-cover best-effort temp file cleanup
                pass
            except OSError:
                _LOGGER.warning(COLUMN_EXCEL_SINK_REMOVE_TEMP_FILE_FAILED_LOG, temp_path_obj, exc_info=True)
            best_effort_cleanup_temp_path_dir(temp_path)
            if wb is not None:
                _best_effort_close_write_only_workbook_worksheets(wb)
            raise
        finally:
            if wb is not None:  # pragma: no branch  # pragma: allow-no-branch best-effort cleanup under multiple error paths
                with suppress(Exception):
                    wb.close()

        self._closed = True

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional["types.TracebackType"],  # noqa: PYI036
    ) -> None:
        self.close()


__all__ = ()
