import json
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ....workflow.errors import ScalimWorkflowConfigError
from ..init_var_nodes import parse_init_var_mapping_node
from ..schema_dsl.constants import DEFAULT_OUTPUT_ENCODING
from ..schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    FileConfig,
    ResourcesConfig,
)
from ..schema_dsl.output_enums import (
    BOOK_KINDS,
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
from ._models import (
    WorkflowCachePoolBudget,
    WorkflowCachePoolOptions,
    WorkflowCachePoolPin,
    WorkflowConfig,
    WorkflowCtxOptions,
    WorkflowOptions,
    WorkflowRun,
)

_FAILURE_POLICIES = ("all_fail", "primary_only")
_CACHE_POOL_CONFLICT_POLICIES = ("error", "separate", "warn")
_CACHE_POOL_RELEASE_POLICIES = ("dag_refcount", "workflow_end")
_CACHE_POOL_OVER_BUDGET_POLICIES = ("fail_fast", "evict_lru")
_CACHE_POOL_PIN_KINDS = ("preload_forever",)

_INTERNAL_NODE_ID_PREFIX = "__wf__"
_IMPORT_KEY = "$import"
_IMPORTS_KEY = "imports"


def _raise_if_import_present(data: Mapping[str, Any], *, path: str) -> None:
    found_import_key = _IMPORT_KEY in data
    found_imports_key = _IMPORTS_KEY in data
    if not (found_import_key or found_imports_key):
        return
    bad_key = _IMPORT_KEY if found_import_key else _IMPORTS_KEY
    msg = (
        "workflow YAML does not support `imports`/`$import` (no imports expansion). "
        "Hint: inline the config under `workflow.resources.*`, or move the reuse to demand YAML via YAML anchors (`_templates`)."
    )
    raise ScalimWorkflowConfigError(msg, path="{}.{}".format(path, bad_key))


def _parse_run_depends_on(depends_on_raw: object, *, item_path: str) -> Tuple[str, ...]:
    msg: str
    depends_on: Tuple[str, ...] = ()
    if depends_on_raw is None:
        return depends_on

    if not isinstance(depends_on_raw, list):
        msg = "run.depends_on must be a list of strings"
        raise ScalimWorkflowConfigError(msg, path="{}.depends_on".format(item_path))

    depends_on_list: List[str] = []
    for dep_idx, dep_raw in enumerate(cast("List[Any]", depends_on_raw)):  # pragma: allow-cast yaml list typed narrowing
        dep_path = "{}.depends_on.{}".format(item_path, dep_idx)
        dep_id = str(dep_raw or "").strip() if isinstance(dep_raw, str) else ""
        if not dep_id:
            msg = "run.depends_on items must be non-empty strings"
            raise ScalimWorkflowConfigError(msg, path=dep_path)
        depends_on_list.append(dep_id)

    # 去重但保留顺序
    seen: Set[str] = set()
    ordered: List[str] = []
    for dep_id in depends_on_list:
        if dep_id in seen:
            continue
        seen.add(dep_id)
        ordered.append(dep_id)

    return tuple(ordered)


def _parse_run_main_rows_from(main_rows_from_raw: object, *, item_path: str) -> Optional[str]:
    msg: str
    if main_rows_from_raw is None:
        return None
    if not isinstance(main_rows_from_raw, dict):
        msg = "run.main_rows_from must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="{}.main_rows_from".format(item_path))
    main_rows_from = cast("Dict[str, Any]", main_rows_from_raw)  # pragma: allow-cast yaml mapping typed narrowing
    run_raw = main_rows_from.get("run")
    run_id = str(run_raw or "").strip() if isinstance(run_raw, str) else ""
    if not run_id:
        msg = "run.main_rows_from.run must be a non-empty string"
        raise ScalimWorkflowConfigError(msg, path="{}.main_rows_from.run".format(item_path))
    unknown = sorted({str(k) for k in main_rows_from if str(k) != "run"})
    if unknown:
        msg = "run.main_rows_from has unknown keys: {}".format(", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path="{}.main_rows_from".format(item_path))
    return run_id


def _parse_run_init_vars(init_vars_raw: object, *, item_path: str) -> Optional[Dict[str, object]]:
    msg: str
    if init_vars_raw is None:
        return None
    if not isinstance(init_vars_raw, dict):
        msg = "run.init_vars must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="{}.init_vars".format(item_path))
    init_vars = cast("Dict[str, Any]", init_vars_raw)  # pragma: allow-cast yaml mapping typed narrowing
    out: Dict[str, object] = {}
    for raw_key, raw_value in init_vars.items():
        key = str(raw_key or "").strip() if isinstance(raw_key, str) else ""
        if not key:
            msg = "run.init_vars keys must be non-empty strings"
            raise ScalimWorkflowConfigError(msg, path="{}.init_vars".format(item_path))
        # 允许任意 `JSON-like` 值; `$ctx` 指令由工作流运行时渲染与校验.
        out[key] = raw_value
    return out


def _load_workflow_runs(wf: Mapping[str, Any]) -> Tuple[List[WorkflowRun], Dict[str, int]]:  # noqa: C901
    msg: str
    runs_raw = wf.get("runs")
    if not isinstance(runs_raw, list) or not runs_raw:
        msg = "workflow.runs must be a non-empty list"
        raise ScalimWorkflowConfigError(msg, path="workflow.runs")

    seen_ids: Dict[str, int] = {}
    runs: List[WorkflowRun] = []
    for idx, item_raw in enumerate(cast("List[Any]", runs_raw)):  # pragma: allow-cast yaml list typed narrowing
        item_path = "workflow.runs.{}".format(idx)
        if not isinstance(item_raw, dict):
            msg = "run entry must be a mapping"
            raise ScalimWorkflowConfigError(msg, path=item_path)

        run_dict = cast("Dict[str, Any]", item_raw)  # pragma: allow-cast yaml mapping typed narrowing

        if "deps" in run_dict:
            msg = "run.deps was removed; use run.depends_on"
            raise ScalimWorkflowConfigError(msg, path="{}.deps".format(item_path))
        if "write_to" in run_dict:
            msg = "run.write_to was removed; migrate IO bindings to demand outputs (outputs[*].to / outputs[*].write)"
            raise ScalimWorkflowConfigError(msg, path="{}.write_to".format(item_path))
        if "writes" in run_dict:
            msg = "run.writes was removed; migrate IO bindings to demand outputs (outputs[*].to / outputs[*].write)"
            raise ScalimWorkflowConfigError(msg, path="{}.writes".format(item_path))

        run_id_raw = run_dict.get("id")
        demand_raw = run_dict.get("demand")

        run_id = str(run_id_raw or "").strip()
        if not run_id:
            msg = "run.id must be a non-empty string"
            raise ScalimWorkflowConfigError(msg, path="{}.id".format(item_path))
        if run_id.startswith(_INTERNAL_NODE_ID_PREFIX):
            msg = "run.id must not start with reserved prefix '{}'".format(_INTERNAL_NODE_ID_PREFIX)
            raise ScalimWorkflowConfigError(msg, path="{}.id".format(item_path))

        if run_id in seen_ids:
            msg = "Duplicate run.id '{}'".format(run_id)
            raise ScalimWorkflowConfigError(msg, path="{}.id".format(item_path))
        seen_ids[run_id] = idx

        demand = str(demand_raw or "").strip()
        if not demand:
            msg = "run.demand must be a non-empty string"
            raise ScalimWorkflowConfigError(msg, path="{}.demand".format(item_path))

        depends_on = _parse_run_depends_on(run_dict.get("depends_on"), item_path=item_path)
        main_rows_from_run_id = _parse_run_main_rows_from(run_dict.get("main_rows_from"), item_path=item_path)
        init_vars = _parse_run_init_vars(run_dict.get("init_vars"), item_path=item_path)

        runs.append(
            WorkflowRun(
                id=run_id,
                demand=demand,
                depends_on=depends_on,
                main_rows_from_run_id=main_rows_from_run_id,
                init_vars=init_vars,
            )
        )

    return runs, seen_ids


def _parse_path_or_init_var(raw: object, *, path: str) -> Any:
    if isinstance(raw, dict):
        return {"$init_var": parse_init_var_mapping_node(cast("Dict[str, Any]", raw), path=path)}  # pragma: allow-cast yaml dict
    if raw is None:
        return None
    if isinstance(raw, os.PathLike):
        return str(os.fspath(raw)).strip()
    if isinstance(raw, str):
        return raw.strip()
    msg = "{} must be a non-empty string or {{$init_var: <name>}}".format(path)
    raise ScalimWorkflowConfigError(msg, path=path)


def _parse_book_budget(raw: object, *, path: str) -> BookBudgetConfig:
    msg: str
    if not isinstance(raw, dict):
        msg = "{} must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)

    data = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(data, path=path)
    unknown = sorted({str(k) for k in data} - {"max_sheets", "max_total_cells"})
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    max_sheets_raw = data.get("max_sheets")
    max_total_cells_raw = data.get("max_total_cells")
    if max_sheets_raw is None:
        msg = "{}.max_sheets must be an integer >= 1".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.max_sheets".format(path))
    if max_total_cells_raw is None:
        msg = "{}.max_total_cells must be an integer >= 1".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.max_total_cells".format(path))
    try:
        max_sheets = int(max_sheets_raw)
    except (TypeError, ValueError):
        msg = "{}.max_sheets must be an integer >= 1".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.max_sheets".format(path)) from None
    try:
        max_total_cells = int(max_total_cells_raw)
    except (TypeError, ValueError):
        msg = "{}.max_total_cells must be an integer >= 1".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.max_total_cells".format(path)) from None
    if max_sheets < 1:
        msg = "{}.max_sheets must be >= 1".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.max_sheets".format(path))
    if max_total_cells < 1:
        msg = "{}.max_total_cells must be >= 1".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.max_total_cells".format(path))

    return BookBudgetConfig(max_sheets=max_sheets, max_total_cells=max_total_cells)


def _parse_book_export_xlsx(raw: object, *, path: str) -> BookExportXlsxConfig:
    msg: str
    if not isinstance(raw, dict):
        msg = "{} must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)

    data = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(data, path=path)
    unknown = sorted({str(k) for k in data} - {"path", "write_lock", "allow_formulas"})
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    export_path = _parse_path_or_init_var(data.get("path"), path="{}.path".format(path))
    if not export_path or (isinstance(export_path, str) and not export_path.strip()):
        msg = "{}.path is required".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))

    write_lock_raw = data.get("write_lock", False)
    if not isinstance(write_lock_raw, bool):
        msg = "{}.write_lock must be a bool".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.write_lock".format(path))

    allow_formulas_raw = data.get("allow_formulas", False)
    if not isinstance(allow_formulas_raw, bool):
        msg = "{}.allow_formulas must be a bool".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))

    return BookExportXlsxConfig(path=export_path, write_lock=bool(write_lock_raw), allow_formulas=bool(allow_formulas_raw))


def _parse_book_write_defaults(raw: object, *, path: str) -> BookWriteDefaultsConfig:
    msg: str
    if not isinstance(raw, dict):
        msg = "{} must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)

    data = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(data, path=path)
    unknown = sorted({str(k) for k in data} - {"mode", "align_by", "header_policy", "on_mismatch", "on_conflict"})
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    mode = str(data.get("mode") or DEFAULT_BOOK_WRITE_MODE).strip() or DEFAULT_BOOK_WRITE_MODE
    if mode not in BOOK_WRITE_MODE_ENUM:
        msg = "{}.mode={!r} is invalid; expected one of: {}".format(path, mode, ", ".join(BOOK_WRITE_MODE_ENUM))
        raise ScalimWorkflowConfigError(msg, path="{}.mode".format(path))

    align_by = str(data.get("align_by") or DEFAULT_BOOK_WRITE_ALIGN_BY).strip() or DEFAULT_BOOK_WRITE_ALIGN_BY
    if align_by not in BOOK_WRITE_ALIGN_BY_ENUM:
        msg = "{}.align_by={!r} is invalid; expected one of: {}".format(path, align_by, ", ".join(BOOK_WRITE_ALIGN_BY_ENUM))
        raise ScalimWorkflowConfigError(msg, path="{}.align_by".format(path))

    header_policy = str(data.get("header_policy") or DEFAULT_BOOK_WRITE_HEADER_POLICY).strip() or DEFAULT_BOOK_WRITE_HEADER_POLICY
    if header_policy not in BOOK_WRITE_HEADER_POLICY_ENUM:
        msg = "{}.header_policy={!r} is invalid; expected one of: {}".format(path, header_policy, ", ".join(BOOK_WRITE_HEADER_POLICY_ENUM))
        raise ScalimWorkflowConfigError(msg, path="{}.header_policy".format(path))

    on_mismatch = str(data.get("on_mismatch") or DEFAULT_BOOK_WRITE_ON_MISMATCH).strip() or DEFAULT_BOOK_WRITE_ON_MISMATCH
    if on_mismatch not in BOOK_WRITE_ON_MISMATCH_ENUM:
        msg = "{}.on_mismatch={!r} is invalid; expected one of: {}".format(path, on_mismatch, ", ".join(BOOK_WRITE_ON_MISMATCH_ENUM))
        raise ScalimWorkflowConfigError(msg, path="{}.on_mismatch".format(path))

    on_conflict = str(data.get("on_conflict") or DEFAULT_BOOK_WRITE_ON_CONFLICT).strip() or DEFAULT_BOOK_WRITE_ON_CONFLICT
    if on_conflict not in BOOK_WRITE_ON_CONFLICT_ENUM:
        msg = "{}.on_conflict={!r} is invalid; expected one of: {}".format(path, on_conflict, ", ".join(BOOK_WRITE_ON_CONFLICT_ENUM))
        raise ScalimWorkflowConfigError(msg, path="{}.on_conflict".format(path))

    return BookWriteDefaultsConfig(
        mode=mode,
        align_by=align_by,
        header_policy=header_policy,
        on_mismatch=on_mismatch,
        on_conflict=on_conflict,
    )


def _parse_book_config(raw: object, *, path: str) -> BookConfig:  # noqa: C901, PLR0912, PLR0915
    msg: str
    if not isinstance(raw, dict):
        msg = "{} must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)

    cfg = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(cfg, path=path)

    allowed_keys = {"kind", "path", "budget", "export_xlsx", "allow_formulas", "write_lock", "write_defaults"}
    unknown = sorted({str(k) for k in cfg} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    kind = str(cfg.get("kind") or "").strip()
    if not kind:
        msg = "{}.kind is required".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))
    if kind not in BOOK_KINDS:
        msg = "{}.kind={!r} is invalid; expected one of: {}".format(path, kind, ", ".join(BOOK_KINDS))
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))

    has_allow_formulas = "allow_formulas" in cfg
    has_write_lock = "write_lock" in cfg

    book_path = _parse_path_or_init_var(cfg.get("path"), path="{}.path".format(path))
    budget_cfg = _parse_book_budget(cfg.get("budget"), path="{}.budget".format(path)) if "budget" in cfg else None
    export_cfg = _parse_book_export_xlsx(cfg.get("export_xlsx"), path="{}.export_xlsx".format(path)) if "export_xlsx" in cfg else None
    write_defaults_cfg = (
        _parse_book_write_defaults(cfg.get("write_defaults"), path="{}.write_defaults".format(path)) if "write_defaults" in cfg else None
    )

    allow_formulas_raw = cfg.get("allow_formulas", False)
    if not isinstance(allow_formulas_raw, bool):
        msg = "{}.allow_formulas must be a bool".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))

    write_lock_raw = cfg.get("write_lock", False)
    if not isinstance(write_lock_raw, bool):
        msg = "{}.write_lock must be a bool".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.write_lock".format(path))

    # 语义层约束(即使 `schema` 已覆盖,仍保持 `fail-fast` 便于诊断).
    if kind == "xlsx_file":
        if not book_path or (isinstance(book_path, str) and not book_path.strip()):
            msg = "{}.path is required for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
        if budget_cfg is not None:
            msg = "{}.budget is not allowed for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
        if export_cfg is not None:
            msg = "{}.export_xlsx is not allowed for kind=xlsx_file".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.export_xlsx".format(path))

    if kind == "xlsx_memory":
        if budget_cfg is None:
            msg = "{}.budget is required for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.budget".format(path))
        if book_path is not None:
            msg = "{}.path is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
        if has_allow_formulas:
            msg = "{}.allow_formulas is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))
        if has_write_lock:
            msg = "{}.write_lock is not allowed for kind=xlsx_memory".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.write_lock".format(path))

    return BookConfig(
        kind=kind,
        path=book_path,
        budget=budget_cfg,
        export_xlsx=export_cfg,
        allow_formulas=bool(allow_formulas_raw),
        write_lock=bool(write_lock_raw),
        write_defaults=write_defaults_cfg,
    )


def _load_workflow_resources(wf: Mapping[str, Any]) -> ResourcesConfig:  # noqa: C901, PLR0912, PLR0915
    msg: str
    resources_raw = wf.get("resources", {})
    if resources_raw is None:
        resources_raw = {}

    if not isinstance(resources_raw, dict):
        msg = "workflow.resources must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="workflow.resources")

    resources = cast("Dict[str, Any]", resources_raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(resources, path="workflow.resources")
    for raw_key in resources:
        if not isinstance(raw_key, str) or not raw_key.strip():
            msg = "workflow.resources keys must be non-empty strings"
            raise ScalimWorkflowConfigError(msg, path="workflow.resources")

    allowed_keys = {"books", "files"}
    unknown = sorted({str(k) for k in resources} - allowed_keys)
    if unknown:
        legacy = [k for k in unknown if k in {"workbooks", "sheetbooks", "csvs"}]
        if legacy:
            msg = "workflow.resources.{} was removed; migrate to workflow.resources.books / workflow.resources.files".format(
                ",".join(sorted(legacy))
            )
            raise ScalimWorkflowConfigError(msg, path="workflow.resources")
        msg = "workflow.resources contains unknown keys: {}".format(", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path="workflow.resources")

    books_raw = resources.get("books", {})
    if books_raw is None:
        books_raw = {}
    if not isinstance(books_raw, dict):
        msg = "workflow.resources.books must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")

    books_dict = cast("Dict[str, Any]", books_raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(books_dict, path="workflow.resources.books")
    books: Dict[str, BookConfig] = {}
    for raw_book_id, raw_book_cfg in cast("Dict[Any, Any]", books_raw).items():  # pragma: allow-cast yaml mapping typed narrowing
        book_id = str(raw_book_id or "").strip() if isinstance(raw_book_id, str) else ""
        if not book_id:
            msg = "workflow.resources.books keys must be non-empty strings"
            raise ScalimWorkflowConfigError(msg, path="workflow.resources.books")
        item_path = "workflow.resources.books.{}".format(book_id)
        books[book_id] = _parse_book_config(raw_book_cfg, path=item_path)

    files_raw = resources.get("files", {})
    if files_raw is None:
        files_raw = {}
    if not isinstance(files_raw, dict):
        msg = "workflow.resources.files must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="workflow.resources.files")

    files_dict = cast("Dict[str, Any]", files_raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(files_dict, path="workflow.resources.files")
    files: Dict[str, FileConfig] = {}
    for raw_file_id, raw_file_cfg in cast("Dict[Any, Any]", files_raw).items():  # pragma: allow-cast yaml mapping typed narrowing
        file_id = str(raw_file_id or "").strip() if isinstance(raw_file_id, str) else ""
        if not file_id:
            msg = "workflow.resources.files keys must be non-empty strings"
            raise ScalimWorkflowConfigError(msg, path="workflow.resources.files")
        item_path = "workflow.resources.files.{}".format(file_id)
        files[file_id] = _parse_file_config(raw_file_cfg, path=item_path)

    return ResourcesConfig(books=books, files=files)


def _parse_file_config(raw: object, *, path: str) -> FileConfig:
    msg: str
    if not isinstance(raw, dict):
        msg = "{} must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)
    typed = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(typed, path=path)
    allowed_keys = {"kind", "path", "encoding", "write_lock"}
    unknown = sorted({str(k) for k in typed} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    kind_raw = typed.get("kind")
    kind = str(kind_raw or "").strip() if isinstance(kind_raw, str) else ""
    if not kind:
        msg = "{}.kind is required".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))
    if kind not in FILE_KINDS:
        msg = "{}.kind={!r} is invalid; expected one of: {}".format(path, kind, ", ".join(FILE_KINDS))
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))

    file_path = _parse_path_or_init_var(typed.get("path"), path="{}.path".format(path))
    if file_path is None:
        msg = "{}.path is required for kind=csv_file".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))

    encoding_raw = typed.get("encoding")
    encoding = str(encoding_raw or "").strip() if isinstance(encoding_raw, str) else ""
    encoding = encoding or DEFAULT_OUTPUT_ENCODING

    write_lock_raw = typed.get("write_lock", False)
    if not isinstance(write_lock_raw, bool):
        msg = "{}.write_lock must be a boolean".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.write_lock".format(path))
    write_lock = bool(write_lock_raw)

    return FileConfig(kind=kind, path=file_path, encoding=encoding, write_lock=write_lock)


def _load_workflow_ctx_options(ctx_raw: object) -> WorkflowCtxOptions:
    msg: str
    ctx = WorkflowCtxOptions()
    if ctx_raw is None:
        return ctx
    if not isinstance(ctx_raw, dict):
        msg = "workflow.options.ctx must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx")
    ctx_dict = cast("Dict[str, Any]", ctx_raw)  # pragma: allow-cast yaml mapping typed narrowing

    max_value_bytes_raw = ctx_dict.get("max_value_bytes", 65536)
    if isinstance(max_value_bytes_raw, bool) or not isinstance(max_value_bytes_raw, (int, float, str)):
        msg = "workflow.options.ctx.max_value_bytes must be an integer >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx.max_value_bytes")
    try:
        max_value_bytes = int(max_value_bytes_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.ctx.max_value_bytes must be an integer >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx.max_value_bytes") from exc
    if max_value_bytes < 1:
        msg = "workflow.options.ctx.max_value_bytes must be >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx.max_value_bytes")

    max_bytes_raw = ctx_dict.get("max_bytes", 1048576)
    if isinstance(max_bytes_raw, bool) or not isinstance(max_bytes_raw, (int, float, str)):
        msg = "workflow.options.ctx.max_bytes must be an integer >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx.max_bytes")
    try:
        max_bytes = int(max_bytes_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.ctx.max_bytes must be an integer >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx.max_bytes") from exc
    if max_bytes < 1:
        msg = "workflow.options.ctx.max_bytes must be >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx.max_bytes")

    return WorkflowCtxOptions(
        max_value_bytes=max_value_bytes,
        max_bytes=max_bytes,
    )


def _parse_workflow_cache_pool_budget(budget_raw: object) -> WorkflowCachePoolBudget:
    msg: str
    if not isinstance(budget_raw, dict):
        msg = "workflow.options.cache_pool.budget must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool.budget")

    data = cast("Dict[str, Any]", budget_raw)  # pragma: allow-cast yaml mapping typed narrowing
    max_entries_raw = data.get("max_entries")
    if isinstance(max_entries_raw, bool) or not isinstance(max_entries_raw, (int, float, str)):
        msg = "workflow.options.cache_pool.budget.max_entries must be an integer >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool.budget.max_entries")
    try:
        max_entries = int(max_entries_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.cache_pool.budget.max_entries must be an integer >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool.budget.max_entries") from exc
    if max_entries < 1:
        msg = "workflow.options.cache_pool.budget.max_entries must be >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool.budget.max_entries")

    over_budget_policy = str(data.get("over_budget_policy", "") or "").strip()
    if over_budget_policy not in _CACHE_POOL_OVER_BUDGET_POLICIES:
        msg = "workflow.options.cache_pool.budget.over_budget_policy must be one of: {}".format("/".join(_CACHE_POOL_OVER_BUDGET_POLICIES))
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool.budget.over_budget_policy")

    return WorkflowCachePoolBudget(
        max_entries=max_entries,
        over_budget_policy=over_budget_policy,
    )


def _parse_workflow_cache_pool_pins(pin_raw: object) -> Tuple[WorkflowCachePoolPin, ...]:
    msg: str
    if pin_raw is None:
        pin_raw = []

    if not isinstance(pin_raw, list):
        msg = "workflow.options.cache_pool.pin must be a list of mappings"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool.pin")

    pins: List[WorkflowCachePoolPin] = []
    for idx, item in enumerate(cast("List[Any]", pin_raw)):  # pragma: allow-cast yaml list typed narrowing
        pin_path = "workflow.options.cache_pool.pin.{}".format(idx)
        if not isinstance(item, dict):
            msg = "workflow.options.cache_pool.pin items must be mappings"
            raise ScalimWorkflowConfigError(msg, path=pin_path)
        pin_dict = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
        kind = str(pin_dict.get("kind", "") or "").strip()
        if kind not in _CACHE_POOL_PIN_KINDS:
            msg = "workflow.options.cache_pool.pin[*].kind must be one of: {}".format("/".join(_CACHE_POOL_PIN_KINDS))
            raise ScalimWorkflowConfigError(msg, path="{}.kind".format(pin_path))
        source_id = str(pin_dict.get("source_id", "") or "").strip()
        if not source_id:
            msg = "workflow.options.cache_pool.pin[*].source_id must be a non-empty string"
            raise ScalimWorkflowConfigError(msg, path="{}.source_id".format(pin_path))
        pins.append(WorkflowCachePoolPin(kind=kind, source_id=source_id))
    return tuple(pins)


def _load_workflow_cache_pool_options(cache_pool_raw: object) -> Optional[WorkflowCachePoolOptions]:
    msg: str
    if cache_pool_raw is None:
        return None

    if not isinstance(cache_pool_raw, dict):
        msg = "workflow.options.cache_pool must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool")

    cache_pool_dict = cast("Dict[str, Any]", cache_pool_raw)  # pragma: allow-cast yaml mapping typed narrowing

    conflict_policy = str(cache_pool_dict.get("conflict_policy", "") or "").strip()
    if conflict_policy not in _CACHE_POOL_CONFLICT_POLICIES:
        msg = "workflow.options.cache_pool.conflict_policy must be one of: {}".format("/".join(_CACHE_POOL_CONFLICT_POLICIES))
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool.conflict_policy")

    release_policy = str(cache_pool_dict.get("release_policy", "") or "").strip()
    if release_policy not in _CACHE_POOL_RELEASE_POLICIES:
        msg = "workflow.options.cache_pool.release_policy must be one of: {}".format("/".join(_CACHE_POOL_RELEASE_POLICIES))
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool.release_policy")

    budget = _parse_workflow_cache_pool_budget(cache_pool_dict.get("budget"))
    pins = _parse_workflow_cache_pool_pins(cache_pool_dict.get("pin"))
    return WorkflowCachePoolOptions(
        conflict_policy=conflict_policy,
        release_policy=release_policy,
        budget=budget,
        pin=pins,
    )


def _load_workflow_options(wf: Mapping[str, Any]) -> WorkflowOptions:
    msg: str
    options_raw = wf.get("options", {})
    if options_raw is None:
        options_raw = {}
    if not isinstance(options_raw, dict):
        msg = "workflow.options must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="workflow.options")
    options_dict = cast("Dict[str, Any]", options_raw)  # pragma: allow-cast yaml mapping typed narrowing

    max_concurrency_raw = options_dict.get("max_concurrency", 1)
    if isinstance(max_concurrency_raw, bool) or not isinstance(max_concurrency_raw, (int, float, str)):
        msg = "workflow.options.max_concurrency must be an integer >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.max_concurrency")
    try:
        max_concurrency = int(max_concurrency_raw)
    except (TypeError, ValueError) as exc:
        msg = "workflow.options.max_concurrency must be an integer >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.max_concurrency") from exc
    if max_concurrency < 1:
        msg = "workflow.options.max_concurrency must be >= 1"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.max_concurrency")

    failure_policy = str(options_dict.get("failure_policy", "all_fail") or "all_fail").strip()
    if failure_policy not in _FAILURE_POLICIES:
        msg = "workflow.options.failure_policy must be one of: {}".format("/".join(_FAILURE_POLICIES))
        raise ScalimWorkflowConfigError(msg, path="workflow.options.failure_policy")

    ctx = _load_workflow_ctx_options(options_dict.get("ctx"))

    if "share_preload_cache" in options_dict:
        msg = "workflow.options.share_preload_cache was removed; use workflow.options.cache_pool"
        raise ScalimWorkflowConfigError(msg, path="workflow.options.share_preload_cache")

    cache_pool = _load_workflow_cache_pool_options(options_dict.get("cache_pool"))

    if "resources_wait" in options_dict:
        msg = (
            "workflow.options.resources_wait was moved out of workflow YAML (runtime policy boundary); "
            "configure it via runtime entrypoints (e.g. run_workflow(..., workflow_resources_wait=...))."
        )
        raise ScalimWorkflowConfigError(msg, path="workflow.options.resources_wait")
    if "output_staging" in options_dict:
        msg = (
            "workflow.options.output_staging was moved out of workflow YAML (runtime policy boundary); "
            "configure it via runtime entrypoints (e.g. run_workflow(..., workflow_output_staging=...))."
        )
        raise ScalimWorkflowConfigError(msg, path="workflow.options.output_staging")

    return WorkflowOptions(
        max_concurrency=max_concurrency,
        failure_policy=failure_policy,
        cache_pool=cache_pool,
        ctx=ctx,
    )


def load_workflow_config_from_mapping(root: Dict[str, Any]) -> WorkflowConfig:
    """从已解析的 `mapping` 加载 `workflow` 配置(用于文本校验/编辑器等无文件系统场景)."""
    msg: str
    wf_raw = root.get("workflow")
    if not isinstance(wf_raw, dict):
        msg = "Missing required mapping 'workflow'"
        raise ScalimWorkflowConfigError(msg, path="workflow")
    wf = cast("Dict[str, Any]", wf_raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(wf, path="workflow")

    runs, seen_ids = _load_workflow_runs(wf)
    _validate_workflow_deps(runs, seen_ids=seen_ids)
    _validate_workflow_main_rows_from(runs, seen_ids=seen_ids)
    resources = _load_workflow_resources(wf)
    options = _load_workflow_options(wf)

    return WorkflowConfig(
        runs=tuple(runs),
        options=options,
        resources=resources,
    )


def _validate_workflow_deps(runs: Sequence[WorkflowRun], *, seen_ids: Mapping[str, int]) -> None:
    _validate_workflow_deps_references(runs, seen_ids=seen_ids)
    _validate_workflow_deps_no_cycles(runs, seen_ids=seen_ids)


def _validate_workflow_main_rows_from(runs: Sequence[WorkflowRun], *, seen_ids: Mapping[str, int]) -> None:
    msg: str
    run_ids = set(seen_ids.keys())
    for idx, run in enumerate(runs):
        producer_run_id = str(run.main_rows_from_run_id or "").strip()
        if not producer_run_id:
            continue
        item_path = "workflow.runs.{}".format(idx)

        if producer_run_id not in run_ids:
            msg = "Unknown run.main_rows_from.run id '{}'".format(producer_run_id)
            raise ScalimWorkflowConfigError(msg, path="{}.main_rows_from.run".format(item_path))

        if producer_run_id == run.id:
            msg = "run.main_rows_from.run must not reference self: '{}'".format(producer_run_id)
            raise ScalimWorkflowConfigError(msg, path="{}.main_rows_from.run".format(item_path))

        if producer_run_id not in run.depends_on:
            msg = "run.main_rows_from requires explicit depends_on: consumer={!r}, producer={!r}".format(
                str(run.id),
                str(producer_run_id),
            )
            raise ScalimWorkflowConfigError(msg, path="{}.depends_on".format(item_path))


def _validate_workflow_deps_references(
    runs: Sequence[WorkflowRun],
    *,
    seen_ids: Mapping[str, int],
) -> None:
    msg: str
    run_ids = set(seen_ids.keys())
    for idx, run in enumerate(runs):
        item_path = "workflow.runs.{}".format(idx)
        for dep_id in run.depends_on:
            if dep_id == run.id:
                msg = "run.depends_on must not include self dependency: '{}'".format(dep_id)
                raise ScalimWorkflowConfigError(msg, path="{}.depends_on".format(item_path))
            if dep_id not in run_ids:
                msg = "Unknown run.depends_on id '{}'".format(dep_id)
                raise ScalimWorkflowConfigError(msg, path="{}.depends_on".format(item_path))


def _validate_workflow_deps_no_cycles(  # noqa: C901
    runs: Sequence[WorkflowRun],
    *,
    seen_ids: Mapping[str, int],
) -> None:
    msg: str
    by_id: Dict[str, WorkflowRun] = {run.id: run for run in runs}
    ordered_ids = sorted(by_id.keys(), key=lambda rid: int(seen_ids.get(rid, 0)))

    visiting: Set[str] = set()
    visited: Set[str] = set()
    stack: List[str] = []

    def dfs(node_id: str) -> Optional[List[str]]:
        visiting.add(node_id)
        stack.append(node_id)
        run = by_id[node_id]
        for dep_id in run.depends_on:
            if dep_id not in by_id:
                continue  # pragma: no cover  # pragma: allow-no-cover invariant: depends_on references validated earlier
            if dep_id in visited:
                continue
            if dep_id in visiting:
                if dep_id in stack:
                    idx = stack.index(dep_id)
                    return [*stack[idx:], dep_id]
                return [dep_id, node_id, dep_id]  # pragma: no cover  # pragma: allow-no-cover invariant: visiting mirrors stack
            found = dfs(dep_id)
            if found is not None:
                return found

        visiting.remove(node_id)
        visited.add(node_id)
        _ = stack.pop()
        return None

    for node_id in ordered_ids:
        if node_id in visited:
            continue
        found = dfs(node_id)
        if found is not None:
            msg = "workflow depends_on must not contain cycles (cycle_path={})".format(json.dumps(found, ensure_ascii=False))
            raise ScalimWorkflowConfigError(msg, path="workflow.runs[*].depends_on")


__all__ = ()
