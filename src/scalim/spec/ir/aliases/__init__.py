from typing import Callable, Iterable, List, Optional, Tuple, Union

from ....typedefs import LoaderCallParams, LoaderResultMapping, LookupKey, RowData

LoaderResultMapCallable = Callable[..., object]
"""
`Loader` 函数类型: 返回 `Mapping[LookupKey, object]` 的可调用对象

用户注入的数据源加载函数应符合此签名.
"""


LoaderParamsBuilder = Callable[..., LoaderCallParams]
"""
`params_builder` 运行时函数类型: `(context) -> (args, kwargs)`

说明:
- 静态 `IR` 用 `BindingIr.params_builder_ref` 描述引用;实际函数对象由“运行时链接”阶段解析后注入 `RuntimeBindings.params_builders`.
"""


LookupKeyCast = Callable[[object], Optional[LookupKey]]
"""关联键归一化函数类型."""


LoaderExtractor = Callable[[LookupKey, LoaderResultMapping], object]
"""`Loader` 结果提取器类型: `(lookup_key, loader_result) -> extracted_data`."""


MainSourceRowIterableCallable = Callable[..., Iterable[RowData]]
"""
主数据源 `Loader` 函数类型: 返回 `Iterable[RowData]` 的可调用对象

主数据源按行流方式提供数据,无需提供主键映射.
"""


LookupKeySpec = Union[str, Tuple[str, ...], List[str]]
"""
`Lookup` 字段键类型: 支持单字段(`str`)与多字段(`list`/`tuple`)
"""


NormalizedLookupKeySpec = Union[str, Tuple[str, ...]]
"""归一化后的字段键类型: 单字段 `str` 或复合字段元组."""


__all__ = (
    "LoaderExtractor",
    "LoaderParamsBuilder",
    "LoaderResultMapCallable",
    "LookupKeyCast",
    "LookupKeySpec",
    "MainSourceRowIterableCallable",
    "NormalizedLookupKeySpec",
)
