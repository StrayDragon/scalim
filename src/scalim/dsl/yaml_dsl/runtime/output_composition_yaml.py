# pragma: allow-c901-file plan: c70
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple, cast

from ....execution.managed_artifacts import MANAGED_ARTIFACT_KIND_CSV, MANAGED_ARTIFACT_KIND_ROWS
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
from ....execution.versioned_outputs import book_output_relpath, file_output_relpath, validate_version_id
from ....spec.ir import DemandIr
from ....typedefs import FIELD_VALUE_TYPES, CellValue, FailurePolicy, FieldValue, RowData, format_field_value_expected_types
from ....vendor.dataclassesx import dataclass
from .._internal.book_identity import is_pathful_book
from .._internal.config_parsing.call_by import CallByValue, ParsedCallBy, ScalimCallByParseError, parse_call_by
from .._internal.config_parsing.security import (
    ScalimComputeExpressionError,
    ScalimSecurityError,
    SecureComputeEngine,
    build_compute_engine,
)
from .._internal.validation_contracts import validate_excel_sheet_name as _validate_excel_sheet_name_ssot
from ..schema_dsl.constants import DEFAULT_OUTPUT_HEADER_BY, DEFAULT_OUTPUT_INCLUDE_HEADER
from ..schema_dsl.models import (
    BookConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    FileConfig,
    OutputAggregateConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
)
from ..schema_dsl.output_enums import AGG_METRIC_PRODUCER_KEYS as _AGG_FUNC_KEYS
from ..schema_dsl.output_enums import AGG_POST_PRODUCER_KEYS as _POST_FUNC_KEYS
from ..schema_dsl.output_enums import AGG_RANK_PRODUCER_KEYS as _RANK_FUNC_KEYS
from ..schema_dsl.output_enums import DEFAULT_BOOK_WRITE_HEADER_POLICY, DEFAULT_BOOK_WRITE_MODE
from ._internal.call_by_signature import validate_call_by_signature
from ._internal.callable_preflight import ScalimCallablePreflightError
from .output_path_resolve import resolve_yaml_relative_output_path
from .references import SecurePythonReferenceResolver


def _validate_excel_sheet_name(sheet: str, *, path: str) -> None:
    _validate_excel_sheet_name_ssot(str(sheet), path=str(path))


def _ensure_field_value(value: Any, *, field_id: str, producer: str) -> FieldValue:
    if value is None:
        return None
    if isinstance(value, FIELD_VALUE_TYPES):
        return cast("FieldValue", value)  # pragma: allow-cast literal typed narrowing
    msg = "aggregate field {!r} produced unsupported value type {}; expected {} from {}".format(
        field_id,
        type(value).__name__,
        format_field_value_expected_types(),
        producer,
    )
    raise TypeError(msg)


def _decimal_from_text(text: str) -> Optional[Decimal]:
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _to_decimal(value: Any) -> Optional[Decimal]:
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


def _rendered_header_row(layout: ExportLayout) -> Tuple[str, ...]:
    header = layout.header_names if layout.header_names is not None else layout.field_ids
    return tuple(str(x) for x in header)


@dataclass(frozen=True)
class _AggregateCallByContext:
    row_id: Optional[Any]
    batch_num: int
    field_id: str
    deps: Tuple[str, ...]
    values: Dict[str, CellValue]


def _eval_call_by_value(*, field_id: str, value: CallByValue, row: RowData, ctx: _AggregateCallByContext) -> Any:
    kind = str(value.kind)
    if kind == "literal":
        return value.value
    if kind == "field":
        return row.get(str(value.value))
    if kind == "ctx":
        return ctx
    if kind == "ctx_attr":
        return getattr(ctx, str(value.value))  # pragma: allow-dynattr dsl: ctx_attr access
    msg = "Unknown call_by value kind: {} (field_id={!r})".format(
        kind, field_id
    )  # pragma: no cover  # pragma: allow-no-cover invariant: exhaustive CallByValue kind
    raise ValueError(msg)


def _compile_call_by_post_field(
    *,
    out_field_id: str,
    call_by: str,
    resolver: SecurePythonReferenceResolver,
) -> PostFieldSpec:
    try:
        parsed = parse_call_by(call_by)
    except ScalimCallByParseError as exc:
        msg = "aggregate.fields.{} has invalid call_by: {}".format(out_field_id, exc)
        raise ValueError(msg) from exc

    try:
        fn = resolver.resolve(parsed.reference)
    except Exception as exc:
        msg = "aggregate.fields.{} failed to resolve call_by reference '{}': {}".format(out_field_id, parsed.reference, exc)
        raise ValueError(msg) from exc

    try:
        validate_call_by_signature(
            location="aggregate.fields.{}".format(out_field_id),
            call_by=call_by,
            parsed=parsed,
            fn=fn,
        )
    except ScalimCallablePreflightError as exc:
        raise ValueError(str(exc)) from exc

    deps = tuple(str(x) for x in (parsed.field_names or ()))

    def calculator(row: RowData, p: ParsedCallBy = parsed, f: Callable[..., Any] = fn) -> FieldValue:
        dep_values: Dict[str, CellValue] = {name: row.get(name) for name in deps}
        ctx = _AggregateCallByContext(
            row_id=None,
            batch_num=0,
            field_id=str(out_field_id),
            deps=deps,
            values=dep_values,
        )

        args: List[Any] = []
        for arg_value in p.args:
            args.append(_eval_call_by_value(field_id=str(out_field_id), value=arg_value, row=row, ctx=ctx))

        kwargs: Dict[str, Any] = {}
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
        if isinstance(raw_rank, bool) or not isinstance(raw_rank, (int, float, Decimal, str)):
            msg = "score_by_rank requires integer rank, got {} for rank_field={!r}".format(type(raw_rank).__name__, rf)
            raise TypeError(msg)
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


def _compile_compute_post_field(
    *,
    out_field_id: str,
    cfg: Dict[str, Any],
    engine: SecureComputeEngine,
) -> PostFieldSpec:
    expr = str(cfg.get("expression") or "").strip()
    deps = tuple(str(x) for x in cast("Tuple[str, ...]", cfg.get("dependencies") or ()))  # pragma: allow-cast yaml tuple typed narrowing
    if not expr:
        msg = "aggregate.fields.{} has invalid compute config: missing expression".format(out_field_id)
        raise ValueError(msg)

    try:
        raw_calculator = cast("Callable[..., Any]", engine.compile(expr, deps))  # pragma: allow-cast compute engine compile typed narrowing
    except (ScalimComputeExpressionError, ScalimSecurityError) as exc:
        msg = "aggregate.fields.{} has invalid compute expression: {}".format(out_field_id, exc)
        raise ValueError(msg) from exc

    dep_keys = deps

    def calculator(row: RowData, c: Callable[..., Any] = raw_calculator) -> FieldValue:
        values = [row.get(key) for key in dep_keys]
        result = c(*values)
        return _ensure_field_value(result, field_id=str(out_field_id), producer="compute")

    return PostFieldSpec(
        out_field_id=str(out_field_id),
        kind="compute",
        dependencies=deps,
        fingerprint=expr,
        calculator=calculator,
    )


def _get_field_name(field_id: str, demand_ir: DemandIr) -> str:
    field_ir = demand_ir.fields.get(field_id)
    name = field_ir.name if field_ir is not None else ""
    if name and name != field_id:
        return str(name)
    return field_id


def _get_derived_field_name(field_id: str, demand_ir: DemandIr, agg: OutputAggregateConfig) -> str:
    field_ir = demand_ir.fields.get(field_id)
    if field_ir is not None:
        return _get_field_name(field_id, demand_ir)

    agg_field = agg.fields.get(field_id)
    if agg_field is not None:
        name = str(agg_field.name or "").strip()
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


def _output_spec_for_file_resource(file_cfg: FileConfig, *, path: Optional[str], include_header: bool) -> OutputSpec:
    return OutputSpec(
        format="csv",
        path=path,
        encoding=str(file_cfg.encoding),
        streaming=True,
        include_header=bool(include_header),
        sheet_name=None,
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


def _derived_group_by_spec_from_yaml(
    cfg: OutputAggregateConfig,
    *,
    resolver: SecurePythonReferenceResolver,
    compute_engine: SecureComputeEngine,
) -> DerivedGroupBySpec:
    metric_ids = sorted([fid for fid, fc in cfg.fields.items() if str(fc.producer_key) in _AGG_FUNC_KEYS])
    metrics = tuple(
        _metric_spec_from_agg_field(
            out_field_id=metric_id,
            producer_key=str(cfg.fields[metric_id].producer_key),
            cfg=cast("Dict[str, Any]", cfg.fields[metric_id].config),  # pragma: allow-cast yaml mapping typed narrowing
        )
        for metric_id in metric_ids
    )

    rank_specs: List[RankFieldSpec] = []
    for out_field_id, field_cfg in cfg.fields.items():
        if str(field_cfg.producer_key) not in _RANK_FUNC_KEYS:
            continue
        raw = cast("Dict[str, Any]", field_cfg.config)  # pragma: allow-cast yaml mapping typed narrowing
        partition_by_raw = cast("Tuple[str, ...]", raw.get("partition_by") or ())  # pragma: allow-cast yaml tuple typed narrowing
        order_by_raw = cast("Tuple[str, ...]", raw.get("order_by") or ())  # pragma: allow-cast yaml tuple typed narrowing
        rank_specs.append(
            RankFieldSpec(
                out_field_id=str(out_field_id),
                kind=str(field_cfg.producer_key),
                by=str(raw.get("by")),
                partition_by=tuple(str(x) for x in partition_by_raw),
                order=str(raw.get("order") or "desc"),
                order_by=tuple(str(x) for x in order_by_raw),
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
                    cfg=cast("Dict[str, Any]", field_cfg.config),  # pragma: allow-cast yaml mapping typed narrowing
                )
            )
        elif producer_key == "compute":
            post_specs.append(
                _compile_compute_post_field(
                    out_field_id=str(out_field_id),
                    cfg=cast("Dict[str, Any]", field_cfg.config),  # pragma: allow-cast yaml mapping typed narrowing
                    engine=compute_engine,
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
    post_ids = sorted([fid for fid, fc in cfg.fields.items() if str(fc.producer_key) in _POST_FUNC_KEYS])
    fields: List[str] = list(cfg.group_by) + metric_ids + rank_ids + post_ids
    return tuple(str(x) for x in fields)


def _compile_extra_sheet(
    *,
    target_id: str,
    cfg: OutputExtraSheetConfig,
    default_sheet: str,
    default_workbook_path: Optional[str],
    default_allow_formulas: bool,
    as_in_memory_csv: bool,
) -> Tuple[OutputSpec, str]:
    sheet = str(cfg.sheet) if cfg.sheet else str(default_sheet)

    if as_in_memory_csv:
        if cfg.path:
            msg = "{}.path is not supported in workflow-managed mode (meta/audit must be written via books write nodes)".format(target_id)
            raise ValueError(msg)
        return (OutputSpec(format="csv", path=None, streaming=True, include_header=True), sheet)

    path = str(cfg.path).strip() if cfg.path else (str(default_workbook_path) if default_workbook_path else "")
    if not path:
        msg = "{} requires a workbook path (set {}.path or provide at least one workbook output)".format(target_id, target_id)
        raise ValueError(msg)
    allow_formulas = default_allow_formulas if cfg.allow_formulas is None else bool(cfg.allow_formulas)
    return (
        OutputSpec(
            format="excel",
            path=path,
            excel_allow_formulas=allow_formulas,
        ),
        sheet,
    )


def _maybe_compile_extra_sheet(
    *,
    target_id: str,
    cfg: Optional[OutputExtraSheetConfig],
    default_sheet: str,
    default_workbook_path: Optional[str],
    default_allow_formulas: bool,
    skip_without_workbook: bool,
    as_in_memory_csv: bool,
) -> Optional[Tuple[OutputSpec, str]]:
    if cfg is None or (not as_in_memory_csv and skip_without_workbook and cfg.path is None and default_workbook_path is None):
        return None

    out, sheet_name = _compile_extra_sheet(
        target_id=target_id,
        cfg=cfg,
        default_sheet=default_sheet,
        default_workbook_path=default_workbook_path,
        default_allow_formulas=default_allow_formulas,
        as_in_memory_csv=as_in_memory_csv,
    )
    return out, sheet_name


def _validate_extra_sheet_target_names(config: DemandConfig, *, outputs_path: str) -> None:
    outputs = config.outputs or ()
    reserved = {str(t.name) for t in outputs}
    if config.meta is not None and "meta" in reserved:
        msg = "{}.*.name cannot be 'meta' when meta sheet is enabled".format(outputs_path)
        raise ValueError(msg)
    if config.audit is not None and "audit" in reserved:
        msg = "{}.*.name cannot be 'audit' when audit sheet is enabled".format(outputs_path)
        raise ValueError(msg)


def _effective_file_id_for_output(
    out_cfg: OutputTargetConfig,
    *,
    idx: int,
    outputs_path: str,
) -> Tuple[Optional[str], str]:
    file_ref_path = "{}.{}.to.file".format(outputs_path, int(idx))
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.file is not None:
        candidate = str(to_cfg.file or "").strip()
        if candidate:
            return candidate, file_ref_path
    return None, file_ref_path


def _effective_book_id_for_output(
    out_cfg: OutputTargetConfig,
    *,
    idx: int,
    outputs_path: str,
) -> Tuple[Optional[str], str]:
    book_ref_path = "{}.{}.to.book".format(outputs_path, int(idx))
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.book is not None:
        candidate = str(to_cfg.book or "").strip()
        if candidate:
            return candidate, book_ref_path

    return None, book_ref_path


def _effective_sheet_name_for_output(out_cfg: OutputTargetConfig, *, idx: int, outputs_path: str) -> Tuple[str, str, bool]:
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.sheet is not None:
        sheet_raw = str(to_cfg.sheet or "").strip()
        return sheet_raw, "{}.{}.to.sheet".format(outputs_path, int(idx)), False
    return str(out_cfg.name or ""), "{}.{}.name".format(outputs_path, int(idx)), True


def _require_file_resource(config: DemandConfig, *, file_id: str, file_ref_path: str) -> FileConfig:
    resources = config.resources
    files = resources.files if resources is not None else {}
    file_cfg = files.get(str(file_id))
    if file_cfg is None:
        msg = (
            "Missing file resource id {!r} referenced by {}. "
            "Hint: declare resources.files.{} in the demand YAML, declare workflow.resources.files.{} in the workflow YAML, "
            "or provide overrides.resources.files.{} in Python."
        ).format(str(file_id), str(file_ref_path), str(file_id), str(file_id), str(file_id))
        err = "{} (path={})".format(msg, str(file_ref_path))
        raise ValueError(err)
    return file_cfg


def _require_book_resource(config: DemandConfig, *, book_id: str, book_ref_path: str) -> BookConfig:
    resources = config.resources
    books = resources.books if resources is not None else {}
    book = books.get(str(book_id))
    if book is None:
        msg = (
            "Missing book resource id {!r} referenced by {}. "
            "Hint: declare resources.books.{} in the demand YAML, declare workflow.resources.books.{} in the workflow YAML, "
            "or provide overrides.resources.books.{} in Python."
        ).format(str(book_id), str(book_ref_path), str(book_id), str(book_id), str(book_id))
        err = "{} (path={})".format(msg, str(book_ref_path))
        raise ValueError(err)
    return book


_VERSIONED_OUTPUT_MIGRATION_HINT = (
    "Migration: set path to an output root directory (e.g. './out'), and locate outputs via <root>/manifest/latest.json."
)


def _validate_output_root_path(root: str, *, path: str) -> None:
    # `path` 语义升级为 `output root` (目录); 旧语义常见为 `./out/report.xlsx` / `./out/detail.csv`。
    suffix = Path(str(root)).suffix.lower()
    if suffix in (".xlsx", ".csv"):
        msg = "{} now expects an output root directory, not a file path: {!r}. {}".format(
            str(path), str(root), _VERSIONED_OUTPUT_MIGRATION_HINT
        )
        raise ValueError(msg)


def _versioned_file_output_path(*, output_root: str, version_id: str, file_id: str) -> str:
    vid = validate_version_id(str(version_id))
    rel = file_output_relpath(file_id=str(file_id))
    return str(Path(str(output_root)) / "versions" / str(vid) / Path(str(rel)))


def _versioned_book_output_path(*, output_root: str, version_id: str, book_id: str) -> str:
    vid = validate_version_id(str(version_id))
    rel = book_output_relpath(book_id=str(book_id))
    return str(Path(str(output_root)) / "versions" / str(vid) / Path(str(rel)))


def _resolve_file_export_path(
    config: DemandConfig,
    *,
    file_id: str,
    file_ref_path: str,
    yaml_base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    version_id: str,
) -> Tuple[str, FileConfig]:
    file_cfg = _require_file_resource(config, file_id=str(file_id), file_ref_path=str(file_ref_path))
    output_root = resolve_yaml_relative_output_path(
        file_cfg.path,
        base_dir=str(yaml_base_dir),
        init_vars=init_vars,
        path="resources.files.{}.csv_file.path".format(str(file_id)),
    )
    _validate_output_root_path(str(output_root), path="resources.files.{}.csv_file.path".format(str(file_id)))
    export_path = _versioned_file_output_path(output_root=str(output_root), version_id=str(version_id), file_id=str(file_id))
    return export_path, file_cfg


def _resolve_book_export_path(
    config: DemandConfig,
    *,
    book_id: str,
    book_ref_path: str,
    yaml_base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    version_id: str,
) -> Tuple[str, bool]:
    book = _require_book_resource(config, book_id=str(book_id), book_ref_path=str(book_ref_path))

    if is_pathful_book(book):
        output_root = resolve_yaml_relative_output_path(
            book.path,
            base_dir=str(yaml_base_dir),
            init_vars=init_vars,
            path="resources.books.{}.xlsx.path".format(str(book_id)),
        )
        _validate_output_root_path(str(output_root), path="resources.books.{}.xlsx.path".format(str(book_id)))
        export_path = _versioned_book_output_path(output_root=str(output_root), version_id=str(version_id), book_id=str(book_id))
        return export_path, bool(book.allow_formulas)

    # `pathless`: `standalone` `export` 仅当仍带 `export_xlsx`(过渡期 `override` / 旧形状)
    export = book.export_xlsx
    if export is None:
        msg = (
            "pathless book requires export_xlsx for standalone xlsx export (book_id={!r}); "
            "prefer resources.books.{}.xlsx.path or run in a workflow"
        ).format(str(book_id), str(book_id))
        path_ref = "resources.books.{}.export_xlsx".format(str(book_id))
        err = "{} (path={})".format(msg, path_ref)
        raise ValueError(err)
    output_root = resolve_yaml_relative_output_path(
        export.path,
        base_dir=str(yaml_base_dir),
        init_vars=init_vars,
        path="resources.books.{}.export_xlsx.path".format(str(book_id)),
    )
    _validate_output_root_path(str(output_root), path="resources.books.{}.export_xlsx.path".format(str(book_id)))
    export_path = _versioned_book_output_path(output_root=str(output_root), version_id=str(version_id), book_id=str(book_id))
    return export_path, bool(export.allow_formulas)


def _try_resolve_workflow_managed_book_export_path(
    book: BookConfig,
    *,
    book_id: str,
    yaml_base_dir: str,
    init_vars: Optional[Dict[str, Any]],
    version_id: str,
) -> Optional[str]:
    """为 `workflow-managed` 的 `book` 输出解析“可能存在”的最终导出路径.

    - `pathful`: 始终可导出,返回版本化 `.xlsx` 文件路径
    - `pathless`: 仅当声明 `export_xlsx` 时返回导出路径;否则返回 `None`(仅内存态)
    """
    if is_pathful_book(book):
        output_root = resolve_yaml_relative_output_path(
            book.path,
            base_dir=str(yaml_base_dir),
            init_vars=init_vars,
            path="resources.books.{}.xlsx.path".format(str(book_id)),
        )
        _validate_output_root_path(str(output_root), path="resources.books.{}.xlsx.path".format(str(book_id)))
        return _versioned_book_output_path(output_root=str(output_root), version_id=str(version_id), book_id=str(book_id))

    export = book.export_xlsx
    if export is None:
        return None
    output_root = resolve_yaml_relative_output_path(
        export.path,
        base_dir=str(yaml_base_dir),
        init_vars=init_vars,
        path="resources.books.{}.export_xlsx.path".format(str(book_id)),
    )
    _validate_output_root_path(str(output_root), path="resources.books.{}.export_xlsx.path".format(str(book_id)))
    return _versioned_book_output_path(output_root=str(output_root), version_id=str(version_id), book_id=str(book_id))


def _effective_book_write_defaults(book: BookConfig) -> BookWriteDefaultsConfig:
    base = book.write_defaults
    if base is None:
        base = BookWriteDefaultsConfig(
            mode=str(DEFAULT_BOOK_WRITE_MODE),
            header_policy=str(DEFAULT_BOOK_WRITE_HEADER_POLICY),
        )
    return base


def _effective_output_header_fields_output_by(
    *,
    out_cfg: OutputTargetConfig,
) -> str:
    write_cfg = out_cfg.write
    if write_cfg is not None and write_cfg.header_fields_output_by is not None:
        return str(write_cfg.header_fields_output_by)

    return str(DEFAULT_OUTPUT_HEADER_BY)


def _effective_output_include_header(
    *,
    out_cfg: OutputTargetConfig,
    mode: Optional[str],
    header_policy: Optional[str],
    include_header_path: str,
    header_policy_path: Optional[str] = None,
) -> bool:
    write_cfg = out_cfg.write
    if mode == "append":
        if write_cfg is not None and write_cfg.include_header is not None:
            hint_path = str(header_policy_path or "resources.books.*.write_defaults.header_policy")
            msg = "{} is not allowed for append-mode book outputs; use {}".format(include_header_path, hint_path)
            raise ValueError(msg)
        return str(header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY) != "never"

    if write_cfg is not None and write_cfg.include_header is not None:
        return bool(write_cfg.include_header)
    return bool(DEFAULT_OUTPUT_INCLUDE_HEADER)


def _validate_xlsx_memory_write_contract(
    *,
    book: BookConfig,
    book_id: str,
) -> None:
    if is_pathful_book(book):
        return

    effective_defaults = _effective_book_write_defaults(book)
    if str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE) != "append":
        return
    if str(effective_defaults.align_by or "") != "header":
        return

    align_by_path = "resources.books.{}.write_defaults.align_by".format(str(book_id))
    msg = (
        "pathless books (in-memory bus) do not support write_defaults.align_by=header; "
        "internal rows only use canonical field keys. Migrate to resources.books.<book_id>.write_defaults.align_by=field_id "
        "and keep write.header_fields_output_by for export display (book_id={!r})"
    ).format(str(book_id))
    err = "{} (path={})".format(msg, str(align_by_path))
    raise ValueError(err)


def compile_output_composition_from_yaml(  # noqa: C901, PLR0912, PLR0915
    config: DemandConfig,
    demand_ir: DemandIr,
    *,
    version_id: str,
    resolver: SecurePythonReferenceResolver,
    init_vars: Optional[Dict[str, Any]] = None,
    yaml_base_dir: Optional[str] = None,
    workflow_managed_output_ids: Optional[FrozenSet[str]] = None,
    outputs_path: str = "outputs",
    skip_extra_sheets_without_workbook: bool = False,
) -> Optional[OutputCompositionSpec]:
    outputs = config.outputs
    if not outputs:
        if config.meta is not None or config.audit is not None:
            msg = "meta/audit requires outputs"
            raise ValueError(msg)
        return None

    _validate_extra_sheet_target_names(config, outputs_path=outputs_path)

    engine = build_compute_engine()

    direct_targets: List[OutputTargetSpec] = []
    derived_targets: List[DerivedOutputTargetSpec] = []
    workbook_default_path: Optional[str] = None
    workbook_default_allow_formulas = True

    version_id = validate_version_id(str(version_id))

    for idx, out_cfg in enumerate(outputs):
        is_primary = idx == 0
        requires = tuple(str(x) for x in (out_cfg.requires or ()))
        requires_opt = requires or None

        in_memory = False
        book: Optional[BookConfig] = None
        book_id: Optional[str] = None
        workflow_export_header: Optional[Tuple[str, ...]] = None
        managed_artifact_kind: Optional[str] = None
        output_spec: OutputSpec
        header_by = str(DEFAULT_OUTPUT_HEADER_BY)

        file_id, file_ref_path = _effective_file_id_for_output(out_cfg, idx=int(idx), outputs_path=str(outputs_path))
        file_id = str(file_id or "").strip()
        if file_id:
            if yaml_base_dir is None:
                msg = "yaml_base_dir is required to resolve resources.files output paths"
                raise ValueError(msg)
            export_path, file_cfg = _resolve_file_export_path(
                config,
                file_id=str(file_id),
                file_ref_path=str(file_ref_path),
                yaml_base_dir=str(yaml_base_dir),
                init_vars=init_vars,
                version_id=str(version_id),
            )
            include_header = _effective_output_include_header(
                out_cfg=out_cfg,
                mode=None,
                header_policy=None,
                include_header_path="{}.{}.write.include_header".format(outputs_path, idx),
            )
            if workflow_managed_output_ids is not None and str(out_cfg.name) in workflow_managed_output_ids:
                in_memory = True
                managed_artifact_kind = MANAGED_ARTIFACT_KIND_CSV
                output_spec = OutputSpec(format="csv", path=str(export_path), streaming=True, include_header=bool(include_header))
            else:
                output_spec = _output_spec_for_file_resource(file_cfg, path=export_path, include_header=include_header)
            header_by = _effective_output_header_fields_output_by(out_cfg=out_cfg)
        else:
            book_id, book_ref_path = _effective_book_id_for_output(out_cfg, idx=int(idx), outputs_path=str(outputs_path))
            if book_id is None:
                msg = (
                    "Missing output destination for output {!r}; set {}.{}.to.file or {}.{}.to.book explicitly. "
                    "Reuse the binding with YAML anchors (`_templates`) or `$import` if needed."
                ).format(str(out_cfg.name), str(outputs_path), int(idx), str(outputs_path), int(idx))
                err = "{} (path={})".format(msg, book_ref_path)
                raise ValueError(err)
            book = _require_book_resource(config, book_id=str(book_id), book_ref_path=str(book_ref_path))
            _validate_xlsx_memory_write_contract(
                book=book,
                book_id=str(book_id),
            )

            sheet_name, sheet_ref_path, defaulted_from_name = _effective_sheet_name_for_output(
                out_cfg, idx=int(idx), outputs_path=str(outputs_path)
            )
            sheet_name = str(sheet_name or "").strip()
            try:
                _validate_excel_sheet_name(sheet_name, path=sheet_ref_path)
            except ValueError as exc:
                if defaulted_from_name:
                    msg = ("Invalid default Excel sheet name for output {!r}; set {}.{}.to.sheet explicitly. {}").format(
                        str(out_cfg.name), str(outputs_path), int(idx), exc
                    )
                    raise ValueError(msg) from exc
                raise

            if workflow_managed_output_ids is not None and str(out_cfg.name) in workflow_managed_output_ids:
                in_memory = True
                export_path = None
                if yaml_base_dir is not None:
                    export_path = _try_resolve_workflow_managed_book_export_path(
                        book,
                        book_id=str(book_id),
                        yaml_base_dir=str(yaml_base_dir),
                        init_vars=init_vars,
                        version_id=str(version_id),
                    )
                effective_defaults = _effective_book_write_defaults(book)
                include_header = _effective_output_include_header(
                    out_cfg=out_cfg,
                    mode=str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE),
                    header_policy=str(effective_defaults.header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY),
                    include_header_path="{}.{}.write.include_header".format(outputs_path, idx),
                    header_policy_path="resources.books.{}.write_defaults.header_policy".format(str(book_id)),
                )
                # `MANAGED_ARTIFACT_KIND_ROWS` = 类型化行工件(`InMemoryRows`/`FieldValue`);
                # 与 `MANAGED_ARTIFACT_KIND_CSV`(字符串化)相对。不是 `pipeline` 的列写(`IColumnSink`)
                # 或块列写(`BlockColumnCSVSink`)模式——那些是 `sink` 布局,不在 `managed-artifact kind` 闭集内。
                managed_artifact_kind = MANAGED_ARTIFACT_KIND_ROWS
                output_spec = OutputSpec(
                    format="excel",
                    path=str(export_path) if export_path else None,
                    streaming=True,
                    include_header=bool(include_header),
                    sheet_name=str(sheet_name),
                )
            else:
                if yaml_base_dir is None:
                    msg = "yaml_base_dir is required to resolve resources.books output paths"
                    raise ValueError(msg)
                effective_defaults = _effective_book_write_defaults(book)
                include_header = _effective_output_include_header(
                    out_cfg=out_cfg,
                    mode=str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE),
                    header_policy=str(effective_defaults.header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY),
                    include_header_path="{}.{}.write.include_header".format(outputs_path, idx),
                    header_policy_path="resources.books.{}.write_defaults.header_policy".format(str(book_id)),
                )
                export_path, allow_formulas = _resolve_book_export_path(
                    config,
                    book_id=str(book_id),
                    book_ref_path=str(book_ref_path),
                    yaml_base_dir=str(yaml_base_dir),
                    init_vars=init_vars,
                    version_id=str(version_id),
                )
                output_spec = OutputSpec(
                    format="excel",
                    path=str(export_path),
                    streaming=True,
                    include_header=bool(include_header),
                    sheet_name=str(sheet_name),
                    excel_allow_formulas=bool(allow_formulas),
                )
                if workbook_default_path is None:
                    workbook_default_path = str(export_path)
                    workbook_default_allow_formulas = bool(allow_formulas)
            header_by = _effective_output_header_fields_output_by(out_cfg=out_cfg)

        predicate = None
        if out_cfg.where:
            predicate = _compile_where_predicate(engine=engine, expression=str(out_cfg.where), requires=requires)

        if out_cfg.aggregate is None:
            fields = out_cfg.fields or ()
            layout_header_by = str(header_by)
            if in_memory:
                export_layout = export_layout_from_demand_ir(
                    demand_ir,
                    list(fields),
                    header_fields_output_by=str(header_by),
                )
                workflow_export_header = _rendered_header_row(export_layout)
                layout_header_by = "field_id"
            layout = export_layout_from_demand_ir(
                demand_ir,
                list(fields),
                header_fields_output_by=str(layout_header_by),
            )
            direct_targets.append(
                OutputTargetSpec(
                    target_id=str(out_cfg.name),
                    layout=layout,
                    output=output_spec,
                    in_memory=bool(in_memory),
                    predicate=predicate,
                    is_primary=bool(is_primary),
                    requires=requires_opt,
                    workflow_export_header=workflow_export_header,
                    managed_artifact_kind=managed_artifact_kind if in_memory else None,
                )
            )
            continue

        agg = out_cfg.aggregate
        derived = _derived_group_by_spec_from_yaml(agg, resolver=resolver, compute_engine=engine)
        out_layout_fields = tuple(str(x) for x in out_cfg.fields) if out_cfg.fields is not None else _derived_output_layout_fields(agg)
        out_layout_header_by = str(header_by)
        if in_memory:
            export_layout = _export_layout_for_derived(
                demand_ir=demand_ir,
                agg=agg,
                field_ids=out_layout_fields,
                header_fields_output_by=str(header_by),
            )
            workflow_export_header = _rendered_header_row(export_layout)
            out_layout_header_by = "field_id"
        out_layout = _export_layout_for_derived(
            demand_ir=demand_ir,
            agg=agg,
            field_ids=out_layout_fields,
            header_fields_output_by=str(out_layout_header_by),
        )
        derived_targets.append(
            DerivedOutputTargetSpec(
                target_id=str(out_cfg.name),
                derived=derived,
                output_layout=out_layout,
                output=output_spec,
                in_memory=bool(in_memory),
                predicate=predicate,
                is_primary=bool(is_primary),
                requires=requires_opt,
                workflow_export_header=workflow_export_header,
                managed_artifact_kind=managed_artifact_kind if in_memory else None,
            )
        )

    meta_sheet_spec = None
    meta_sheet_compiled = _maybe_compile_extra_sheet(
        target_id="meta",
        cfg=config.meta,
        default_sheet="__meta__",
        default_workbook_path=workbook_default_path,
        default_allow_formulas=workbook_default_allow_formulas,
        skip_without_workbook=skip_extra_sheets_without_workbook,
        as_in_memory_csv=workflow_managed_output_ids is not None,
    )
    if meta_sheet_compiled is not None:
        meta_out, meta_sheet_name = meta_sheet_compiled
        meta_sheet_spec = MetaSheetSpec(
            target_id="meta",
            output=meta_out,
            sheet_name=meta_sheet_name,
            in_memory=workflow_managed_output_ids is not None,
        )

    audit_sheet_spec = None
    audit_sheet_compiled = _maybe_compile_extra_sheet(
        target_id="audit",
        cfg=config.audit,
        default_sheet="__audit__",
        default_workbook_path=workbook_default_path,
        default_allow_formulas=workbook_default_allow_formulas,
        skip_without_workbook=skip_extra_sheets_without_workbook,
        as_in_memory_csv=workflow_managed_output_ids is not None,
    )
    if audit_sheet_compiled is not None:
        audit_out, audit_sheet_name = audit_sheet_compiled
        audit_sheet_spec = AuditSheetSpec(
            target_id="audit",
            output=audit_out,
            sheet_name=audit_sheet_name,
            in_memory=workflow_managed_output_ids is not None,
        )

    return OutputCompositionSpec(
        targets=tuple(direct_targets),
        derived_targets=tuple(derived_targets),
        meta_sheet=meta_sheet_spec,
        audit_sheet=audit_sheet_spec,
        failure_policy=str(config.failure_policy or FailurePolicy.ALL_FAIL.value),
        include_full_error_message=bool(config.include_full_error_message),
    )


__all__ = ("compile_output_composition_from_yaml",)
