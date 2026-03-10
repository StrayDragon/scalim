"""IR(中间表示)类型官方入口.

此包提供稳定的 IR 类型导入路径,供用户侧直接构造/读取 IR 结构.
"""

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
from .demand import DemandIr
from .fields import ComputeCallContextIr, DerivedFieldIr, FieldIr, SupportedFieldIr
from .presentation import (
    CsvFieldPresentationIr,
    ExportProfileIr,
    FieldPresentationIr,
    PandasFieldPresentationIr,
    SpreadsheetFieldPresentationIr,
)
from .relations import FieldRefIr, JoinConditionIr, LookupStepIr, RelationIr
from .sources import KeyIr, MainSourceIr, OrderByKeyIr, SourceIr, SourceNormalizeIr, SourceRefIr

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
