from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

from ....execution.output_composition import (
    AggMetricSpec,
    AuditSheetSpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputRowPredicate,
    OutputTargetSpec,
    PostFieldSpec,
    RankFieldSpec,
)
from ....execution.output_contracts import ExportLayout, OutputSpec
from ....execution.run_ir import export_layout_from_demand_ir
from ....spec.ir.demand import DemandIr
from ....typedefs import FieldValue, RowData
from ..config_parsing.call_by import CallByParseError, CallByValue, ParsedCallBy, parse_call_by
from ..config_parsing.security import SecureComputeEngine
from ..schema_dsl.models import (
    DemandConfig,
    OutputAggregateConfig,
    OutputContainerConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
)
from .references import SecurePythonReferenceResolver

_AGG_FUNC_KEYS: Tuple[str, ...] = ("count", "sum", "min", "max", "count_true", "count_true_gte", "count_distinct")
_RANK_FUNC_KEYS: Tuple[str, ...] = ("row_number", "rank", "dense_rank")


def _ensure_field_value(value: object, *, field_id: str, producer: str) -> FieldValue:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal, str, bool)):
        return cast("FieldValue", value)
    msg = "aggregate field {!r} produced unsupported value type {} from {}".format(field_id, type(value).__name__, producer)
    raise TypeError(msg)


def _decimal_from_text(text: str) -> Optional[Decimal]:
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _to_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    dec: Optional[Decimal] = None
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, bool):
        dec = Decimal(1) if value else Decimal(0)
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, float):
        dec = _decimal_from_text(str(value))
    elif isinstance(value, str):
        dec = _decimal_from_text(value.strip())
    if dec is None:
        return None
    if not dec.is_finite():
        return None
    return dec


@dataclass(frozen=True)
class _AggregateCallByContext:
    row_id: Optional[object]
    batch_num: int
    field_id: str
    deps: Tuple[str, ...]
    values: Dict[str, FieldValue]


def _eval_call_by_value(*, field_id: str, value: CallByValue, row: RowData, ctx: _AggregateCallByContext) -> object:
    kind = str(value.kind)
    if kind == "literal":
        return value.value
    if kind == "field":
        return row.get(str(value.value))
    if kind == "ctx":
        return ctx
    if kind == "ctx_attr":
        return getattr(ctx, str(value.value))
    msg = "Unknown call_by value kind: {} (field_id={!r})".format(kind, field_id)  # pragma: no cover
    raise ValueError(msg)


def _compile_call_by_post_field(
    *,
    out_field_id: str,
    call_by: str,
    resolver: SecurePythonReferenceResolver,
) -> PostFieldSpec:
    try:
        parsed = parse_call_by(call_by)
    except CallByParseError as exc:
        msg = "aggregate.fields.{} has invalid call_by: {}".format(out_field_id, exc)
        raise ValueError(msg) from exc

    try:
        fn = cast("Callable[..., object]", resolver.resolve(parsed.reference))
    except Exception as exc:
        msg = "aggregate.fields.{} failed to resolve call_by reference '{}': {}".format(out_field_id, parsed.reference, exc)
        raise ValueError(msg) from exc

    deps = tuple(str(x) for x in (parsed.field_names or ()))

    def calculator(row: RowData, p: ParsedCallBy = parsed, f: Callable[..., object] = fn) -> FieldValue:
        dep_values: Dict[str, FieldValue] = {name: row.get(name) for name in deps}
        ctx = _AggregateCallByContext(
            row_id=None,
            batch_num=0,
            field_id=str(out_field_id),
            deps=deps,
            values=dep_values,
        )

        args: List[object] = []
        for arg_value in p.args:
            args.append(_eval_call_by_value(field_id=str(out_field_id), value=arg_value, row=row, ctx=ctx))

        kwargs: Dict[str, object] = {}
        for key, kw_value in p.kwargs:
            kwargs[str(key)] = _eval_call_by_value(field_id=str(out_field_id), value=kw_value, row=row, ctx=ctx)

        result = f(*args, **kwargs)
        return _ensure_field_value(result, field_id=str(out_field_id), producer="call_by")

    return PostFieldSpec(
        out_field_id=str(out_field_id),
        kind="call_by",
        dependencies=deps,
        fingerprint=str(call_by),
        calculator=calculator,
    )


def _compile_score_by_rank_post_field(
    *,
    out_field_id: str,
    cfg: Dict[str, Any],
) -> PostFieldSpec:
    rank_field = str(cfg.get("rank_field") or "rank").strip() or "rank"
    base_dec = _to_decimal(cfg.get("base"))
    step_dec = _to_decimal(cfg.get("step"))
    base = base_dec if base_dec is not None else Decimal(0)
    step = step_dec if step_dec is not None else Decimal(1)

    def calculator(row: RowData, rf: str = rank_field, b: Decimal = base, s: Decimal = step) -> FieldValue:
        raw_rank = row.get(rf)
        if raw_rank is None:
            return None
        try:
            rank_val = int(raw_rank)
        except Exception as exc:
            msg = "score_by_rank requires integer rank, got {} for rank_field={!r}".format(type(raw_rank).__name__, rf)
            raise TypeError(msg) from exc
        return b - (Decimal(rank_val - 1) * s)

    fingerprint = "rank_field={},base={},step={}".format(rank_field, str(base), str(step))
    return PostFieldSpec(
        out_field_id=str(out_field_id),
        kind="score_by_rank",
        dependencies=(rank_field,),
        fingerprint=fingerprint,
        calculator=calculator,
    )


def _get_field_name(field_id: str, demand_ir: DemandIr) -> str:
    field_ir = demand_ir.fields.get(field_id)
    name = getattr(field_ir, "name", "") or ""
    if name and name != field_id:
        return str(name)
    return field_id


def _get_derived_field_name(field_id: str, demand_ir: DemandIr, agg: OutputAggregateConfig) -> str:
    field_ir = demand_ir.fields.get(field_id)
    if field_ir is not None:
        return _get_field_name(field_id, demand_ir)

    agg_field = agg.fields.get(field_id)
    if agg_field is not None:
        name = str(getattr(agg_field, "name", "") or "").strip()
        if name and name != field_id:
            return name
    return field_id


def _export_layout_for_derived(
    *,
    demand_ir: DemandIr,
    agg: OutputAggregateConfig,
    field_ids: Sequence[str],
    header_fields_output_by: str,
) -> ExportLayout:
    normalized = tuple(str(x) for x in field_ids)
    if header_fields_output_by != "name":
        return ExportLayout(field_ids=normalized, header_names=None)

    names: List[str] = []
    has_diff = False
    for fid in normalized:
        resolved = _get_derived_field_name(fid, demand_ir, agg)
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


def _metric_spec_from_agg_field(*, out_field_id: str, producer_key: str, cfg: Dict[str, Any]) -> AggMetricSpec:
    field_id = str(cfg.get("field")) if cfg.get("field") else None
    field_ids = cfg.get("fields")
    field_ids_norm = tuple(str(x) for x in field_ids) if field_ids else None
    threshold = cfg.get("threshold")
    return AggMetricSpec(
        out_field_id=str(out_field_id),
        op=str(producer_key),
        field_id=field_id,
        field_ids=field_ids_norm,
        threshold=threshold,
    )


def _derived_group_by_spec_from_yaml(cfg: OutputAggregateConfig, *, resolver: SecurePythonReferenceResolver) -> DerivedGroupBySpec:
    metric_ids = sorted([fid for fid, fc in cfg.fields.items() if str(fc.producer_key) in _AGG_FUNC_KEYS])
    metrics = tuple(
        _metric_spec_from_agg_field(
            out_field_id=metric_id,
            producer_key=str(cfg.fields[metric_id].producer_key),
            cfg=cast("Dict[str, Any]", cfg.fields[metric_id].config),
        )
        for metric_id in metric_ids
    )

    rank_specs: List[RankFieldSpec] = []
    for out_field_id, field_cfg in cfg.fields.items():
        if str(field_cfg.producer_key) not in _RANK_FUNC_KEYS:
            continue
        raw = cast("Dict[str, Any]", field_cfg.config)
        rank_specs.append(
            RankFieldSpec(
                out_field_id=str(out_field_id),
                kind=str(field_cfg.producer_key),
                by=str(raw.get("by")),
                partition_by=tuple(str(x) for x in cast("Tuple[str, ...]", raw.get("partition_by") or ())),
                order=str(raw.get("order") or "desc"),
                order_by=tuple(str(x) for x in cast("Tuple[str, ...]", raw.get("order_by") or ())),
                top_k=int(raw.get("top_k") or 0),
                top_k_mode=str(raw.get("top_k_mode") or "rank"),
            )
        )

    post_specs: List[PostFieldSpec] = []
    for out_field_id, field_cfg in cfg.fields.items():
        producer_key = str(field_cfg.producer_key)
        if producer_key == "call_by":
            post_specs.append(
                _compile_call_by_post_field(
                    out_field_id=str(out_field_id),
                    call_by=str(field_cfg.config),
                    resolver=resolver,
                )
            )
        elif producer_key == "score_by_rank":
            post_specs.append(
                _compile_score_by_rank_post_field(
                    out_field_id=str(out_field_id),
                    cfg=cast("Dict[str, Any]", field_cfg.config),
                )
            )

    return DerivedGroupBySpec(
        group_by=tuple(str(x) for x in cfg.group_by),
        metrics=metrics,
        rank_fields=tuple(sorted(rank_specs, key=lambda r: str(r.out_field_id))),
        post_fields=tuple(sorted(post_specs, key=lambda p: str(p.out_field_id))),
        max_groups=int(cfg.max_groups),
        max_distinct=int(cfg.max_distinct),
        distinct_on_overflow=str(cfg.distinct_on_overflow),
    )


def _derived_output_layout_fields(cfg: OutputAggregateConfig) -> Tuple[str, ...]:
    metric_ids = sorted([fid for fid, fc in cfg.fields.items() if str(fc.producer_key) in _AGG_FUNC_KEYS])
    rank_ids = sorted([fid for fid, fc in cfg.fields.items() if str(fc.producer_key) in _RANK_FUNC_KEYS])
    post_ids = sorted([fid for fid, fc in cfg.fields.items() if str(fc.producer_key) in ("score_by_rank", "call_by")])
    fields: List[str] = list(cfg.group_by) + metric_ids + rank_ids + post_ids
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
    *,
    resolver: SecurePythonReferenceResolver,
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
        derived = _derived_group_by_spec_from_yaml(agg, resolver=resolver)
        out_layout_fields = tuple(str(x) for x in out_cfg.fields) if out_cfg.fields is not None else _derived_output_layout_fields(agg)
        out_layout = _export_layout_for_derived(
            demand_ir=demand_ir,
            agg=agg,
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
