"""`workflow` 编译阶段实现(内部模块).

说明:
- 承载 `workflow config` -> `workflow IR` 的编译逻辑
- 运行时需兼容 `Python 3.6`
"""

from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ...spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowArtifactsIr,
    WorkflowCachePoolBudgetIr,
    WorkflowCachePoolIr,
    WorkflowCachePoolPinIr,
    WorkflowCtxOptionsIr,
    WorkflowEdgeIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
    WorkflowOutputStagingOptionsIr,
    WorkflowResourceIr,
    WorkflowResourcesWaitDiagnosticsIr,
    WorkflowResourcesWaitOptionsIr,
    WriteSheetNodeIr,
)
from ...vendor.dataclassesx import replace
from ._internal.config_parsing.loader import YamlDemandLoader
from .runtime.contracts import (
    BookResourceOverride,
    FileResourceOverride,
    OutputOverride,
    OutputsDefaultsOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResourcesOverride,
    RunOverrides,
)
from .runtime.output_path_resolve import resolve_yaml_relative_output_path
from .schema_dsl.constants import DEFAULT_OUTPUT_ENCODING
from .schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    FileConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
)
from .schema_dsl.output_enums import (
    BOOK_WRITE_ALIGN_BY_ENUM,
    BOOK_WRITE_HEADER_POLICY_ENUM,
    BOOK_WRITE_MODE_ENUM,
    BOOK_WRITE_ON_CONFLICT_ENUM,
    BOOK_WRITE_ON_MISMATCH_ENUM,
    DEFAULT_BOOK_WRITE_ALIGN_BY,
    DEFAULT_BOOK_WRITE_HEADER_POLICY,
    DEFAULT_BOOK_WRITE_MODE,
    DEFAULT_BOOK_WRITE_ON_CONFLICT,
    DEFAULT_BOOK_WRITE_ON_MISMATCH,
    FILE_KINDS,
)
from .workflow import ScalimWorkflowConfigError, WorkflowConfig, resolve_workflow_demand_path

_INTERNAL_NODE_ID_PREFIX = "__wf__"

_INVALID_EXCEL_SHEET_CHARS: FrozenSet[str] = frozenset(["\\", "/", "?", "*", "[", "]", ":"])
_EXCEL_SHEET_NAME_MAX_LEN = 31


def _as_abs_path(raw_path: str) -> str:
    return str(Path(str(raw_path)).expanduser().resolve(strict=False))


def _try_resolve_book_export_abs_path(
    book: BookConfig,
    *,
    book_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, object]],
    path_prefix: str,
) -> Optional[str]:
    try:
        export_path, _opts = _book_export_path_and_options(
            book,
            book_id=str(book_id),
            base_dir=str(base_dir),
            init_vars=init_vars,
            path_prefix=str(path_prefix),
        )
    except (TypeError, ValueError):
        return None
    if not export_path:
        return None
    return _as_abs_path(str(export_path))


def _validate_excel_sheet_name(sheet: str, *, path: str) -> None:
    name = str(sheet or "").strip()
    if not name:
        msg = "{} is required".format(path)
        raise ValueError(msg)
    if len(name) > _EXCEL_SHEET_NAME_MAX_LEN:
        msg = "Excel sheet name is too long: len={} > {}".format(len(name), _EXCEL_SHEET_NAME_MAX_LEN)
        err = "{} (path={})".format(msg, path)
        raise ValueError(err)
    for ch in _INVALID_EXCEL_SHEET_CHARS:
        if ch in name:
            msg = "Excel sheet name contains invalid character {!r}".format(ch)
            err = "{} (path={})".format(msg, path)
            raise ValueError(err)


def _workflow_base_dir(workflow_yaml_path: str) -> Path:
    wf_path = Path(str(workflow_yaml_path or "")).expanduser().resolve(strict=False)
    return wf_path.parent


def _demand_base_dir(demand_yaml_path: str) -> Path:
    p = Path(str(demand_yaml_path or "")).expanduser().resolve(strict=False)
    return p.parent


def _outputs_path_ref(outputs_path: str, idx: int, suffix: str) -> str:
    return "{}.{}.{}".format(str(outputs_path), int(idx), suffix)


def _effective_book_binding_for_output(
    out_cfg: OutputTargetConfig,
    *,
    idx: int,
    outputs_path: str,
) -> Tuple[Optional[str], str]:
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.book is not None:
        book = str(to_cfg.book or "").strip()
        if book:
            return book, _outputs_path_ref(outputs_path, int(idx), "to.book")

    return None, _outputs_path_ref(outputs_path, int(idx), "to.book")


def _effective_file_binding_for_output(
    out_cfg: OutputTargetConfig,
    *,
    idx: int,
    outputs_path: str,
) -> Tuple[Optional[str], str]:
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.file is not None:
        file_id = str(to_cfg.file or "").strip()
        if file_id:
            return file_id, _outputs_path_ref(outputs_path, int(idx), "to.file")

    return None, _outputs_path_ref(outputs_path, int(idx), "to.file")


def _effective_sheet_name_for_output(out_cfg: OutputTargetConfig, *, idx: int, outputs_path: str) -> Tuple[str, str]:
    to_cfg = out_cfg.to
    if to_cfg is not None and to_cfg.sheet is not None:
        return str(to_cfg.sheet or "").strip(), _outputs_path_ref(outputs_path, int(idx), "to.sheet")
    return str(out_cfg.name or ""), _outputs_path_ref(outputs_path, int(idx), "name")


def _effective_write_defaults(book: BookConfig) -> BookWriteDefaultsConfig:
    base = book.write_defaults
    if base is not None:
        return base
    return BookWriteDefaultsConfig(
        mode=str(DEFAULT_BOOK_WRITE_MODE),
        align_by=str(DEFAULT_BOOK_WRITE_ALIGN_BY),
        header_policy=str(DEFAULT_BOOK_WRITE_HEADER_POLICY),
        on_mismatch=str(DEFAULT_BOOK_WRITE_ON_MISMATCH),
        on_conflict=str(DEFAULT_BOOK_WRITE_ON_CONFLICT),
    )


def _overlay_write_defaults(base: BookWriteDefaultsConfig, override: Optional[OutputWriteConfig]) -> BookWriteDefaultsConfig:
    if override is None:
        return base

    mode = base.mode if override.mode is None else str(override.mode)
    align_by = base.align_by if override.align_by is None else str(override.align_by)
    header_policy = base.header_policy if override.header_policy is None else str(override.header_policy)
    on_mismatch = base.on_mismatch if override.on_mismatch is None else str(override.on_mismatch)
    on_conflict = base.on_conflict if override.on_conflict is None else str(override.on_conflict)

    if mode not in BOOK_WRITE_MODE_ENUM:
        msg = "Invalid write.mode={!r}; expected one of: {}".format(mode, ", ".join(BOOK_WRITE_MODE_ENUM))
        raise ValueError(msg)
    if align_by not in BOOK_WRITE_ALIGN_BY_ENUM:
        msg = "Invalid write.align_by={!r}; expected one of: {}".format(align_by, ", ".join(BOOK_WRITE_ALIGN_BY_ENUM))
        raise ValueError(msg)
    if header_policy not in BOOK_WRITE_HEADER_POLICY_ENUM:
        msg = "Invalid write.header_policy={!r}; expected one of: {}".format(header_policy, ", ".join(BOOK_WRITE_HEADER_POLICY_ENUM))
        raise ValueError(msg)
    if on_mismatch not in BOOK_WRITE_ON_MISMATCH_ENUM:
        msg = "Invalid write.on_mismatch={!r}; expected one of: {}".format(on_mismatch, ", ".join(BOOK_WRITE_ON_MISMATCH_ENUM))
        raise ValueError(msg)
    if on_conflict not in BOOK_WRITE_ON_CONFLICT_ENUM:
        msg = "Invalid write.on_conflict={!r}; expected one of: {}".format(on_conflict, ", ".join(BOOK_WRITE_ON_CONFLICT_ENUM))
        raise ValueError(msg)

    return BookWriteDefaultsConfig(
        mode=str(mode),
        align_by=str(align_by),
        header_policy=str(header_policy),
        on_mismatch=str(on_mismatch),
        on_conflict=str(on_conflict),
    )


def _validate_xlsx_memory_align_by(
    *,
    book: BookConfig,
    book_id: str,
    out_cfg: OutputTargetConfig,
    idx: int,
    outputs_path: str,
) -> None:
    if str(book.kind or "").strip() != "xlsx_memory":
        return

    effective_defaults = _overlay_write_defaults(_effective_write_defaults(book), out_cfg.write)
    if str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE) != "append":
        return
    if str(effective_defaults.align_by or "") != "header":
        return

    align_by_path = (
        "{}.{}.write.align_by".format(str(outputs_path), int(idx))
        if out_cfg.write is not None and out_cfg.write.align_by is not None
        else "resources.books.{}.write_defaults.align_by".format(str(book_id))
    )
    msg = (
        "books.kind=xlsx_memory does not support write.align_by=header; "
        "internal rows only use canonical field keys. Migrate to write.align_by=field_id "
        "and keep write.header_fields_output_by for export display (book_id={!r})"
    ).format(str(book_id))
    raise ScalimWorkflowConfigError(msg, path=str(align_by_path))


def _apply_book_patch(  # noqa: C901, PLR0912, PLR0915
    base: Optional[BookConfig],
    patch: Mapping[str, object],
    *,
    path: str,
) -> BookConfig:
    msg: str

    kind = str(base.kind or "").strip() if base is not None else ""
    book_path: Any = base.path if base is not None else None
    budget = base.budget if base is not None else None
    export_xlsx = base.export_xlsx if base is not None else None
    allow_formulas = bool(base.allow_formulas) if base is not None else False
    write_lock = bool(base.write_lock) if base is not None else False
    write_defaults = base.write_defaults if base is not None else None

    allowed_keys = {"kind", "path", "budget", "export_xlsx", "allow_formulas", "write_lock", "write_defaults"}
    unknown = sorted({str(k) for k in patch} - allowed_keys)
    if unknown:
        msg = "{} contains unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    if "kind" in patch:
        raw = patch.get("kind")
        kind = str(raw or "").strip() if isinstance(raw, str) else ""
        if not kind:
            msg = "{}.kind must be a non-empty string".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))

    if "path" in patch:
        book_path = patch.get("path")

    if "allow_formulas" in patch:
        raw = patch.get("allow_formulas")
        if not isinstance(raw, bool):
            msg = "{}.allow_formulas must be a bool".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))
        allow_formulas = bool(raw)

    if "write_lock" in patch:
        raw = patch.get("write_lock")
        if not isinstance(raw, bool):
            msg = "{}.write_lock must be a bool".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.write_lock".format(path))
        write_lock = bool(raw)

    if "budget" in patch:
        raw = patch.get("budget")
        if raw is None:
            budget = None
        elif not isinstance(raw, dict):
            msg = "{}.budget must be a mapping".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
        else:
            raw_dict = cast("Dict[str, Any]", raw)  # pragma: allow-cast runtime overrides dict narrowing
            max_sheets_raw = raw_dict.get("max_sheets")
            max_total_cells_raw = raw_dict.get("max_total_cells")
            if budget is None:
                if max_sheets_raw is None or max_total_cells_raw is None:
                    msg = "{}.budget requires max_sheets and max_total_cells when creating a new xlsx_memory book".format(path)
                    raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
                budget = BookBudgetConfig(max_sheets=int(max_sheets_raw), max_total_cells=int(max_total_cells_raw))
            else:
                max_sheets = int(budget.max_sheets)
                max_total_cells = int(budget.max_total_cells)
                if max_sheets_raw is not None:
                    max_sheets = int(max_sheets_raw)
                if max_total_cells_raw is not None:
                    max_total_cells = int(max_total_cells_raw)
                budget = BookBudgetConfig(max_sheets=int(max_sheets), max_total_cells=int(max_total_cells))

    if "export_xlsx" in patch:
        raw = patch.get("export_xlsx")
        if raw is None:
            export_xlsx = None
        elif not isinstance(raw, dict):
            msg = "{}.export_xlsx must be a mapping".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx".format(path))
        else:
            raw_dict = cast("Dict[str, Any]", raw)  # pragma: allow-cast runtime overrides dict narrowing
            path_raw = raw_dict.get("path")
            write_lock_raw = raw_dict.get("write_lock")
            allow_formulas_raw = raw_dict.get("allow_formulas")
            if export_xlsx is None:
                if path_raw is None:
                    msg = "{}.export_xlsx.path is required when creating export_xlsx".format(path)
                    raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx.path".format(path))
                export_xlsx = BookExportXlsxConfig(
                    path=path_raw,
                    write_lock=bool(write_lock_raw) if isinstance(write_lock_raw, bool) else False,
                    allow_formulas=bool(allow_formulas_raw) if isinstance(allow_formulas_raw, bool) else False,
                )
            else:
                next_path = export_xlsx.path if path_raw is None else path_raw
                next_write_lock = export_xlsx.write_lock if write_lock_raw is None else bool(write_lock_raw)
                next_allow_formulas = export_xlsx.allow_formulas if allow_formulas_raw is None else bool(allow_formulas_raw)
                export_xlsx = BookExportXlsxConfig(
                    path=next_path,
                    write_lock=bool(next_write_lock),
                    allow_formulas=bool(next_allow_formulas),
                )

    if "write_defaults" in patch:
        raw = patch.get("write_defaults")
        if raw is None:
            write_defaults = None
        elif not isinstance(raw, dict):
            msg = "{}.write_defaults must be a mapping".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.write_defaults".format(path))
        else:
            raw_dict = cast("Dict[str, Any]", raw)  # pragma: allow-cast runtime overrides dict narrowing
            base_defaults = _effective_write_defaults(
                BookConfig(
                    kind=str(kind),
                    path=book_path,
                    budget=budget,
                    export_xlsx=export_xlsx,
                    allow_formulas=bool(allow_formulas),
                    write_lock=bool(write_lock),
                    write_defaults=write_defaults,
                )
            )
            override_cfg = OutputWriteConfig(
                mode=raw_dict.get("mode"),
                align_by=raw_dict.get("align_by"),
                header_policy=raw_dict.get("header_policy"),
                header_fields_output_by=raw_dict.get("header_fields_output_by"),
                on_mismatch=raw_dict.get("on_mismatch"),
                on_conflict=raw_dict.get("on_conflict"),
            )
            write_defaults = _overlay_write_defaults(base_defaults, override_cfg)

    # 校验 `kind` 分支约束(与 `YAML` 解析器语义保持一致).
    if kind == "xlsx_file":
        if not book_path or (isinstance(book_path, str) and not str(book_path).strip()):
            msg = "{}.path is required for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
        if budget is not None:
            msg = "{}.budget is not allowed for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
        if export_xlsx is not None:
            msg = "{}.export_xlsx is not allowed for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx".format(path))
    elif kind == "xlsx_memory":
        if budget is None:
            msg = "{}.budget is required for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
        if book_path is not None:
            msg = "{}.path is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
        if allow_formulas:
            msg = "{}.allow_formulas is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))
        if write_lock:
            msg = "{}.write_lock is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.write_lock".format(path))
    else:
        msg = "{}.kind={!r} is invalid; expected one of: xlsx_file, xlsx_memory".format(path, kind)
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))

    return BookConfig(
        kind=str(kind),
        path=book_path,
        budget=budget,
        export_xlsx=export_xlsx,
        allow_formulas=bool(allow_formulas),
        write_lock=bool(write_lock),
        write_defaults=write_defaults,
    )


def _apply_file_patch(base: Optional[FileConfig], patch: Mapping[str, object], *, path: str) -> FileConfig:
    allowed_keys = {"kind", "path", "encoding"}
    unknown = sorted({str(k) for k in patch} - allowed_keys)
    if unknown:
        msg = "{} contains unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    kind = str(base.kind or "").strip() if base is not None else ""
    file_path: Any = base.path if base is not None else None
    encoding = str(base.encoding or DEFAULT_OUTPUT_ENCODING) if base is not None else DEFAULT_OUTPUT_ENCODING

    if "kind" in patch:
        raw_kind = patch.get("kind")
        kind = str(raw_kind or "").strip() if isinstance(raw_kind, str) else ""
        if not kind:
            msg = "{}.kind must be a non-empty string".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))
    if kind not in FILE_KINDS:
        msg = "{}.kind={!r} is invalid; expected one of: {}".format(path, kind, ", ".join(FILE_KINDS))
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))

    if "path" in patch:
        file_path = patch.get("path")
    if file_path is None:
        msg = "{}.path is required for kind=csv_file".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))

    if "encoding" in patch:
        raw_encoding = patch.get("encoding")
        if raw_encoding is None:
            encoding = DEFAULT_OUTPUT_ENCODING
        elif not isinstance(raw_encoding, str):
            msg = "{}.encoding must be a string".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.encoding".format(path))
        else:
            encoding = str(raw_encoding).strip() or DEFAULT_OUTPUT_ENCODING

    return FileConfig(kind=str(kind), path=file_path, encoding=str(encoding))


def _book_export_path_and_options(
    book: BookConfig,
    *,
    book_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, object]],
    path_prefix: str,
) -> Tuple[str, Dict[str, object]]:
    kind = str(book.kind or "").strip()
    if kind == "xlsx_file":
        export_path = resolve_yaml_relative_output_path(
            book.path,
            base_dir=str(base_dir),
            init_vars=init_vars,
            path="{}.path".format(path_prefix),
        )
        options: Dict[str, object] = {
            "kind": "xlsx_file",
            "allow_formulas": bool(book.allow_formulas),
            "write_lock": bool(book.write_lock),
        }
        return export_path, options

    if kind == "xlsx_memory":
        budget = book.budget
        if budget is None:
            msg = "books.kind=xlsx_memory requires budget (book_id={!r})".format(str(book_id))
            path_ref = "{}.budget".format(path_prefix)
            err = "{} (path={})".format(msg, path_ref)
            raise ValueError(err)

        export_cfg = book.export_xlsx
        export_path = ""
        export_options = None
        if export_cfg is not None:
            export_path = resolve_yaml_relative_output_path(
                export_cfg.path,
                base_dir=str(base_dir),
                init_vars=init_vars,
                path="{}.export_xlsx.path".format(path_prefix),
            )
            export_options = {
                "write_lock": bool(export_cfg.write_lock),
                "allow_formulas": bool(export_cfg.allow_formulas),
            }

        options = {
            "kind": "xlsx_memory",
            "budget": {"max_sheets": int(budget.max_sheets), "max_total_cells": int(budget.max_total_cells)},
        }
        if export_options is not None:
            options["export_xlsx"] = export_options
        return export_path, options

    msg = "Unknown book kind {!r} for book_id={!r}".format(kind, str(book_id))
    path_ref = "{}.kind".format(path_prefix)
    err = "{} (path={})".format(msg, path_ref)
    raise ValueError(err)


def _file_export_path_and_options(
    file_cfg: FileConfig,
    *,
    file_id: str,
    base_dir: str,
    init_vars: Optional[Dict[str, object]],
    path_prefix: str,
) -> Tuple[str, Dict[str, object]]:
    kind = str(file_cfg.kind or "").strip()
    if kind != "csv_file":
        msg = "Unknown file kind {!r} for file_id={!r}".format(kind, str(file_id))
        path_ref = "{}.kind".format(path_prefix)
        err = "{} (path={})".format(msg, path_ref)
        raise ValueError(err)

    export_path = resolve_yaml_relative_output_path(
        file_cfg.path,
        base_dir=str(base_dir),
        init_vars=init_vars,
        path="{}.path".format(path_prefix),
    )
    return export_path, {"kind": "csv_file", "encoding": str(file_cfg.encoding or DEFAULT_OUTPUT_ENCODING)}


def _book_override_to_patch(override: BookResourceOverride) -> Dict[str, object]:  # noqa: C901, PLR0912
    patch: Dict[str, object] = {}
    if override.kind is not None:
        patch["kind"] = override.kind
    if override.path is not None:
        patch["path"] = override.path
    if override.allow_formulas is not None:
        patch["allow_formulas"] = override.allow_formulas
    if override.write_lock is not None:
        patch["write_lock"] = override.write_lock
    if override.budget is not None:
        budget_patch: Dict[str, object] = {}
        if override.budget.max_sheets is not None:
            budget_patch["max_sheets"] = override.budget.max_sheets
        if override.budget.max_total_cells is not None:
            budget_patch["max_total_cells"] = override.budget.max_total_cells
        patch["budget"] = budget_patch
    if override.export_xlsx is not None:
        export_patch: Dict[str, object] = {}
        if override.export_xlsx.path is not None:
            export_patch["path"] = override.export_xlsx.path
        if override.export_xlsx.write_lock is not None:
            export_patch["write_lock"] = override.export_xlsx.write_lock
        if override.export_xlsx.allow_formulas is not None:
            export_patch["allow_formulas"] = override.export_xlsx.allow_formulas
        patch["export_xlsx"] = export_patch
    if override.write_defaults is not None:
        defaults_patch: Dict[str, object] = {}
        if override.write_defaults.mode is not None:
            defaults_patch["mode"] = override.write_defaults.mode
        if override.write_defaults.align_by is not None:
            defaults_patch["align_by"] = override.write_defaults.align_by
        if override.write_defaults.header_policy is not None:
            defaults_patch["header_policy"] = override.write_defaults.header_policy
        if override.write_defaults.on_mismatch is not None:
            defaults_patch["on_mismatch"] = override.write_defaults.on_mismatch
        if override.write_defaults.on_conflict is not None:
            defaults_patch["on_conflict"] = override.write_defaults.on_conflict
        patch["write_defaults"] = defaults_patch
    return patch


def _file_override_to_patch(override: FileResourceOverride) -> Dict[str, object]:
    patch: Dict[str, object] = {}
    if override.kind is not None:
        patch["kind"] = override.kind
    if override.path is not None:
        patch["path"] = override.path
    if override.encoding is not None:
        patch["encoding"] = override.encoding
    return patch


def _compile_workflow_resources(  # noqa: C901, PLR0912, PLR0915
    wf_obj: WorkflowConfig,
    *,
    workflow_base_dir: Path,
    demand_cfg_by_run_id: Mapping[str, DemandConfig],
    demand_yaml_paths_by_run_id: Mapping[str, str],
    init_vars: Optional[Dict[str, object]],
    overrides_resources: Optional[ResourcesOverride],
) -> Tuple[List[WorkflowResourceIr], Dict[str, BookConfig], Dict[str, FileConfig]]:
    """编译工作流的有效 `books` 资源并返回:

    - 资源列表(`IR`)
    - 有效 `BookConfig` 映射(`book_id` -> 配置)
    - 有效 `FileConfig` 映射(`file_id` -> 配置)
    """

    msg: str

    workflow_books: Dict[str, BookConfig] = dict(wf_obj.resources.books or {})
    workflow_files: Dict[str, FileConfig] = dict(wf_obj.resources.files or {})
    demand_books: Dict[str, BookConfig] = {}
    demand_files: Dict[str, FileConfig] = {}
    demand_base_dir_by_book_id: Dict[str, str] = {}
    demand_base_dir_by_file_id: Dict[str, str] = {}

    # 1) 收集需求侧声明的 `books`(用于与 `standalone` 行为对齐).
    for run in wf_obj.runs:
        run_id = str(run.id)
        cfg = demand_cfg_by_run_id.get(run_id)
        if cfg is None:
            continue
        res = cfg.resources
        books = res.books if res is not None else {}
        files = res.files if res is not None else {}
        if not books:
            pass
        base_dir = str(_demand_base_dir(demand_yaml_paths_by_run_id.get(run_id, "")))

        for book_id, book in books.items():
            bid = str(book_id)
            if bid in workflow_books:
                # 工作流声明同名 `book_id` 时,要求与需求侧的 `kind` 兼容.
                wf_kind = str(workflow_books[bid].kind or "").strip()
                demand_kind = str(book.kind or "").strip()
                if wf_kind and demand_kind and wf_kind != demand_kind:
                    msg = "Book kind mismatch between workflow and demand (book_id={!r}, workflow_kind={!r}, demand_kind={!r})".format(
                        bid, wf_kind, demand_kind
                    )
                    raise ScalimWorkflowConfigError(msg, path="workflow.resources.books.{}".format(bid))
                continue

            existing = demand_books.get(bid)
            if existing is None:
                demand_books[bid] = book
                demand_base_dir_by_book_id[bid] = base_dir
                continue

            # 多个需求声明同一 `book_id` 时,在路径解析后要求配置等价.
            if existing != book:
                msg = "Conflicting demand book definitions for book_id={!r}; declare workflow.resources.books.{} to override".format(
                    bid, bid
                )
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")

            # 配置相同但相对路径可能在不同 `YAML` 目录下解析出不同结果:
            # - 使用第一个 `base_dir` 作为基准
            # - 尽量确保其它需求解析得到的绝对路径一致
            # - 若需要跨目录共享,应在工作流级声明该 `book`
            first_dir = demand_base_dir_by_book_id.get(bid, base_dir)
            first_abs_path = _try_resolve_book_export_abs_path(
                existing,
                book_id=bid,
                base_dir=str(first_dir),
                init_vars=init_vars,
                path_prefix="resources.books.{}".format(bid),
            )
            current_abs_path = _try_resolve_book_export_abs_path(
                book,
                book_id=bid,
                base_dir=str(base_dir),
                init_vars=init_vars,
                path_prefix="resources.books.{}".format(bid),
            )
            if first_abs_path and current_abs_path and str(first_abs_path) != str(current_abs_path):
                msg = (
                    "Conflicting demand book paths for shared book_id={!r} across different YAML dirs; "
                    "declare workflow.resources.books.{} to unify"
                ).format(bid, bid)
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")

        for file_id, file_cfg in files.items():
            fid = str(file_id)
            if fid in workflow_files:
                wf_kind = str(workflow_files[fid].kind or "").strip()
                demand_kind = str(file_cfg.kind or "").strip()
                if wf_kind and demand_kind and wf_kind != demand_kind:
                    msg = "File kind mismatch between workflow and demand (file_id={!r}, workflow_kind={!r}, demand_kind={!r})".format(
                        fid, wf_kind, demand_kind
                    )
                    raise ScalimWorkflowConfigError(msg, path="workflow.resources.files.{}".format(fid))
                continue
            existing_file = demand_files.get(fid)
            if existing_file is None:
                demand_files[fid] = file_cfg
                demand_base_dir_by_file_id[fid] = base_dir
                continue
            if existing_file != file_cfg:
                msg = "Conflicting demand file definitions for file_id={!r}; declare workflow.resources.files.{} to override".format(
                    fid, fid
                )
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.files")

    # 2) 计算有效配置,优先级: 需求 < 工作流 < `overrides`.
    effective_books: Dict[str, BookConfig] = {}
    effective_files: Dict[str, FileConfig] = {}
    base_dir_by_book_id: Dict[str, str] = {}
    base_dir_by_file_id: Dict[str, str] = {}
    path_prefix_by_book_id: Dict[str, str] = {}
    path_prefix_by_file_id: Dict[str, str] = {}

    all_book_ids: Set[str] = set()
    all_book_ids.update(demand_books)
    all_book_ids.update(workflow_books)
    all_file_ids: Set[str] = set()
    all_file_ids.update(demand_files)
    all_file_ids.update(workflow_files)

    overrides_books_raw = None if overrides_resources is None else overrides_resources.books
    overrides_files_raw = None if overrides_resources is None else overrides_resources.files
    if overrides_books_raw:
        all_book_ids.update(str(k) for k in overrides_books_raw)
    if overrides_files_raw:
        all_file_ids.update(str(k) for k in overrides_files_raw)

    for book_id in sorted(all_book_ids):
        bid = str(book_id)
        book = None
        base_dir = None
        path_prefix = ""

        if bid in workflow_books:
            book = workflow_books[bid]
            base_dir = str(workflow_base_dir)
            path_prefix = "workflow.resources.books.{}".format(bid)
        elif bid in demand_books:
            book = demand_books[bid]
            base_dir = str(demand_base_dir_by_book_id.get(bid, workflow_base_dir))
            path_prefix = "resources.books.{}".format(bid)

        # 应用仅 `IO` 的 `overrides.resources.books.<id>` 补丁覆盖(按 `deep-merge` 语义).
        if overrides_books_raw is not None and bid in overrides_books_raw:
            book_override = overrides_books_raw[bid]
            if not isinstance(book_override, BookResourceOverride):
                msg = "overrides.resources.books.{} must be a BookResourceOverride".format(bid)
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.books.{}".format(bid))
            patch = _book_override_to_patch(book_override)
            if book is None:
                book = BookConfig(kind="")
                if base_dir is None:
                    base_dir = str(workflow_base_dir)
            book = _apply_book_patch(book, patch, path="overrides.resources.books.{}".format(bid))
            path_prefix = "overrides.resources.books.{}".format(bid)

        if book is None or base_dir is None:
            continue
        effective_books[bid] = book
        base_dir_by_book_id[bid] = base_dir
        path_prefix_by_book_id[bid] = path_prefix

    for file_id in sorted(all_file_ids):
        fid = str(file_id)
        file_cfg = None
        base_dir = None
        path_prefix = ""

        if fid in workflow_files:
            file_cfg = workflow_files[fid]
            base_dir = str(workflow_base_dir)
            path_prefix = "workflow.resources.files.{}".format(fid)
        elif fid in demand_files:
            file_cfg = demand_files[fid]
            base_dir = str(demand_base_dir_by_file_id.get(fid, workflow_base_dir))
            path_prefix = "resources.files.{}".format(fid)

        if overrides_files_raw is not None and fid in overrides_files_raw:
            file_override = overrides_files_raw[fid]
            if not isinstance(file_override, FileResourceOverride):
                msg = "overrides.resources.files.{} must be a FileResourceOverride".format(fid)
                raise ScalimWorkflowConfigError(msg, path="overrides.resources.files.{}".format(fid))
            patch = _file_override_to_patch(file_override)
            if file_cfg is None:
                file_cfg = FileConfig(kind="")
                if base_dir is None:
                    base_dir = str(workflow_base_dir)
            file_cfg = _apply_file_patch(file_cfg, patch, path="overrides.resources.files.{}".format(fid))
            path_prefix = "overrides.resources.files.{}".format(fid)

        if file_cfg is None or base_dir is None:
            continue  # pragma: no cover  # pragma: allow-no-cover unreachable: all_file_ids derived from workflow/demand/overrides
        effective_files[fid] = file_cfg
        base_dir_by_file_id[fid] = base_dir
        path_prefix_by_file_id[fid] = path_prefix

    resources: List[WorkflowResourceIr] = []
    for bid, book in sorted(effective_books.items(), key=lambda kv: str(kv[0])):
        base_dir = base_dir_by_book_id.get(str(bid), str(workflow_base_dir))
        prefix = path_prefix_by_book_id.get(str(bid)) or (
            "workflow.resources.books.{}".format(str(bid)) if str(bid) in workflow_books else "resources.books.{}".format(str(bid))
        )
        try:
            export_path, options = _book_export_path_and_options(
                book,
                book_id=str(bid),
                base_dir=str(base_dir),
                init_vars=init_vars,
                path_prefix=prefix,
            )
        except (TypeError, ValueError) as exc:
            raise ScalimWorkflowConfigError(str(exc), path=prefix) from None

        resources.append(
            WorkflowResourceIr(
                resource_id=str(bid),
                resource_type="book",
                path=str(export_path or ""),
                options=options,
            )
        )

    for fid, file_cfg in sorted(effective_files.items(), key=lambda kv: str(kv[0])):
        base_dir = base_dir_by_file_id.get(str(fid), str(workflow_base_dir))
        prefix = path_prefix_by_file_id.get(str(fid)) or (
            "workflow.resources.files.{}".format(str(fid)) if str(fid) in workflow_files else "resources.files.{}".format(str(fid))
        )
        try:
            export_path, options = _file_export_path_and_options(
                file_cfg,
                file_id=str(fid),
                base_dir=str(base_dir),
                init_vars=init_vars,
                path_prefix=prefix,
            )
        except (TypeError, ValueError) as exc:
            raise ScalimWorkflowConfigError(str(exc), path=prefix) from None

        resources.append(
            WorkflowResourceIr(
                resource_id=str(fid),
                resource_type="csv",
                path=str(export_path or ""),
                options=options,
            )
        )

    # 预检 `xlsx` 导出路径冲突(跨 `books`,且顺序确定).
    by_abs_path: Dict[str, List[str]] = {}
    for res in resources:
        p = str(res.path or "").strip()
        if not p:
            continue
        abs_path = _as_abs_path(p)
        by_abs_path.setdefault(abs_path, []).append(str(res.resource_id))
    collisions = sorted((path, sorted(ids)) for path, ids in by_abs_path.items() if len(ids) > 1)
    if collisions:
        path, ids = collisions[0]
        msg = "Excel output path collision across books: path={!r}, book_ids={}".format(str(path), ",".join(ids))
        raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")

    return resources, effective_books, effective_files


def _build_demand_nodes_and_graph(
    wf_obj: WorkflowConfig,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Tuple[
    List[WorkflowAnyNodeIr],
    List[WorkflowEdgeIr],
    Dict[str, Tuple[str, ...]],
    Dict[str, str],
    Dict[str, List[str]],
    Dict[str, int],
]:
    nodes: List[WorkflowAnyNodeIr] = []
    edges: List[WorkflowEdgeIr] = []
    slots_by_node_id: Dict[str, Tuple[str, ...]] = {}
    demand_yaml_paths_by_run_id: Dict[str, str] = {}
    direct_dependents_by_run_id: Dict[str, List[str]] = {}
    demand_node_pos_by_run_id: Dict[str, int] = {}

    for idx, run in enumerate(wf_obj.runs):
        demand_path = resolve_workflow_demand_path(
            run.demand,
            workflow_yaml_path=workflow_yaml_path,
            path_aliases=path_aliases,
            run_id=run.id,
            allowed_yaml_roots=allowed_yaml_roots,
        )
        node_id = str(run.id)
        run_deps = tuple(str(d) for d in (run.depends_on or ()))
        main_rows_from_run_id = run.main_rows_from_run_id
        if main_rows_from_run_id is not None:
            main_rows_from_run_id = str(main_rows_from_run_id or "").strip() or None
        init_vars = run.init_vars
        if init_vars is not None:
            init_vars = dict(init_vars)
        demand_yaml_paths_by_run_id[node_id] = str(demand_path)
        nodes.append(
            WorkflowNodeIr(
                node_id=node_id,
                node_type=WorkflowNodeType.DEMAND,
                decl_order=int(idx),
                deps=run_deps,
                demand_path=str(demand_path),
                init_vars=init_vars,
                main_rows_from_run_id=main_rows_from_run_id,
            )
        )
        demand_node_pos_by_run_id[node_id] = int(len(nodes) - 1)
        for dep_id in run_deps:
            edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=node_id))
            direct_dependents_by_run_id.setdefault(str(dep_id), []).append(node_id)
        slots_by_node_id[node_id] = ("output_path", "outputs")

    return (
        nodes,
        edges,
        slots_by_node_id,
        demand_yaml_paths_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
    )


def _load_demands(
    demand_yaml_paths_by_run_id: Mapping[str, str],
    *,
    template_vars: Optional[Mapping[str, object]],
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Dict[str, DemandConfig]:
    loader = YamlDemandLoader()
    demand_cfg_by_run_id: Dict[str, DemandConfig] = {}
    for node_id, yaml_path in demand_yaml_paths_by_run_id.items():
        try:
            cfg = loader.load(str(yaml_path), template_vars=template_vars, allowed_yaml_roots=allowed_yaml_roots)
        except Exception as exc:
            msg = "Failed to load demand YAML for workflow compile: run_id={!r}, demand_path={!r}: {}".format(
                str(node_id),
                str(yaml_path),
                exc,
            )
            raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].demand") from exc
        demand_cfg_by_run_id[str(node_id)] = cfg
    return demand_cfg_by_run_id


def _parse_overrides_outputs_defaults_book_id(defaults: Optional[OutputsDefaultsOverride]) -> Optional[str]:
    if defaults is None:
        return None
    book_id = str(defaults.to.book or "").strip()
    if not book_id:
        msg = "overrides.outputs_defaults.to.book is required"
        raise ScalimWorkflowConfigError(msg, path="overrides.outputs_defaults.to.book")
    return book_id


def _apply_default_book_binding_to_outputs(
    outputs: Tuple[OutputTargetConfig, ...],
    *,
    default_book_id: str,
) -> Tuple[OutputTargetConfig, ...]:
    if not outputs or not default_book_id:
        return outputs

    updated: List[OutputTargetConfig] = []
    for out_cfg in outputs:
        to_cfg = out_cfg.to
        if to_cfg is None:
            updated.append(replace(out_cfg, to=OutputToConfig(book=str(default_book_id))))
            continue

        file_id = str(to_cfg.file or "").strip() if to_cfg.file is not None else ""
        book_id = str(to_cfg.book or "").strip() if to_cfg.book is not None else ""
        if file_id or book_id:
            updated.append(out_cfg)
            continue

        updated.append(replace(out_cfg, to=replace(to_cfg, book=str(default_book_id))))

    return tuple(updated)


def _effective_outputs_for_workflow_compile(  # noqa: C901
    config: DemandConfig,
    *,
    overrides_outputs: Optional[Sequence[OutputOverride]],
    default_book_id: Optional[str],
) -> Tuple[OutputTargetConfig, ...]:
    if overrides_outputs is None:
        yaml_outputs = tuple(config.outputs or ())
        if default_book_id is not None:
            yaml_outputs = _apply_default_book_binding_to_outputs(yaml_outputs, default_book_id=str(default_book_id))
        return yaml_outputs

    # 最小解析器: 仅抽取 `name`/`to`/`write`;完整校验在需求编译阶段完成.
    outputs: List[OutputTargetConfig] = []
    for idx, raw in enumerate(overrides_outputs):
        if not isinstance(raw, OutputOverride):
            msg = "overrides.outputs.{} must be an OutputOverride".format(int(idx))
            raise ScalimWorkflowConfigError(msg, path="overrides.outputs")

        name = str(raw.name or "").strip()
        if not name:
            msg = "overrides.outputs.{}.name is required".format(int(idx))
            raise ScalimWorkflowConfigError(msg, path="overrides.outputs")

        to_override = raw.to
        if not isinstance(to_override, OutputToOverride):
            msg = "overrides.outputs.{}.to must be an OutputToOverride".format(int(idx))
            raise ScalimWorkflowConfigError(msg, path="overrides.outputs.{}.to".format(int(idx)))
        file_id = str(to_override.file or "").strip() if to_override.file is not None else ""
        book_id = str(to_override.book or "").strip() if to_override.book is not None else ""
        sheet = str(to_override.sheet or "").strip() if to_override.sheet is not None else ""

        if file_id and (book_id or sheet):
            msg = "overrides.outputs.{}.to declares to.file and to.book/to.sheet; declare only one destination".format(int(idx))
            raise ScalimWorkflowConfigError(msg, path="overrides.outputs.{}.to".format(int(idx)))

        if not file_id:
            book_id = book_id or str(default_book_id or "").strip()
            if not book_id:
                msg = (
                    "Missing outputs to.book binding for output {!r}; set overrides.outputs.{}.to.book explicitly "
                    "or provide overrides.outputs_defaults.to.book"
                ).format(str(name), int(idx))
                raise ScalimWorkflowConfigError(msg, path="overrides.outputs.{}.to.book".format(int(idx)))

        to_cfg = OutputToConfig(
            file=str(file_id).strip() or None,
            book=str(book_id).strip() or None,
            sheet=str(sheet).strip() or None,
        )

        write_obj = raw.write
        write_cfg = None
        if write_obj is not None:
            if not isinstance(write_obj, OutputWriteOverride):
                msg = "overrides.outputs.{}.write must be an OutputWriteOverride".format(int(idx))
                raise ScalimWorkflowConfigError(msg, path="overrides.outputs.{}.write".format(int(idx)))

            write_raw = cast("Any", write_obj)  # pragma: allow-cast typed override field access boundary
            write_cfg = OutputWriteConfig(
                include_header=write_raw.include_header,
                mode=write_raw.mode,
                align_by=write_raw.align_by,
                header_policy=write_raw.header_policy,
                header_fields_output_by=write_raw.header_fields_output_by,
                on_mismatch=write_raw.on_mismatch,
                on_conflict=write_raw.on_conflict,
            )

        outputs.append(
            OutputTargetConfig(
                name=str(name),
                to=to_cfg,
                write=write_cfg,
                fields=None,
            )
        )
    return tuple(outputs)


def _append_write_nodes_from_runs(  # noqa: C901, PLR0912, PLR0915
    wf_obj: WorkflowConfig,
    *,
    demand_cfg_by_run_id: Mapping[str, DemandConfig],
    nodes: List[WorkflowAnyNodeIr],
    edges: List[WorkflowEdgeIr],
    effective_books: Mapping[str, BookConfig],
    effective_files: Mapping[str, FileConfig],
    overrides_outputs: Optional[Sequence[OutputOverride]],
    default_book_id: Optional[str],
) -> Dict[str, List[str]]:
    last_write_node_id_by_book_id: Dict[str, str] = {}
    xlsx_memory_write_node_ids_by_run_id: Dict[str, List[str]] = {}

    for run in wf_obj.runs:
        cfg = demand_cfg_by_run_id.get(str(run.id))
        if cfg is None:
            continue

        outputs = _effective_outputs_for_workflow_compile(cfg, overrides_outputs=overrides_outputs, default_book_id=default_book_id)
        if not outputs:
            continue

        outputs_path = "outputs" if overrides_outputs is None else "overrides.outputs"

        next_write_idx = 0
        for out_idx, out_cfg in enumerate(outputs):
            file_id, file_ref_path = _effective_file_binding_for_output(
                out_cfg,
                idx=int(out_idx),
                outputs_path=outputs_path,
            )
            if file_id is not None:
                if effective_files.get(str(file_id)) is None:
                    msg = (
                        "Missing file resource id {!r} referenced by {}. "
                        "Hint: declare resources.files.{} in the demand YAML, declare workflow.resources.files.{} in the workflow YAML, "
                        "or provide overrides.resources.files.{} in Python."
                    ).format(str(file_id), str(file_ref_path), str(file_id), str(file_id), str(file_id))
                    raise ScalimWorkflowConfigError(msg, path=str(file_ref_path))
                continue

            book_id, book_ref_path = _effective_book_binding_for_output(
                out_cfg,
                idx=int(out_idx),
                outputs_path=outputs_path,
            )
            if book_id is None:
                msg = (
                    "Missing outputs to.book binding for output {!r}; set {}.{}.to.book explicitly. "
                    "Reuse the binding with YAML anchors (`_templates`) or `$import` if needed."
                ).format(str(out_cfg.name), str(outputs_path), int(out_idx))
                raise ScalimWorkflowConfigError(msg, path=str(book_ref_path))

            book = effective_books.get(str(book_id))
            if book is None:
                msg = (
                    "Missing book resource id {!r} referenced by {}. "
                    "Hint: declare resources.books.{} in the demand YAML, declare workflow.resources.books.{} in the workflow YAML, "
                    "or provide overrides.resources.books.{} in Python."
                ).format(str(book_id), str(book_ref_path), str(book_id), str(book_id), str(book_id))
                raise ScalimWorkflowConfigError(msg, path=str(book_ref_path))
            _validate_xlsx_memory_align_by(
                book=book,
                book_id=str(book_id),
                out_cfg=out_cfg,
                idx=int(out_idx),
                outputs_path=outputs_path,
            )

            sheet_name, sheet_ref_path = _effective_sheet_name_for_output(out_cfg, idx=int(out_idx), outputs_path=outputs_path)
            try:
                _validate_excel_sheet_name(sheet_name, path=str(sheet_ref_path))
            except ValueError as exc:
                raise ScalimWorkflowConfigError(str(exc), path=str(sheet_ref_path)) from None

            base_defaults = _effective_write_defaults(book)
            effective_defaults = _overlay_write_defaults(base_defaults, out_cfg.write)
            mode = str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE)

            node_id = "{}write.{}.{}".format(_INTERNAL_NODE_ID_PREFIX, str(run.id), int(next_write_idx))
            next_write_idx += 1
            decl_order = len(nodes)
            write_deps: List[str] = [str(run.id)]

            prev_write_id = last_write_node_id_by_book_id.get(str(book_id))
            if prev_write_id is not None:
                write_deps.append(str(prev_write_id))
            last_write_node_id_by_book_id[str(book_id)] = str(node_id)

            node: WorkflowAnyNodeIr
            if mode == "sheet":
                node = WriteSheetNodeIr(
                    node_id=str(node_id),
                    node_type=WorkflowNodeType.WRITE_SHEET,
                    decl_order=int(decl_order),
                    deps=tuple(write_deps),
                    resource_type="book",
                    resource_id=str(book_id),
                    sheet=str(sheet_name),
                    input_node_id=str(run.id),
                    input_output_id=str(out_cfg.name),
                    on_conflict=str(effective_defaults.on_conflict or DEFAULT_BOOK_WRITE_ON_CONFLICT),
                )
            elif mode == "append":
                node = AppendSheetNodeIr(
                    node_id=str(node_id),
                    node_type=WorkflowNodeType.APPEND_SHEET,
                    decl_order=int(decl_order),
                    deps=tuple(write_deps),
                    resource_type="book",
                    resource_id=str(book_id),
                    sheet=str(sheet_name),
                    input_node_id=str(run.id),
                    input_output_id=str(out_cfg.name),
                    align_by=str(effective_defaults.align_by or DEFAULT_BOOK_WRITE_ALIGN_BY),
                    header_policy=str(effective_defaults.header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY),
                    on_mismatch=str(effective_defaults.on_mismatch or DEFAULT_BOOK_WRITE_ON_MISMATCH),
                )
            else:
                msg = "Unsupported books.write_defaults.mode={!r} (book_id={!r})".format(mode, str(book_id))
                raise ScalimWorkflowConfigError(msg, path="workflow.resources.books.{}.write_defaults.mode".format(str(book_id)))

            nodes.append(node)
            for dep_id in write_deps:
                edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=str(node_id)))

            kind = str(book.kind or "").strip()
            if kind == "xlsx_memory":
                xlsx_memory_write_node_ids_by_run_id.setdefault(str(run.id), []).append(str(node_id))

        # `meta`/`audit` 额外工作表: 在工作流模式下通过推导的写入节点写出.
        extras: List[Tuple[str, object, str]] = []
        if cfg.meta is not None:
            extras.append(("meta", cfg.meta, "__meta__"))
        if cfg.audit is not None:
            extras.append(("audit", cfg.audit, "__audit__"))
        if extras:
            default_book_id = None
            default_book_ref = "outputs[*].to.book"
            for scan_idx, scan_out in enumerate(outputs):
                scan_file_id, _scan_file_ref = _effective_file_binding_for_output(
                    scan_out,
                    idx=int(scan_idx),
                    outputs_path=outputs_path,
                )
                if scan_file_id is not None:
                    continue
                candidate, cand_ref = _effective_book_binding_for_output(
                    scan_out,
                    idx=int(scan_idx),
                    outputs_path=outputs_path,
                )
                if candidate:
                    default_book_id, default_book_ref = candidate, cand_ref
                    break

            if default_book_id is None:
                msg = "meta/audit requires at least one Excel output with outputs[*].to.book"
                raise ScalimWorkflowConfigError(msg, path=str(default_book_ref))

            book = effective_books.get(str(default_book_id))
            if book is None:  # pragma: no cover  # pragma: allow-no-cover unreachable: first excel output binding already validated above
                msg = (
                    "Missing book resource id {!r} referenced by {}. "
                    "Hint: declare resources.books.{} in the demand YAML, declare workflow.resources.books.{} in the workflow YAML, "
                    "or provide overrides.resources.books.{} in Python."
                ).format(
                    str(default_book_id),
                    str(default_book_ref),
                    str(default_book_id),
                    str(default_book_id),
                    str(default_book_id),
                )
                raise ScalimWorkflowConfigError(msg, path=str(default_book_ref))

            base_defaults = _effective_write_defaults(book)
            effective_defaults = _overlay_write_defaults(base_defaults, None)
            mode = str(effective_defaults.mode or DEFAULT_BOOK_WRITE_MODE)
            _validate_xlsx_memory_align_by(
                book=book,
                book_id=str(default_book_id),
                out_cfg=OutputTargetConfig(name="__extra__", write=None),
                idx=0,
                outputs_path="resources.books.{}".format(str(default_book_id)),
            )

            for extra_id, extra_cfg_obj, default_sheet in extras:
                extra_cfg = cast("Any", extra_cfg_obj)  # pragma: allow-cast output extra sheet cfg typed narrowing
                sheet_name = str(extra_cfg.sheet or default_sheet)
                sheet_ref_path = "{}.{}".format(extra_id, "sheet")
                try:
                    _validate_excel_sheet_name(sheet_name, path=str(sheet_ref_path))
                except ValueError as exc:
                    raise ScalimWorkflowConfigError(str(exc), path=str(sheet_ref_path)) from None

                node_id = "{}write.{}.{}".format(_INTERNAL_NODE_ID_PREFIX, str(run.id), int(next_write_idx))
                next_write_idx += 1
                decl_order = len(nodes)
                write_deps = [str(run.id)]
                prev_write_id = last_write_node_id_by_book_id.get(str(default_book_id))
                if prev_write_id is not None:
                    write_deps.append(str(prev_write_id))
                last_write_node_id_by_book_id[str(default_book_id)] = str(node_id)

                if mode == "sheet":
                    node = WriteSheetNodeIr(
                        node_id=str(node_id),
                        node_type=WorkflowNodeType.WRITE_SHEET,
                        decl_order=int(decl_order),
                        deps=tuple(write_deps),
                        resource_type="book",
                        resource_id=str(default_book_id),
                        sheet=str(sheet_name),
                        input_node_id=str(run.id),
                        input_output_id=str(extra_id),
                        on_conflict=str(effective_defaults.on_conflict or DEFAULT_BOOK_WRITE_ON_CONFLICT),
                    )
                elif mode == "append":
                    node = AppendSheetNodeIr(
                        node_id=str(node_id),
                        node_type=WorkflowNodeType.APPEND_SHEET,
                        decl_order=int(decl_order),
                        deps=tuple(write_deps),
                        resource_type="book",
                        resource_id=str(default_book_id),
                        sheet=str(sheet_name),
                        input_node_id=str(run.id),
                        input_output_id=str(extra_id),
                        align_by=str(effective_defaults.align_by or DEFAULT_BOOK_WRITE_ALIGN_BY),
                        header_policy=str(effective_defaults.header_policy or DEFAULT_BOOK_WRITE_HEADER_POLICY),
                        on_mismatch=str(effective_defaults.on_mismatch or DEFAULT_BOOK_WRITE_ON_MISMATCH),
                    )
                else:
                    msg = "Unsupported books.write_defaults.mode={!r} (book_id={!r})".format(mode, str(default_book_id))
                    raise ScalimWorkflowConfigError(
                        msg, path="workflow.resources.books.{}.write_defaults.mode".format(str(default_book_id))
                    )

                nodes.append(node)
                for dep_id in write_deps:
                    edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=str(node_id)))

                kind = str(book.kind or "").strip()
                if kind == "xlsx_memory":
                    xlsx_memory_write_node_ids_by_run_id.setdefault(str(run.id), []).append(str(node_id))

    return xlsx_memory_write_node_ids_by_run_id


def _inject_xlsx_memory_write_dependencies(
    xlsx_memory_write_node_ids_by_run_id: Mapping[str, List[str]],
    direct_dependents_by_run_id: Mapping[str, List[str]],
    demand_node_pos_by_run_id: Mapping[str, int],
    nodes: List[WorkflowAnyNodeIr],
    edges: List[WorkflowEdgeIr],
) -> None:
    for producer_node_id, write_node_ids in xlsx_memory_write_node_ids_by_run_id.items():
        for consumer_node_id in direct_dependents_by_run_id.get(str(producer_node_id), []):
            pos = demand_node_pos_by_run_id.get(str(consumer_node_id))
            if pos is None:
                continue
            consumer = nodes[int(pos)]
            if not isinstance(consumer, WorkflowNodeIr):
                continue
            deps: List[str] = list(consumer.deps or ())
            for write_node_id in write_node_ids:
                if str(write_node_id) not in deps:
                    deps.append(str(write_node_id))
                    edges.append(WorkflowEdgeIr(from_node_id=str(write_node_id), to_node_id=str(consumer_node_id)))
            if deps != list(consumer.deps or ()):
                nodes[int(pos)] = replace(consumer, deps=tuple(deps))


def _build_workflow_options_ir(wf_obj: WorkflowConfig) -> WorkflowOptionsIr:
    cache_pool = None
    raw_cache_pool = wf_obj.options.cache_pool
    if raw_cache_pool is not None:
        budget = WorkflowCachePoolBudgetIr(
            max_entries=int(raw_cache_pool.budget.max_entries),
            over_budget_policy=str(raw_cache_pool.budget.over_budget_policy),
        )
        pins = tuple(WorkflowCachePoolPinIr(kind=str(pin.kind), source_id=str(pin.source_id)) for pin in (raw_cache_pool.pin or ()))
        cache_pool = WorkflowCachePoolIr(
            conflict_policy=str(raw_cache_pool.conflict_policy),
            release_policy=str(raw_cache_pool.release_policy),
            budget=budget,
            pin=pins,
        )

    raw_ctx = wf_obj.options.ctx
    ctx = WorkflowCtxOptionsIr(
        max_value_bytes=int(raw_ctx.max_value_bytes),
        max_bytes=int(raw_ctx.max_bytes),
    )

    raw_resources_wait = wf_obj.options.resources_wait
    raw_diagnostics = raw_resources_wait.diagnostics
    resources_wait = WorkflowResourcesWaitOptionsIr(
        max_wait_s=float(raw_resources_wait.max_wait_s),
        diagnostics=WorkflowResourcesWaitDiagnosticsIr(
            enabled=bool(raw_diagnostics.enabled),
            warn_after_s=float(raw_diagnostics.warn_after_s),
            repeat_every_s=float(raw_diagnostics.repeat_every_s) if raw_diagnostics.repeat_every_s is not None else None,
            capture_owner_callsite=bool(raw_diagnostics.capture_owner_callsite),
        ),
    )

    raw_output_staging = wf_obj.options.output_staging
    output_staging = WorkflowOutputStagingOptionsIr(
        dir_name=str(raw_output_staging.dir_name),
        keep_on_success=bool(raw_output_staging.keep_on_success),
        keep_on_failure=bool(raw_output_staging.keep_on_failure),
    )

    return WorkflowOptionsIr(
        max_concurrency=int(wf_obj.options.max_concurrency),
        failure_policy=str(wf_obj.options.failure_policy or "all_fail"),
        cache_pool=cache_pool,
        ctx=ctx,
        resources_wait=resources_wait,
        output_staging=output_staging,
    )


def compile_workflow_ir(
    wf: object,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    template_vars: Optional[Mapping[str, object]] = None,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
    init_vars: Optional[Dict[str, object]] = None,
    overrides: Optional[object] = None,
) -> WorkflowIr:
    """将工作流配置编译为工作流 `IR`.

    说明:
    - `overrides` 为 `RunOverrides` 强类型覆盖项,用于 `resources` 覆盖、`outputs_defaults` 与 `outputs` 替换.
    """
    if overrides is not None and not isinstance(overrides, RunOverrides):
        msg = (
            "overrides must be a RunOverrides (typed dataclasses); legacy YAML-shaped overrides mappings were removed. "
            "Migrate to RunOverrides(outputs=(OutputOverride(...),), "
            "resources=ResourcesOverride(...), outputs_defaults=OutputsDefaultsOverride(...))."
        )
        raise ScalimWorkflowConfigError(msg, path="overrides")
    overrides_typed = overrides
    wf_obj = cast("WorkflowConfig", wf)  # pragma: allow-cast workflow config typed narrowing

    workflow_base_dir = _workflow_base_dir(workflow_yaml_path)

    (
        nodes,
        edges,
        slots_by_node_id,
        demand_yaml_paths_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
    ) = _build_demand_nodes_and_graph(
        wf_obj,
        workflow_yaml_path=workflow_yaml_path,
        path_aliases=path_aliases,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    demand_cfg_by_run_id = _load_demands(
        demand_yaml_paths_by_run_id,
        template_vars=template_vars,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    overrides_resources = None if overrides_typed is None else overrides_typed.resources
    overrides_outputs = None if overrides_typed is None else overrides_typed.outputs
    default_book_id = _parse_overrides_outputs_defaults_book_id(None if overrides_typed is None else overrides_typed.outputs_defaults)

    resources, effective_books, effective_files = _compile_workflow_resources(
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        demand_yaml_paths_by_run_id=demand_yaml_paths_by_run_id,
        init_vars=init_vars,
        overrides_resources=overrides_resources,
    )

    xlsx_memory_write_node_ids_by_run_id = _append_write_nodes_from_runs(
        wf_obj,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        nodes=nodes,
        edges=edges,
        effective_books=effective_books,
        effective_files=effective_files,
        overrides_outputs=overrides_outputs,
        default_book_id=default_book_id,
    )

    _inject_xlsx_memory_write_dependencies(
        xlsx_memory_write_node_ids_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
        nodes,
        edges,
    )

    workflow_options = _build_workflow_options_ir(wf_obj)

    artifacts = WorkflowArtifactsIr(slots_by_node_id=slots_by_node_id)
    resources_sorted = sorted(resources, key=lambda r: (str(r.resource_type), str(r.resource_id)))
    return WorkflowIr(
        nodes=tuple(nodes),
        edges=tuple(edges),
        options=workflow_options,
        resources=tuple(resources_sorted),
        artifacts=artifacts,
    )


def derive_cache_pool_consumers(
    workflow_ir: WorkflowIr,
    *,
    template_vars: Optional[Mapping[str, object]],
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Tuple[Dict[str, FrozenSet[Tuple[str, str]]], Dict[Tuple[str, str], FrozenSet[str]]]:
    """基于 `workflow IR` + `demand YAML` 推导缓存消费者集合上界.

    `v0`: 仅覆盖 `cache_mode=preload_forever` 的 `sources`,按 `(kind, source_id)` 聚合.
    """

    loader = YamlDemandLoader()

    logical_keys_by_node_id: Dict[str, FrozenSet[Tuple[str, str]]] = {}
    consumers_by_logical_key: Dict[Tuple[str, str], Set[str]] = {}

    for node in workflow_ir.nodes:
        node_id = str(node.node_id)
        keys: Set[Tuple[str, str]] = set()
        demand_path = node.demand_path if isinstance(node, WorkflowNodeIr) else None
        if demand_path is not None:
            config = loader.load(str(demand_path), template_vars=template_vars, allowed_yaml_roots=allowed_yaml_roots)
            for source_id, source in config.sources.items():
                if str(source.cache_mode or "") != "preload_forever":
                    continue
                logical_key = ("preload_forever", str(source_id))
                keys.add(logical_key)
                consumers_by_logical_key.setdefault(logical_key, set()).add(node_id)

        logical_keys_by_node_id[node_id] = frozenset(keys)

    consumers_frozen = {key: frozenset(sorted(node_ids)) for key, node_ids in consumers_by_logical_key.items()}
    return logical_keys_by_node_id, consumers_frozen


__all__ = [
    "compile_workflow_ir",
    "derive_cache_pool_consumers",
]
