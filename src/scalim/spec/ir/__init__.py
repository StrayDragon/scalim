"""IR(中间表示)类型官方入口.

此包提供稳定的 IR 类型导入路径,供用户侧直接构造/读取 IR 结构.
"""

# pragma: scalim-public-api tier1:60:scalim.spec.ir|IR(中间表示)数据结构(稳定导入路径)|写自定义组件/扩展点/高级调试

from ._demand import DemandIr
from ._fields import (
    CallBySpecIr,
    CallByValueIr,
    ComputeCallContextIr,
    DerivedFieldIr,
    FieldIr,
    SupportedFieldIr,
    ValueOpIr,
)
from ._relations import FieldRefIr, JoinConditionIr, LookupStepIr, RelationIr
from ._sources import (
    KeyIr,
    MainSourceIr,
    OrderByKeyIr,
    SourceIr,
    SourceNormalizeIr,
    SourceNormalizeProjectFieldRuleIr,
    SourceNormalizeStepIr,
    SourceRefIr,
)
from .aliases import (
    LoaderExtractor,
    LoaderParamsBuilder,
    LoaderResultMapCallable,
    LookupKeyCast,
    LookupKeySpec,
    MainSourceRowIterableCallable,
    NormalizedLookupKeySpec,
)
from .binding import BindingIr, LoaderCallContextIr, LoaderIr, build_stable_lookup_key_list
from .callable_refs import BuiltinCallableIdIr, CallableRefIr, PythonReferenceIr, RuntimeHandleIdIr, describe_callable_ref
from .lookup_casts import LookupCastSpecIr
from .presentation import (
    CsvFieldPresentationIr,
    ExportProfileIr,
    FieldPresentationIr,
    PandasFieldPresentationIr,
    SpreadsheetFieldPresentationIr,
)

# 这些符号允许从 `scalim.spec.ir` 直接导入以便内部复用,但不纳入 `__all__`(非稳定公开契约).
_non_public_exports = (SourceNormalizeProjectFieldRuleIr, SourceNormalizeStepIr)
del _non_public_exports

__all__ = (
    "BindingIr",
    "BuiltinCallableIdIr",
    "CallBySpecIr",
    "CallByValueIr",
    "CallableRefIr",
    "ComputeCallContextIr",
    "CsvFieldPresentationIr",
    "DemandIr",
    "DerivedFieldIr",
    "ExportProfileIr",
    "FieldIr",
    "FieldPresentationIr",
    "FieldRefIr",
    "JoinConditionIr",
    "KeyIr",
    "LoaderCallContextIr",
    "LoaderExtractor",
    "LoaderIr",
    "LoaderParamsBuilder",
    "LoaderResultMapCallable",
    "LookupCastSpecIr",
    "LookupKeyCast",
    "LookupKeySpec",
    "LookupStepIr",
    "MainSourceIr",
    "MainSourceRowIterableCallable",
    "NormalizedLookupKeySpec",
    "OrderByKeyIr",
    "PandasFieldPresentationIr",
    "PythonReferenceIr",
    "RelationIr",
    "RuntimeHandleIdIr",
    "SourceIr",
    "SourceNormalizeIr",
    "SourceRefIr",
    "SpreadsheetFieldPresentationIr",
    "SupportedFieldIr",
    "ValueOpIr",
    "build_stable_lookup_key_list",
    "describe_callable_ref",
)
