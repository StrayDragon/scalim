from collections.abc import Callable, Hashable, Iterable
from typing import Any

from ....typedefs import RowData

LoaderCallable = Callable[..., dict[Hashable, Any]]
"""
Loader 函数类型: 返回 Dict[Hashable, Any] 的可调用对象

用户注入的数据源加载函数应符合此签名.
"""


MainSourceLoaderCallable = Callable[..., Iterable[RowData]]
"""
主数据源 Loader 函数类型: 返回 Iterable[RowData] 的可调用对象

主数据源按行流方式提供数据,无需提供主键映射.
"""


LookupFieldKey = str | tuple[str, ...] | list[str]
"""
Lookup 字段键类型: 支持单字段(str)与多字段(list/tuple)
"""
