# region imports

from abc import ABC, abstractmethod
from contextlib import suppress
from typing import TYPE_CHECKING, Callable, Dict, Hashable, Iterator, List, Mapping, Optional, Sequence, Type

from ..._internal.utils import atomic_paths as _atomic_paths
from ...typedefs import CellValue, RowData, SinkRowKeySeq
from ...vendor.compact.typing_extensionsx import Self, override

if TYPE_CHECKING:
    import types

# endregion


ColumnValues = Mapping[Hashable, CellValue]
ColumnBatch = Mapping[str, ColumnValues]
ColumnData = Dict[str, Dict[Hashable, CellValue]]

# 从 `_internal.utils.atomic_paths` 再导出,兼容既有导入路径.
atomic_replace_temp_path = _atomic_paths.atomic_replace_temp_path
best_effort_cleanup_temp_path_dir = _atomic_paths.best_effort_cleanup_temp_path_dir
best_effort_remove_temp_path = _atomic_paths.best_effort_remove_temp_path
create_temp_path = _atomic_paths.create_temp_path


def update_column(columns: ColumnData, field_key: str, values: ColumnValues) -> None:
    if field_key not in columns:
        columns[field_key] = {}
    columns[field_key].update(values)


def update_columns(columns: ColumnData, updates: ColumnBatch) -> None:
    for field_key, values in updates.items():
        update_column(columns, field_key, values)


def store_rows_as_columns(
    rows: Sequence[RowData],
    row_ids: List[Hashable],
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


def iter_row_values(row_ids: "SinkRowKeySeq", field_names: Sequence[str], columns: ColumnData) -> Iterator[List[CellValue]]:
    for pk in row_ids:
        row_values: List[CellValue] = []
        for field_name in field_names:
            column_data = columns.get(field_name, {})
            row_values.append(column_data.get(pk))
        yield row_values


class ISink(ABC):
    """输出 `Sink` 接口.

    框架通过此接口输出数据,不关心输出格式和目标.
    """

    @abstractmethod
    def write_batch(self, rows: Sequence[RowData]) -> None:
        """写入一批数据.

        参数:
            `rows`: 数据行列表(每行是从字段键到字段值的映射)
        """

    @abstractmethod
    def close(self) -> None:
        """关闭 `Sink`,完成输出(成功路径提交/落盘)."""

    @abstractmethod
    def discard(self) -> None:
        """失败路径清理:放弃半成品,`MUST NOT` `promote` 最终用户可见输出路径.

        无文件副作用的实现可为可调用的 `no-op`,但必须幂等.
        """


class IRowSink(ISink, ABC):
    """流式 `Sink` 接口:支持按行写入.

    此接口扩展 `ISink`,用于支持逐行写入,并实现更激进的内存优化(FR023).

    使用 `IRowSink` 时:
    - 引擎通常可以在每行的所有目标字段就绪后立即写入
    - 该行的内存通常可以在写入后立即释放(若存在 `batch_rows` 绑定/`use_rows` 依赖,释放可能被推迟到屏障完成)
    - 比批量写入更节省内存

    何时使用按行写入(`IRowSink`):
    1. 目标字段数量较少(< 50 个字段)
    2. 每行的字段计算有依赖关系,需要等待该行所有字段完成
    3. 输出格式是行导向的(如 `CSV`、`JSON Lines`)
    4. 需要保持行的完整性(所有字段一起写入)

    与按列写入(`IColumnSink`)的区别:
    - 按行写入:等待一行字段完成 → 写入整行 →(通常)释放该行内存
    - 按列写入:每列完成 → 写入该列 → 释放该列内存(更适合宽表场景)

    注意:内存优化(FR023)- 按行流式写入
    通过支持单行写入,可以在每行的所有目标字段计算完成后立即写入并释放内存.
    """

    @abstractmethod
    def write_row(self, row: RowData) -> None:
        """写入单行数据.

        参数:
            `row`: 单行数据(从字段键到字段值的映射)

        注意:内存优化 - 写入后调用方通常可以立即释放该行的内存;若上层执行存在 `batch_rows` 绑定/`use_rows` 屏障,释放可能被推迟.
        """

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        """通过逐行写入来写入一批数据.

        默认实现为每行调用 `write_row`;子类可以重写以实现更高效的批量写入.

        参数:
            `rows`: 数据行列表
        """
        for row in rows:
            self.write_row(row)


class IColumnSink(ISink, ABC):
    """列式 `Sink` 接口:支持按列流式写入(FR023).

    此接口支持 FR023 中描述的“区块列写入”模式:
    1. 处理完每个数据源后,立即写入其目标列
    2. 释放这些列的内存
    3. 继续处理下一个数据源

    当处理大量列时(如 200+ 列),这比按行写入更节省内存,因为:
    - 每列可以独立写入和释放
    - 只需保留关键字段(`row_id`/`lookup_key`)直到结束

    何时使用按列写入(`IColumnSink`):
    1. 目标字段数量非常多(> 50 个字段,尤其是 200+ 列的宽表)
    2. 数据源字段分散在多个加载函数中,每个加载函数提供一部分字段
    3. 希望尽早释放内存,不等待整行完成
    4. 输出格式支持按列追加(如 `Parquet`,或可重组的 `CSV`)

    与按行写入(`IRowSink`)的区别:
    - 按列写入:每列完成 → 写入该列 → 释放该列内存
    - 按行写入:等待一行字段完成 → 写入整行 → 释放该行内存

    典型场景:
    - 订单宽表:200+ 列,来自 `orders`、`customers`、`payments`、`items` 等多个数据源
    - 用户画像:100+ 特征列,来自不同的特征计算模块
    - 报表生成:大量指标列,需要分阶段计算和写入

    使用模式:
    1. 用 `row_id` 初始化(确定行顺序)
    2. 在列可用时写入列
    3. 关闭以完成输出

    注意:内存优化(FR023)- 真正的按列追加写入
    每处理完一个数据源,立即写入该数据源提供的目标字段列,然后释放内存.

    驻留边界(内建列式写出器):
    - 调用方在 `write_column`/`write_columns` 成功后可以丢弃其本地源列引用
    - 内建 `ColumnExcelSink` 在 `close()` 完成前仍持有写入副本以完成原子写出
    - 默认路径不提供隐式的 `close` 中途列释放;更早流式写出需另案提出显式可选类型
    """

    @abstractmethod
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        """设置定义行顺序的 `row_id`.

        必须在任何 `write_column` 调用之前调用.

        参数:
            `row_ids`: 行标识序列(确定行顺序)

        注意:
            `row_ids` 是输出行顺序的唯一依据,可能来自真实业务键(`key`/`lookup_key`),也可能是批次内行号 `batch_row_nth`(从 0 开始).
            `Sink` 应将其视为不透明的 `row_id`.
        """

    @abstractmethod
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        """写入单列数据.

        参数:
            `field_key`: 字段/列名
            `values`: 从 `row_id` 到字段值的字典

        注意:内存优化 - 写入后调用方可以立即释放该列的内存.
        """

    @abstractmethod
    def write_columns(self, columns: ColumnBatch) -> None:
        """一次写入多列.

        参数:
            `columns`: 从字段键到(主键 → 值)字典的字典

        注意:批量写入多列,比逐列写入更高效.
        """

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
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
                # 使用行索引作为伪 `row_id`(`batch_row_nth`),用于组织列数据.
                columns[field_key][row_idx] = value

        self.write_columns(columns)


def discard_sink(sink: object) -> None:
    """失败路径:调用 `discard()`;`MUST NOT` 回退为成功语义的 `close()` `promote`.

    主路径为正式合约方法;对非 `ISink` 对象仍以可调用探测做 `best-effort` 兼容.
    """
    discard = getattr(sink, "discard", None)  # pragma: allow-dynattr optional-interface: sink discard
    if callable(discard):
        _ = discard()


def exit_sink(sink: object, exc_type: Optional[Type[BaseException]]) -> None:
    """`CM` 退出:成功则 `close()`;异常则 `discard()` 且 `MUST NOT` 成功 `promote`."""
    if exc_type is not None:
        with suppress(Exception):
            discard_sink(sink)
        return
    close = getattr(sink, "close", None)  # pragma: allow-dynattr optional-interface: sink close
    if callable(close):
        _ = close()


class BaseSink(ISink):
    """`Sink` 基类.

    实现 `ISink` 接口,支持批量写入.
    """

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        raise NotImplementedError

    @override
    def close(self) -> None:
        pass

    @override
    def discard(self) -> None:
        """默认无副作用;有状态/文件副作用的子类 `MUST` 覆盖."""

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional["types.TracebackType"],  # noqa: PYI036
    ) -> None:
        exit_sink(self, exc_type)


class BaseRowSink(IRowSink):
    """行式 `Sink` 基类.

    实现 `IRowSink` 接口,支持单行流式写入(FR023).
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

    @override
    def discard(self) -> None:
        """默认无副作用;有状态/文件副作用的子类 `MUST` 覆盖."""

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional["types.TracebackType"],  # noqa: PYI036
    ) -> None:
        exit_sink(self, exc_type)


class BaseColumnSink(IColumnSink):
    """列式 `Sink` 基类."""

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

    @override
    def discard(self) -> None:
        """默认无副作用;有状态/文件副作用的子类 `MUST` 覆盖."""

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
