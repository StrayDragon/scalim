from __future__ import absolute_import

# 说明: 以下类型来自 `derived_outputs`,并且历史上可通过 `scalim.execution.output_composition` 导入.
# 它们不属于本模块 `__all__`,但仍保留为稳定导入路径的一部分(避免非预期回归).
from ..derived_outputs import AggMetricSpec as AggMetricSpec
from ..derived_outputs import PostFieldSpec as PostFieldSpec
from ..derived_outputs import RankFieldSpec as RankFieldSpec
from ..managed_artifacts import ManagedArtifactPlan as ManagedArtifactPlan
from .build import OutputCompositionPlan as OutputCompositionPlan
from .build import build_output_composition as build_output_composition
from .build import ensure_primary_route as ensure_primary_route
from .build import normalize_output_failure_policy as normalize_output_failure_policy
from .build import required_demand_fields as required_demand_fields
from .build import validate_excel_workbook_sheet_names as validate_excel_workbook_sheet_names
from .router import FinalTargetState as FinalTargetState
from .router import RouterRowSink as RouterRowSink
from .router import RouteState as RouteState
from .router import ScalimOutputTargetWriteError as ScalimOutputTargetWriteError
from .router import truncate_text as truncate_text
from .sinks import RowCounter as RowCounter
from .sinks import create_row_sink_for_composed_output as create_row_sink_for_composed_output
from .sinks import get_or_create_excel_workbook_sink as get_or_create_excel_workbook_sink
from .specs import AuditSheetSpec as AuditSheetSpec
from .specs import DerivedGroupBySpec as DerivedGroupBySpec
from .specs import DerivedOutputTargetSpec as DerivedOutputTargetSpec
from .specs import IDerivedAggregationSpec as IDerivedAggregationSpec
from .specs import MetaSheetSpec as MetaSheetSpec
from .specs import OutputCompositionSpec as OutputCompositionSpec
from .specs import OutputRowPredicate as OutputRowPredicate
from .specs import OutputTargetSpec as OutputTargetSpec
from .specs import OutputTargetStats as OutputTargetStats
from .specs import fingerprint_for_derived_target as fingerprint_for_derived_target
from .specs import metric_fingerprint_part as metric_fingerprint_part
from .specs import post_field_fingerprint_part as post_field_fingerprint_part
from .specs import rank_field_fingerprint_part as rank_field_fingerprint_part

# 兼容说明: 以下私有符号主要用于测试与历史导入,新代码不建议依赖.
_FinalTargetState = FinalTargetState
_RouteState = RouteState
_RowCounter = RowCounter

_create_row_sink_for_composed_output = create_row_sink_for_composed_output
_get_or_create_excel_workbook_sink = get_or_create_excel_workbook_sink

_ensure_primary_route = ensure_primary_route
_normalize_failure_policy = normalize_output_failure_policy
_validate_excel_workbook_sheet_names = validate_excel_workbook_sheet_names

_fingerprint_for_derived_target = fingerprint_for_derived_target
_metric_fingerprint_part = metric_fingerprint_part
_post_field_fingerprint_part = post_field_fingerprint_part
_rank_field_fingerprint_part = rank_field_fingerprint_part
_truncate_text = truncate_text

__all__ = (
    "AuditSheetSpec",
    "DerivedGroupBySpec",
    "DerivedOutputTargetSpec",
    "IDerivedAggregationSpec",
    "MetaSheetSpec",
    "OutputCompositionPlan",
    "OutputCompositionSpec",
    "OutputTargetSpec",
    "OutputTargetStats",
    "RouterRowSink",
    "ScalimOutputTargetWriteError",
    "build_output_composition",
    "required_demand_fields",
)
