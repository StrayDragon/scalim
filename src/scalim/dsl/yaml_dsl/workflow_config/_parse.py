# pragma: allow-c901-file plan: c75
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ....workflow.errors import ScalimWorkflowConfigError
from .._internal.config_parsing.book_branch_parse import parse_book_config_mapping
from ..init_var_nodes import OptionalPathNode, parse_init_var_ref
from ..schema_dsl.constants import DEFAULT_OUTPUT_ENCODING
from ..schema_dsl.models import (
    BookConfig,
    BookExportXlsxConfig,
    FileConfig,
    ResourcesConfig,
)
from ._models import (
    WorkflowConfig,
    WorkflowRun,
)

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


def _raise_if_workflow_options_present(wf: Mapping[str, Any]) -> None:
    if "options" not in wf:
        return
    msg = (
        "workflow.options was moved out of workflow YAML (runtime policy boundary). "
        "Migration: delete workflow.options from YAML and configure runtime via entrypoints "
        "(e.g. run_workflow(..., options=WorkflowRunOptions(demand=DemandRunOptions(...), runtime=WorkflowRuntimeOptions(...)))). "
        "Examples: WorkflowRuntimeOptions(execution=WorkflowExecutionOptions(max_concurrency=2)); "
        "cache_pool via WorkflowCachePoolPreloadForeverUnlimited() "
        "or WorkflowCachePoolPreloadForeverShared(max_entries=16)."
    )
    raise ScalimWorkflowConfigError(msg, path="workflow.options")


def _parse_run_depends_on(depends_on_raw: Any, *, item_path: str) -> Tuple[str, ...]:
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


def _parse_run_main_rows_from(main_rows_from_raw: Any, *, item_path: str) -> Optional[str]:
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


def _parse_run_init_vars(init_vars_raw: Any, *, item_path: str) -> Optional[Dict[str, Any]]:
    msg: str
    if init_vars_raw is None:
        return None
    if not isinstance(init_vars_raw, dict):
        msg = "run.init_vars must be a mapping"
        raise ScalimWorkflowConfigError(msg, path="{}.init_vars".format(item_path))
    init_vars = cast("Dict[str, Any]", init_vars_raw)  # pragma: allow-cast yaml mapping typed narrowing
    out: Dict[str, Any] = {}
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


def _parse_path_or_init_var(raw: Any, *, path: str) -> OptionalPathNode:
    if isinstance(raw, dict):
        return parse_init_var_ref(cast("Dict[str, Any]", raw), path=path)  # pragma: allow-cast yaml dict
    if raw is None:
        return None
    if isinstance(raw, os.PathLike):
        return str(os.fspath(raw)).strip()
    if isinstance(raw, str):
        return raw.strip()
    msg = "{} must be a non-empty string or {{$init_var: <name>}}".format(path)
    raise ScalimWorkflowConfigError(msg, path=path)


def _parse_book_export_xlsx(raw: Any, *, path: str) -> BookExportXlsxConfig:
    msg: str
    if not isinstance(raw, dict):
        msg = "{} must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)

    data = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(data, path=path)
    unknown = sorted({str(k) for k in data} - {"path", "allow_formulas"})
    if unknown:
        if "write_lock" in unknown:
            msg = "{}.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json".format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.write_lock".format(path))
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    export_path = _parse_path_or_init_var(data.get("path"), path="{}.path".format(path))
    if not export_path or (isinstance(export_path, str) and not export_path.strip()):
        msg = "{}.path is required".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))
    if isinstance(export_path, str) and Path(export_path).suffix.lower() == ".xlsx":
        msg = (
            "{}.path now expects an output root directory, not a file path. "
            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
        ).format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.path".format(path))

    allow_formulas_raw = data.get("allow_formulas", True)
    if not isinstance(allow_formulas_raw, bool):
        msg = "{}.allow_formulas must be a bool".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.allow_formulas".format(path))

    return BookExportXlsxConfig(path=export_path, allow_formulas=bool(allow_formulas_raw))


def _parse_book_config(raw: Any, *, path: str) -> BookConfig:
    msg: str
    if not isinstance(raw, dict):
        msg = "{} must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)

    cfg = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing

    def _error(message: str, path: Optional[str] = None) -> ScalimWorkflowConfigError:
        return ScalimWorkflowConfigError(message, path=str(path or ""))

    return parse_book_config_mapping(
        cfg,
        path=path,
        parse_path_or_init_var=_parse_path_or_init_var,
        raise_if_import_present=_raise_if_import_present,
        error_factory=_error,
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


def _parse_file_config(raw: Any, *, path: str) -> FileConfig:  # noqa: C901
    msg: str
    if not isinstance(raw, dict):
        msg = "{} must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)
    typed = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(typed, path=path)
    if "write_lock" in typed:
        msg = "{}.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.write_lock".format(path))

    if "kind" in typed:
        kind = str(typed.get("kind") or "").strip()
        if kind == "csv_file":
            msg = (
                "{}.kind was removed. Migration: use oneOf branch object: {}.csv_file: {{path: <output_root>, encoding?: utf-8}}."
            ).format(path, path)
        else:
            msg = "{}.kind was removed. Migration: use oneOf branch object: {}.csv_file: {{...}}.".format(path, path)
        raise ScalimWorkflowConfigError(msg, path="{}.kind".format(path))

    allowed_keys = {"csv_file"}
    unknown = sorted({str(k) for k in typed} - allowed_keys)
    if unknown:
        msg = "{} has unknown keys: {}".format(path, ", ".join(unknown))
        raise ScalimWorkflowConfigError(msg, path=path)

    if "csv_file" not in typed:
        msg = "{}.csv_file is required".format(path)
        raise ScalimWorkflowConfigError(msg, path=path)

    csv_file_raw = typed.get("csv_file")
    if not isinstance(csv_file_raw, dict):
        msg = "{}.csv_file must be a mapping".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.csv_file".format(path))
    csv_file = cast("Dict[str, Any]", csv_file_raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(csv_file, path="{}.csv_file".format(path))
    unknown_branch = sorted({str(k) for k in csv_file} - {"path", "encoding"})
    if unknown_branch:
        if "write_lock" in unknown_branch:
            msg = (
                "{}.csv_file.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json"
            ).format(path)
            raise ScalimWorkflowConfigError(msg, path="{}.csv_file.write_lock".format(path))
        msg = "{}.csv_file has unknown keys: {}".format(path, ", ".join(unknown_branch))
        raise ScalimWorkflowConfigError(msg, path="{}.csv_file".format(path))

    file_path = _parse_path_or_init_var(csv_file.get("path"), path="{}.csv_file.path".format(path))
    if file_path is None or (isinstance(file_path, str) and not file_path.strip()):
        msg = "{}.csv_file.path is required".format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.csv_file.path".format(path))
    if isinstance(file_path, str) and Path(file_path).suffix.lower() == ".csv":
        msg = (
            "{}.csv_file.path now expects an output root directory, not a file path. "
            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
        ).format(path)
        raise ScalimWorkflowConfigError(msg, path="{}.csv_file.path".format(path))

    encoding_raw = csv_file.get("encoding")
    encoding = str(encoding_raw or "").strip() if isinstance(encoding_raw, str) else ""
    encoding = encoding or DEFAULT_OUTPUT_ENCODING

    return FileConfig(kind="csv_file", path=file_path, encoding=encoding)


def load_workflow_config_from_mapping(root: Dict[str, Any]) -> WorkflowConfig:
    """从已解析的 `mapping` 加载 `workflow` 配置(用于文本校验/编辑器等无文件系统场景)."""
    msg: str
    wf_raw = root.get("workflow")
    if not isinstance(wf_raw, dict):
        msg = "Missing required mapping 'workflow'"
        raise ScalimWorkflowConfigError(msg, path="workflow")
    wf = cast("Dict[str, Any]", wf_raw)  # pragma: allow-cast yaml mapping typed narrowing
    _raise_if_import_present(wf, path="workflow")
    _raise_if_workflow_options_present(wf)

    runs, seen_ids = _load_workflow_runs(wf)
    _validate_workflow_deps(runs, seen_ids=seen_ids)
    _validate_workflow_main_rows_from(runs, seen_ids=seen_ids)
    resources = _load_workflow_resources(wf)

    return WorkflowConfig(
        runs=tuple(runs),
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
