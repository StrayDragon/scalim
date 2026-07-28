from __future__ import absolute_import

from typing import Dict, List, Optional, Sequence, Tuple

from ..._internal.utils.iterables import ordered_unique_str
from ...ob.hub import InstrumentationHub
from ...sinks import ExcelWorkbookSink, IRowSink
from ...sinks.accept_types import SinkTypePrecheck
from ...typedefs import KeyNormalizationMode, RuntimeValue
from ...vendor.dataclassesx import dataclass
from ..derived_outputs import AggregatingRowSink
from ..managed_artifacts import MANAGED_ARTIFACT_KIND_CSV, ManagedArtifactPlan
from ..output_contracts import ExportLayout, OutputSpec
from .policy import parse_output_failure_policy
from .router import FinalTargetState, RouterRowSink, RouteState
from .sinks import RowCounter, create_row_sink_for_composed_output
from .specs import (
    AuditSheetSpec,
    DerivedOutputTargetSpec,
    IDerivedAggregationSpec,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputRowPredicate,
    OutputTargetSpec,
    fingerprint_for_derived_target,
)


def required_demand_fields(spec: OutputCompositionSpec) -> Tuple[str, ...]:
    """计算一次运行的目标字段列表(去重保序)."""
    fields: List[str] = []
    for target in spec.targets:
        fields.extend([str(x) for x in target.layout.field_ids])
        if target.requires:
            fields.extend([str(x) for x in target.requires])
    for target in spec.derived_targets:
        fields.extend([str(x) for x in target.derived.required_fields()])
        if target.requires:
            fields.extend([str(x) for x in target.requires])
    return ordered_unique_str(fields)


@dataclass(frozen=True)
class OutputCompositionPlan:
    sink: RouterRowSink
    output_paths: Dict[str, str]
    managed_artifact_plans: Dict[str, ManagedArtifactPlan]


def normalize_output_failure_policy(failure_policy: RuntimeValue) -> str:
    return parse_output_failure_policy(failure_policy)


def validate_excel_workbook_sheet_names(spec: OutputCompositionSpec) -> None:
    """确保同一路径的 `excel` 输出都显式声明 `sheet_name`(避免隐式覆盖)."""
    excel_paths: Dict[str, List[Tuple[str, Optional[str]]]] = {}

    def _collect_excel_path(target_id: str, output: OutputSpec, sheet_name: Optional[str]) -> None:
        fmt = (output.format or "csv").lower()
        if fmt == "excel" and output.path:
            excel_paths.setdefault(str(output.path), []).append((str(target_id), sheet_name))

    for t in spec.targets:
        _collect_excel_path(t.target_id, t.output, str(t.output.sheet_name) if t.output.sheet_name else None)
    for t in spec.derived_targets:
        _collect_excel_path(t.target_id, t.output, str(t.output.sheet_name) if t.output.sheet_name else None)
    if spec.meta_sheet is not None:
        _collect_excel_path(spec.meta_sheet.target_id, spec.meta_sheet.output, str(spec.meta_sheet.sheet_name))
    if spec.audit_sheet is not None:
        _collect_excel_path(spec.audit_sheet.target_id, spec.audit_sheet.output, str(spec.audit_sheet.sheet_name))

    for path, entries in excel_paths.items():
        if len(entries) <= 1:
            continue
        missing = [tid for tid, sheet in entries if not sheet]
        if missing:
            msg = (
                "Excel workbook path is shared by multiple outputs, but some outputs are missing sheet_name: path={!r}, targets={}"
            ).format(path, ", ".join(sorted(missing)))
            raise ValueError(msg)


def _append_route_state(
    *,
    routes: List[RouteState],
    output_paths: Dict[str, str],
    target_id: str,
    sink: IRowSink,
    predicate: Optional[OutputRowPredicate],
    is_primary: bool,
    output: OutputSpec,
    output_counter: RowCounter,
    derived_fingerprint: Optional[str] = None,
) -> None:
    output_paths[str(target_id)] = str(output.path) if output.path else ""
    routes.append(
        RouteState(
            target_id=str(target_id),
            sink=sink,
            predicate=predicate,
            is_primary=bool(is_primary),
            output_path=str(output.path) if output.path else None,
            sheet_name=str(output.sheet_name) if output.sheet_name else None,
            derived_fingerprint=str(derived_fingerprint) if derived_fingerprint else None,
            output_counter=output_counter,
        )
    )


def _append_direct_target_routes(
    *,
    routes: List[RouteState],
    output_paths: Dict[str, str],
    managed_artifact_plans: Dict[str, ManagedArtifactPlan],
    targets: Sequence[OutputTargetSpec],
    workbook_by_path: Dict[str, ExcelWorkbookSink],
    sink_type_precheck: SinkTypePrecheck = SinkTypePrecheck.OFF,
) -> None:
    for t in targets:
        sink, counter, managed_plan = create_row_sink_for_composed_output(
            target_id=str(t.target_id),
            output=t.output,
            layout=t.layout,
            workbook_by_path=workbook_by_path,
            in_memory=bool(t.in_memory),
            managed_artifact_kind=t.managed_artifact_kind,
            sink_type_precheck=sink_type_precheck,
        )
        if managed_plan is not None:
            managed_artifact_plans[str(t.target_id)] = managed_plan
        _append_route_state(
            routes=routes,
            output_paths=output_paths,
            target_id=str(t.target_id),
            sink=sink,
            predicate=t.predicate,
            is_primary=bool(t.is_primary),
            output=t.output,
            output_counter=counter,
        )


def _validate_derived_parallel_mode(target_id: str, derived: IDerivedAggregationSpec, run_parallel_mode: str) -> None:
    try:
        derived.validate_parallel_mode(run_parallel_mode)
    except ValueError as exc:
        msg = "派生输出不支持 parallel_mode={!r}: target_id={!r}: {}".format(str(run_parallel_mode), str(target_id), exc)
        raise ValueError(msg) from exc


def _append_derived_target_routes(
    *,
    routes: List[RouteState],
    output_paths: Dict[str, str],
    managed_artifact_plans: Dict[str, ManagedArtifactPlan],
    targets: Sequence[DerivedOutputTargetSpec],
    workbook_by_path: Dict[str, ExcelWorkbookSink],
    run_parallel_mode: str,
    run_key_normalization: KeyNormalizationMode,
    sink_type_precheck: SinkTypePrecheck = SinkTypePrecheck.OFF,
) -> None:
    for t in targets:
        # 扩展点:自定义 `IDerivedAggregationSpec` 可在此 `fail-fast`(内置 `DerivedGroupBySpec` 为 `no-op`)
        _validate_derived_parallel_mode(str(t.target_id), t.derived, run_parallel_mode)
        derived_fingerprint = fingerprint_for_derived_target(target_id=str(t.target_id), derived=t.derived)

        out_sink, out_counter, managed_plan = create_row_sink_for_composed_output(
            target_id=str(t.target_id),
            output=t.output,
            layout=t.output_layout,
            workbook_by_path=workbook_by_path,
            in_memory=bool(t.in_memory),
            managed_artifact_kind=t.managed_artifact_kind,
            sink_type_precheck=sink_type_precheck,
        )
        if managed_plan is not None:
            managed_artifact_plans[str(t.target_id)] = managed_plan
        agg = t.derived.build_aggregator(key_normalization=run_key_normalization)

        sink = AggregatingRowSink(aggregator=agg, out_sink=out_sink)
        _append_route_state(
            routes=routes,
            output_paths=output_paths,
            target_id=str(t.target_id),
            sink=sink,
            predicate=t.predicate,
            is_primary=bool(t.is_primary),
            output=t.output,
            output_counter=out_counter,
            derived_fingerprint=derived_fingerprint,
        )


def ensure_primary_route(routes: List[RouteState]) -> None:
    if routes and not any(r.is_primary for r in routes):
        routes[0].is_primary = True


def _maybe_create_meta_target(
    *,
    meta_sheet: Optional[MetaSheetSpec],
    output_paths: Dict[str, str],
    workbook_by_path: Dict[str, ExcelWorkbookSink],
    managed_artifact_plans: Dict[str, ManagedArtifactPlan],
    sink_type_precheck: SinkTypePrecheck = SinkTypePrecheck.OFF,
) -> Optional[FinalTargetState]:
    if meta_sheet is None:
        return None

    layout = ExportLayout(field_ids=("key", "value"), header_names=("key", "value"))
    meta_output = OutputSpec(
        format=meta_sheet.output.format,
        path=meta_sheet.output.path,
        encoding=meta_sheet.output.encoding,
        streaming=True,
        include_header=True,
        sheet_name=str(meta_sheet.sheet_name),
        excel_allow_formulas=bool(meta_sheet.output.excel_allow_formulas),
    )
    sink, counter, managed_plan = create_row_sink_for_composed_output(
        target_id=str(meta_sheet.target_id),
        output=meta_output,
        layout=layout,
        workbook_by_path=workbook_by_path,
        in_memory=bool(meta_sheet.in_memory),
        managed_artifact_kind=MANAGED_ARTIFACT_KIND_CSV,
        sink_type_precheck=sink_type_precheck,
    )
    if managed_plan is not None:
        managed_artifact_plans[str(meta_sheet.target_id)] = managed_plan
    output_paths[str(meta_sheet.target_id)] = str(meta_output.path) if meta_output.path else ""
    return FinalTargetState(
        target_id=str(meta_sheet.target_id),
        sink=sink,
        output_counter=counter,
        output_path=str(meta_output.path) if meta_output.path else None,
        sheet_name=str(meta_output.sheet_name) if meta_output.sheet_name else None,
    )


def _maybe_create_audit_target(
    *,
    audit_sheet: Optional[AuditSheetSpec],
    output_paths: Dict[str, str],
    workbook_by_path: Dict[str, ExcelWorkbookSink],
    managed_artifact_plans: Dict[str, ManagedArtifactPlan],
    sink_type_precheck: SinkTypePrecheck = SinkTypePrecheck.OFF,
) -> Optional[FinalTargetState]:
    if audit_sheet is None:
        return None

    layout = ExportLayout(
        field_ids=(
            "target_id",
            "error_type",
            "error_message",
            "error_count",
            "disabled",
            "event_type",
            "fingerprint",
            "error_message_hash",
        ),
        header_names=(
            "target_id",
            "error_type",
            "error_message",
            "error_count",
            "disabled",
            "event_type",
            "fingerprint",
            "error_message_hash",
        ),
    )
    audit_output = OutputSpec(
        format=audit_sheet.output.format,
        path=audit_sheet.output.path,
        encoding=audit_sheet.output.encoding,
        streaming=True,
        include_header=True,
        sheet_name=str(audit_sheet.sheet_name),
        excel_allow_formulas=bool(audit_sheet.output.excel_allow_formulas),
    )
    sink, counter, managed_plan = create_row_sink_for_composed_output(
        target_id=str(audit_sheet.target_id),
        output=audit_output,
        layout=layout,
        workbook_by_path=workbook_by_path,
        in_memory=bool(audit_sheet.in_memory),
        managed_artifact_kind=MANAGED_ARTIFACT_KIND_CSV,
        sink_type_precheck=sink_type_precheck,
    )
    if managed_plan is not None:
        managed_artifact_plans[str(audit_sheet.target_id)] = managed_plan
    output_paths[str(audit_sheet.target_id)] = str(audit_output.path) if audit_output.path else ""
    return FinalTargetState(
        target_id=str(audit_sheet.target_id),
        sink=sink,
        output_counter=counter,
        output_path=str(audit_output.path) if audit_output.path else None,
        sheet_name=str(audit_output.sheet_name) if audit_output.sheet_name else None,
    )


def build_output_composition(
    *,
    spec: OutputCompositionSpec,
    demand_name: str,
    demand_main_source_id: str,
    demand_target_fields: Sequence[str],
    demand_field_fingerprints: Sequence[Tuple[str, str, str, str]],
    run_started_at_epoch: Optional[float] = None,
    run_parallel_mode: str = "",
    run_batch_size: Optional[int] = None,
    run_key_normalization: KeyNormalizationMode = "raw",
    instrumentation: Optional[InstrumentationHub] = None,
    sink_type_precheck: SinkTypePrecheck = SinkTypePrecheck.OFF,
) -> OutputCompositionPlan:
    """物化多输出组合为一个 `IRowSink`(`RouterRowSink`).

    该函数只处理行流式写出路径.
    """

    failure_policy = normalize_output_failure_policy(spec.failure_policy)
    validate_excel_workbook_sheet_names(spec)

    workbook_by_path: Dict[str, ExcelWorkbookSink] = {}
    output_paths: Dict[str, str] = {}
    managed_artifact_plans: Dict[str, ManagedArtifactPlan] = {}

    routes: List[RouteState] = []

    _append_direct_target_routes(
        routes=routes,
        output_paths=output_paths,
        managed_artifact_plans=managed_artifact_plans,
        targets=spec.targets,
        workbook_by_path=workbook_by_path,
        sink_type_precheck=sink_type_precheck,
    )
    _append_derived_target_routes(
        routes=routes,
        output_paths=output_paths,
        managed_artifact_plans=managed_artifact_plans,
        targets=spec.derived_targets,
        workbook_by_path=workbook_by_path,
        run_parallel_mode=str(run_parallel_mode or ""),
        run_key_normalization=run_key_normalization,
        sink_type_precheck=sink_type_precheck,
    )
    ensure_primary_route(routes)

    meta_target = _maybe_create_meta_target(
        meta_sheet=spec.meta_sheet,
        output_paths=output_paths,
        workbook_by_path=workbook_by_path,
        managed_artifact_plans=managed_artifact_plans,
        sink_type_precheck=sink_type_precheck,
    )
    audit_target = _maybe_create_audit_target(
        audit_sheet=spec.audit_sheet,
        output_paths=output_paths,
        workbook_by_path=workbook_by_path,
        managed_artifact_plans=managed_artifact_plans,
        sink_type_precheck=sink_type_precheck,
    )

    # 构建路由器
    wb_resources = list(workbook_by_path.values())
    router = RouterRowSink(
        routes=routes,
        failure_policy=failure_policy,
        workbook_resources=wb_resources,
        meta_target=meta_target,
        audit_target=audit_target,
        emit_events=True,
        instrumentation=instrumentation,
        demand_name=demand_name,
        demand_main_source_id=demand_main_source_id,
        demand_target_fields=list(demand_target_fields),
        demand_field_fingerprints=list(demand_field_fingerprints),
        run_started_at_epoch=run_started_at_epoch,
        run_parallel_mode=run_parallel_mode,
        run_batch_size=run_batch_size,
        run_failure_policy=failure_policy,
        include_full_error_message=bool(spec.include_full_error_message),
    )

    return OutputCompositionPlan(
        sink=router,
        output_paths={k: v for k, v in output_paths.items() if v},
        managed_artifact_plans=managed_artifact_plans,
    )
