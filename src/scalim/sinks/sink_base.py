# region imports

import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from ..typedefs import FieldValue, RowData, SinkRowKeySeq
from ..vendor.compact.typing_extensionsx import Self, override

if TYPE_CHECKING:
    import types

# endregion


ColumnValues = Mapping[Hashable, FieldValue]
ColumnBatch = Mapping[str, ColumnValues]
ColumnData = dict[str, dict[Hashable, FieldValue]]


def create_temp_path(output_path: str, suffix: str) -> str:
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(suffix=suffix, dir=str(output_dir))
    os.close(fd)
    return temp_path


def update_column(columns: ColumnData, field_key: str, values: ColumnValues) -> None:
    if field_key not in columns:
        columns[field_key] = {}
    columns[field_key].update(values)


def update_columns(columns: ColumnData, updates: ColumnBatch) -> None:
    for field_key, values in updates.items():
        update_column(columns, field_key, values)


def store_rows_as_columns(
    rows: Sequence[RowData],
    row_ids: list[Hashable],
    columns: ColumnData,
    pk_factory: Callable[[int], Hashable],
    append_unique: bool = True,  # noqa: FBT001, FBT002
) -> None:
    for row_idx, row in enumerate(rows):
        pk = pk_factory(row_idx)
        if (not append_unique) or pk not in row_ids:
            row_ids.append(pk)
        for field_key, value in row.items():
            if field_key not in columns:
                columns[field_key] = {}
            columns[field_key][pk] = value


def iter_row_values(row_ids: "SinkRowKeySeq", field_names: Sequence[str], columns: ColumnData) -> Iterator[list[FieldValue]]:
    for pk in row_ids:
        row_values: list[FieldValue] = []
        for field_name in field_names:
            column_data = columns.get(field_name, {})
            row_values.append(column_data.get(pk))
        yield row_values


class ISink(ABC):
    """输出端接口.

    框架通过此接口输出数据,不关心输出格式和目标.
    """

    @abstractmethod
    def write_batch(self, rows: Sequence[RowData]) -> None:
        """写入一批数据.

        参数:
            `rows`: 数据行列表 (每行是从字段键到字段值的映射)
        """

    @abstractmethod
    def close(self) -> None:
        """关闭输出端, 完成输出"""


class IRowSink(ISink, ABC):
    """行式写出端接口 - 支持行级流式写入.

    此接口扩展 `ISink` 以支持逐行写入,实现更激进的内存优化 (FR023).

    使用 IRowSink 时:
    - 引擎通常可以在每行的所有目标字段就绪后立即写入
    - 该行的内存通常可以在写入后立即释放(若存在 batch_rows 绑定/use_rows 依赖,释放可能被推迟到屏障完成)
    - 比批量写入更节省内存

    何时使用行式写入 (IRowSink):
    --------------------------------
    1. 目标字段数量较少 (< 50 个字段)
    2. 每行的字段计算有依赖关系,需要等待所有字段完成
    3. 输出格式是行导向的 (如 CSV, JSONL)
    4. 需要保持行的完整性 (所有字段一起写入)

    与列式写入 (IColumnSink) 的区别:
    - 行式写入: 等待一行的所有字段都计算完成 -> 写入整行 -> (通常)释放该行内存
    - 列式写入: 每列完成 -> 写入该列 -> 释放该列内存 (更适合宽表场景)

    NOTE: 内存优化 (FR023) - 行级流式写入
    通过支持单行写入,可以在每行的所有目标字段计算完成后立即写入并释放内存
    """

    @abstractmethod
    def write_row(self, row: RowData) -> None:
        """写入单行数据.

        参数:
            `row`: 单行数据 (从字段键到字段值的映射)

        注意: 内存优化 - 写入后调用方通常可以立即释放该行的内存;若上层执行存在 batch_rows 绑定/use_rows 屏障,释放可能被推迟
        """

    def write_batch(self, rows: Sequence[RowData]) -> None:  # pyright: ignore[reportImplicitOverride]
        """通过逐行写入来写入一批数据.

        默认实现为每行调用 write_row.
        子类可以重写以实现更高效的批量写入.

        参数:
            `rows`: 数据行列表
        """
        for row in rows:
            self.write_row(row)


class IColumnSink(ISink, ABC):
    """列式写出端接口 - 支持列级流式写入 (FR023).

    此接口支持 FR023 中描述的"区块列写入"模式:
    1. 处理完每个数据源后,立即写入其目标列
    2. 释放这些列的内存
    3. 继续处理下一个数据源

    当处理大量列时(如 200+ 列),这比行式写入更节省内存,因为:
    - 每列可以独立写入和释放
    - 只需保留关键字段(row_id/lookup_key)直到结束

    何时使用列式写入 (IColumnSink):
    -----------------------------
    1. 目标字段数量非常多 (> 50 个字段,尤其是 200+ 列的宽表)
    2. 数据源字段分散在多个加载器中,每个加载器提供一部分字段
    3. 希望尽早释放内存,不等待整行完成
    4. 输出格式支持列式追加 (如 `Parquet`, 或可以重组的 CSV)

    与行式写入 (IStreamingSink) 的区别:
    - 列式写入: 每列完成 -> 写入该列 -> 释放该列内存
    - 行式写入: 等待一行的所有字段都计算完成 -> 写入整行 -> 释放该行内存

    典型场景:
    - 订单宽表: 200+ 列,来自 `orders`, `customers`, `payments`, `items` 等多个数据源
    - 用户画像: 100+ 特征列,来自不同的特征计算模块
    - 报表生成: 大量指标列,需要分阶段计算和写入

    使用模式:
    1. 用 row_id 初始化 (确定行顺序)
    2. 在列可用时写入列
    3. 关闭以完成输出

    NOTE: 内存优化 (FR023) - 真正的按列追加写入
    每处理完一个数据源,立即写入该数据源提供的目标字段列,然后释放内存
    """

    @abstractmethod
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        """设置定义行顺序的 row_id.

        必须在任何 write_column 调用之前调用.

        参数:
            `row_ids`: 行标识序列 (确定行顺序)

        注意:
            row_ids 是输出行顺序的唯一依据,可能来自真实业务键/lookup_key,
            也可能是批次内行号 batch_row_nth (从 0 开始). 写出端应将其视为不透明 row_id.
        """

    @abstractmethod
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        """写入单列数据.

        参数:
            field_key: 字段/列名
            `values`: 从 row_id 到字段值的字典

        注意: 内存优化 - 写入后调用方可以立即释放该列的内存
        """

    @abstractmethod
    def write_columns(self, columns: ColumnBatch) -> None:
        """一次写入多列.

        参数:
            `columns`: 从字段键到 (`pk` -> 值) 字典的字典

        注意: 批量写入多列,比逐列写入更高效
        """

    def write_batch(self, rows: Sequence[RowData]) -> None:  # pyright: ignore[reportImplicitOverride]
        """通过将行转换为列来写入一批数据.

        默认实现将基于行的数据转换为基于列的数据.

        参数:
            `rows`: 数据行列表
        """
        # 将行数据转换为列数据
        if not rows:
            return

        columns: ColumnData = {}
        for row_idx, row in enumerate(rows):
            for field_key, value in row.items():
                if field_key not in columns:
                    columns[field_key] = {}
                # 使用行号作为伪 `row_id`（`batch_row_nth`）,用于列式组织.
                columns[field_key][row_idx] = value

        self.write_columns(columns)


class BaseSink(ISink):
    """写出端基类.

    实现 `ISink` 接口, 支持批量写入.
    """

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        raise NotImplementedError

    @override
    def close(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "types.TracebackType | None",  # noqa: PYI036
    ) -> None:
        self.close()


class BaseRowSink(IRowSink):
    """行式写出端基类.

    实现 IRowSink 接口, 支持单行流式写入 (FR023).
    """

    @override
    def write_row(self, row: RowData) -> None:
        raise NotImplementedError

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        for row in rows:
            self.write_row(row)

    @override
    def close(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: "types.TracebackType | None",  # noqa: PYI036
    ) -> None:
        self.close()


class BaseColumnSink(IColumnSink):
    """列式写出端基类."""

    @override
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        raise NotImplementedError

    @override
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        raise NotImplementedError

    @override
    def write_columns(self, columns: ColumnBatch) -> None:
        raise NotImplementedError

    @override
    def close(self) -> None:
        pass

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
    "BaseColumnSink",
    "BaseRowSink",
    "BaseSink",
]
