from typing import Any, Callable, Dict, Hashable, Iterable, List, Tuple, Union

from ....typedefs import RowData

LoaderResultMapCallable = Callable[..., Dict[Hashable, Any]]
"""
`Loader` 函数类型: 返回 `Dict[Hashable, Any]` 的可调用对象

用户注入的数据源加载函数应符合此签名.
"""


MainSourceRowIterableCallable = Callable[..., Iterable[RowData]]
"""
主数据源 `Loader` 函数类型: 返回 `Iterable[RowData]` 的可调用对象

主数据源按行流方式提供数据,无需提供主键映射.
"""


LookupKeySpec = Union[str, Tuple[str, ...], List[str]]
"""
`Lookup` 字段键类型: 支持单字段(`str`)与多字段(`list`/`tuple`)
"""


__all__ = [
    "LoaderResultMapCallable",
    "LookupKeySpec",
    "MainSourceRowIterableCallable",
]
