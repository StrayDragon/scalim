from typing import List, Optional, Sequence, Tuple

from ....execution.output_composition import (
    AggMetricSpec,
    AuditSheetSpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputRowPredicate,
    OutputTargetSpec,
)
from ....execution.output_contracts import ExportLayout, OutputSpec
from ....execution.run_ir import export_layout_from_demand_ir
from ....spec.ir.demand import DemandIr
from ....typedefs import RowData
from ..config_parsing.security import SecureComputeEngine
from ..schema_dsl.models import (
    DemandConfig,
    OutputAggregateConfig,
    OutputAggregateMetricConfig,
    OutputContainerConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
)


def _get_field_name(field_id: str, demand_ir: DemandIr) -> str:
    field_ir = demand_ir.fields.get(field_id)
    name = getattr(field_ir, "name", "") or ""
    if name and name != field_id:
        return str(name)
    return field_id


def _export_layout_for_derived(
    *,
    demand_ir: DemandIr,
    field_ids: Sequence[str],
    header_fields_output_by: str,
) -> ExportLayout:
    normalized = tuple(str(x) for x in field_ids)
    if header_fields_output_by != "name":
        return ExportLayout(field_ids=normalized, header_names=None)

    names: List[str] = []
    has_diff = False
    for fid in normalized:
        resolved = _get_field_name(fid, demand_ir)
        if resolved != fid:
            has_diff = True
        names.append(resolved)
    if not has_diff:
        return ExportLayout(field_ids=normalized, header_names=None)
    return ExportLayout(field_ids=normalized, header_names=tuple(names))


def _output_spec_from_container(container: OutputContainerConfig) -> OutputSpec:
    fmt = "excel" if str(container.type).lower() == "workbook" else "csv"
    sheet_name = str(container.sheet) if container.sheet else None
    if fmt != "excel":
        sheet_name = None
    return OutputSpec(
        format=fmt,
        path=str(container.path),
        encoding=str(container.encoding),
        streaming=bool(container.streaming),
        include_header=bool(container.include_header),
        sheet_name=sheet_name,
        excel_allow_formulas=bool(container.allow_formulas),
        write_lock=bool(container.write_lock),
    )


def _compile_where_predicate(
    *,
    engine: SecureComputeEngine,
    expression: str,
    requires: Tuple[str, ...],
) -> OutputRowPredicate:
    calc = engine.compile(str(expression), tuple(str(x) for x in requires))
    dep_keys = tuple(str(x) for x in requires)

    def _predicate(row: RowData) -> bool:
        values = [row.get(key) for key in dep_keys]
        return bool(calc(*values))

    return _predicate


def _metric_spec_from_yaml(out_field_id: str, cfg: OutputAggregateMetricConfig) -> AggMetricSpec:
    return AggMetricSpec(
        out_field_id=str(out_field_id),
        op=str(cfg.op),
        field_id=str(cfg.field_id) if cfg.field_id else None,
        field_ids=tuple(str(x) for x in (cfg.field_ids or ())) if cfg.field_ids else None,
        threshold=cfg.threshold,
    )


def _derived_group_by_spec_from_yaml(cfg: OutputAggregateConfig) -> DerivedGroupBySpec:
    metric_ids = sorted(cfg.metrics.keys())
    metrics = tuple(_metric_spec_from_yaml(metric_id, cfg.metrics[metric_id]) for metric_id in metric_ids)
    return DerivedGroupBySpec(
        group_by=tuple(str(x) for x in cfg.group_by),
        metrics=metrics,
        max_groups=int(cfg.max_groups),
        max_distinct=int(cfg.max_distinct),
        distinct_on_overflow=str(cfg.distinct_on_overflow),
        rank_by=str(cfg.rank_by) if cfg.rank_by else None,
        rank_field_id=str(cfg.rank_field_id),
        rank_order=str(cfg.rank_order),
        top_k=int(cfg.top_k),
    )


def _derived_output_layout_fields(cfg: OutputAggregateConfig) -> Tuple[str, ...]:
    metric_ids = sorted(cfg.metrics.keys())
    fields: List[str] = list(cfg.group_by) + metric_ids
    if cfg.rank_by:
        fields.append(str(cfg.rank_field_id or "rank"))
    return tuple(str(x) for x in fields)


def _compile_extra_sheet(
    *,
    target_id: str,
    cfg: OutputExtraSheetConfig,
    default_sheet: str,
    default_workbook_container: Optional[OutputContainerConfig],
) -> Tuple[OutputSpec, str]:
    default_workbook_path = None
    default_allow_formulas = False
    default_write_lock = False
    if default_workbook_container is not None:
        default_workbook_path = str(default_workbook_container.path) if default_workbook_container.path else None
        default_allow_formulas = bool(default_workbook_container.allow_formulas)
        default_write_lock = bool(default_workbook_container.write_lock)

    path = str(cfg.path) if cfg.path else (str(default_workbook_path) if default_workbook_path else "")
    if not path:
        msg = "{} requires a workbook path (set {}.path or provide at least one workbook output)".format(target_id, target_id)
        raise ValueError(msg)
    sheet = str(cfg.sheet) if cfg.sheet else str(default_sheet)

    allow_formulas = default_allow_formulas if cfg.allow_formulas is None else bool(cfg.allow_formulas)
    write_lock = default_write_lock if cfg.write_lock is None else bool(cfg.write_lock)
    return (
        OutputSpec(
            format="excel",
            path=path,
            excel_allow_formulas=allow_formulas,
            write_lock=write_lock,
        ),
        sheet,
    )


def _first_workbook_container(outputs: Sequence[OutputTargetConfig]) -> Optional[OutputContainerConfig]:
    for t in outputs:
        c = t.container
        if c is None:
            continue
        if str(c.type).lower() == "workbook" and c.path:
            return c
    return None


def compile_output_composition_from_yaml(  # noqa: C901
    config: DemandConfig,
    demand_ir: DemandIr,
) -> Optional[OutputCompositionSpec]:
    outputs = config.outputs
    if not outputs:
        if config.meta is not None or config.audit is not None:
            msg = "meta/audit requires outputs"
            raise ValueError(msg)
        return None

    reserved = {str(t.name) for t in outputs}
    if config.meta is not None and "meta" in reserved:
        msg = "outputs.*.name cannot be 'meta' when meta sheet is enabled"
        raise ValueError(msg)
    if config.audit is not None and "audit" in reserved:
        msg = "outputs.*.name cannot be 'audit' when audit sheet is enabled"
        raise ValueError(msg)

    engine = SecureComputeEngine()

    direct_targets: List[OutputTargetSpec] = []
    derived_targets: List[DerivedOutputTargetSpec] = []

    for idx, out_cfg in enumerate(outputs):
        is_primary = idx == 0
        requires = tuple(str(x) for x in (out_cfg.requires or ()))
        requires_opt = requires or None

        container = out_cfg.container
        if container is None:
            msg = "outputs.{} missing container".format(out_cfg.name)
            raise ValueError(msg)

        output_spec = _output_spec_from_container(container)

        predicate = None
        if out_cfg.where:
            predicate = _compile_where_predicate(engine=engine, expression=str(out_cfg.where), requires=requires)

        if out_cfg.aggregate is None:
            fields = out_cfg.fields or ()
            layout = export_layout_from_demand_ir(
                demand_ir,
                list(fields),
                header_fields_output_by=str(container.header_fields_output_by),
            )
            direct_targets.append(
                OutputTargetSpec(
                    target_id=str(out_cfg.name),
                    layout=layout,
                    output=output_spec,
                    predicate=predicate,
                    is_primary=bool(is_primary),
                    requires=requires_opt,
                )
            )
            continue

        agg = out_cfg.aggregate
        derived = _derived_group_by_spec_from_yaml(agg)
        out_layout_fields = _derived_output_layout_fields(agg)
        out_layout = _export_layout_for_derived(
            demand_ir=demand_ir,
            field_ids=out_layout_fields,
            header_fields_output_by=str(container.header_fields_output_by),
        )
        derived_targets.append(
            DerivedOutputTargetSpec(
                target_id=str(out_cfg.name),
                derived=derived,
                output_layout=out_layout,
                output=output_spec,
                predicate=predicate,
                is_primary=bool(is_primary),
                requires=requires_opt,
            )
        )

    workbook_default = _first_workbook_container(outputs)

    meta_sheet_spec = None
    if config.meta is not None:
        meta_out, meta_sheet_name = _compile_extra_sheet(
            target_id="meta",
            cfg=config.meta,
            default_sheet="__meta__",
            default_workbook_container=workbook_default,
        )
        meta_sheet_spec = MetaSheetSpec(target_id="meta", output=meta_out, sheet_name=meta_sheet_name)

    audit_sheet_spec = None
    if config.audit is not None:
        audit_out, audit_sheet_name = _compile_extra_sheet(
            target_id="audit",
            cfg=config.audit,
            default_sheet="__audit__",
            default_workbook_container=workbook_default,
        )
        audit_sheet_spec = AuditSheetSpec(target_id="audit", output=audit_out, sheet_name=audit_sheet_name)

    return OutputCompositionSpec(
        targets=tuple(direct_targets),
        derived_targets=tuple(derived_targets),
        meta_sheet=meta_sheet_spec,
        audit_sheet=audit_sheet_spec,
        failure_policy=str(config.failure_policy or "all_fail"),
        include_full_error_message=bool(config.include_full_error_message),
    )


__all__ = ["compile_output_composition_from_yaml"]
