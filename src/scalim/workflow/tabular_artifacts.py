"""`workflow` 内部表格工件适配层.

说明:
- 为 `sheetbook/xlsx_memory` 提供统一的类型化读写入口.
- `InMemoryRows` 是类型化单一事实来源; `InMemoryCsv` / `CSV` 文件路径仅作为字符串工件适配.
- 运行时需兼容 `Python 3.6`.
"""

import csv
from pathlib import Path
from typing import Iterator, List, Sequence, Union

from ..sinks.memory import InMemoryCsv
from ..sinks.rows import InMemoryRows
from ..typedefs import FieldValue
from .resources_base import ScalimWorkflowWriteError

WorkflowTabularInput = Union[str, InMemoryCsv, InMemoryRows]


def read_tabular_header(input_tabular: WorkflowTabularInput) -> List[str]:
    if isinstance(input_tabular, InMemoryRows):
        header = [str(x or "").strip() for x in input_tabular.header]
        if not header or any(not x for x in header):
            msg = "Input tabular artifact has invalid header (empty field): <in_memory_rows>"
            raise ScalimWorkflowWriteError(msg)
        return header

    if isinstance(input_tabular, InMemoryCsv):
        header = [str(x or "").strip() for x in input_tabular.header]
        if not header or any(not x for x in header):
            msg = "Input tabular artifact has invalid header (empty field): <in_memory_csv>"
            raise ScalimWorkflowWriteError(msg)
        return header

    path = str(input_tabular)
    csv_path = Path(path)
    if not csv_path.exists():
        msg = "Missing input CSV: {!r}".format(path)
        raise ScalimWorkflowWriteError(msg)
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            msg = "Input CSV is empty (missing header): {!r}".format(path)
            raise ScalimWorkflowWriteError(msg) from None
    header = [str(x or "").strip() for x in header]
    if not header or any(not x for x in header):
        msg = "Input CSV has invalid header (empty field): {!r}".format(path)
        raise ScalimWorkflowWriteError(msg)
    return header


def iter_tabular_rows(input_tabular: WorkflowTabularInput) -> Iterator[List[FieldValue]]:
    if isinstance(input_tabular, InMemoryRows):
        for row in input_tabular.rows:
            yield list(row)
        return

    if isinstance(input_tabular, InMemoryCsv):
        for row in input_tabular.rows:
            yield [str(v) for v in row]
        return

    csv_path = Path(str(input_tabular))
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        _header = next(reader, None)
        for row in reader:
            yield [str(v) for v in row]


def materialize_aligned_tabular_rows(
    expected: Sequence[str],
    mapping: Sequence[int],
    *,
    input_tabular: WorkflowTabularInput,
) -> List[List[FieldValue]]:
    _ = list(expected)
    rows: List[List[FieldValue]] = []
    for row in iter_tabular_rows(input_tabular):
        out_row: List[FieldValue] = []
        for src_idx in mapping:
            out_row.append(row[src_idx] if src_idx >= 0 and src_idx < len(row) else "")
        rows.append(out_row)
    return rows


__all__ = (
    "WorkflowTabularInput",
    "iter_tabular_rows",
    "materialize_aligned_tabular_rows",
    "read_tabular_header",
)
