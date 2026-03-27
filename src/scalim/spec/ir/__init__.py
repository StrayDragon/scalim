"""IR(中间表示)类型官方入口.

此包提供稳定的 IR 类型导入路径,供用户侧直接构造/读取 IR 结构.
"""

from ._demand import DemandIr
from ._fields import ComputeCallContextIr, DerivedFieldIr, FieldIr, SupportedFieldIr
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
    "LookupKeyCast",
    "LookupKeySpec",
    "LookupStepIr",
    "MainSourceIr",
    "MainSourceRowIterableCallable",
    "NormalizedLookupKeySpec",
    "OrderByKeyIr",
    "PandasFieldPresentationIr",
    "RelationIr",
    "SourceIr",
    "SourceNormalizeIr",
    "SourceRefIr",
    "SpreadsheetFieldPresentationIr",
    "SupportedFieldIr",
    "build_stable_lookup_key_list",
)
